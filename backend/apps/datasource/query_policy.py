"""One server-owned allowlist for model context, queries and stored results.

The administrator's existing table/field switches are the global boundary, even
for the system administrator. User column/row permissions narrow it further.
No permission decision is delegated to a language model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.schema import MappingSchema

from common.utils.locale import I18n

STAMP = "_query_policy"


class QueryPolicyError(ValueError):
    def __init__(self, key="query_denied"):
        super().__init__(I18n()(lang="zh-CN")("i18n_query_policy." + key))


def dialect_for(kind):
    return {
        "pg": "postgres",
        "postgresql": "postgres",
        "excel": "postgres",
        "sqlserver": "tsql",
        "ck": "clickhouse",
        "dm": "oracle",
        "kingbase": "postgres",
        "doris": "mysql",
        "starrocks": "mysql",
        "es": "mysql",
    }.get((kind or "").lower(), (kind or "").lower() or None)


@dataclass
class QueryPolicy:
    tables: dict[str, tuple[str, ...]]
    dialect: str | None = "postgres"
    namespace: str = ""
    catalog: str = ""
    filters: dict[str, str] = field(default_factory=dict)
    identity: str = ""
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def parser_dialect(self):
        dialect = Dialect.get_or_raise(self.dialect)
        # Preserve exact metadata names when the database collation is unknown.
        if "CASE_INSENSITIVE" in dialect.normalization_strategy.name:
            dialect = type(dialect)(normalization_strategy="case_sensitive")
        return dialect

    @property
    def fingerprint(self):
        data = {
            "tables": self.tables,
            "dialect": self.dialect,
            "namespace": self.namespace,
            "catalog": self.catalog,
            "filters": self.filters,
            "identity": self.identity,
            "sources": self.sources,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def _name(self, identifier):
        if not identifier:
            return ""
        return self.parser_dialect.normalize_identifier(identifier.copy()).name

    def protect(self, sql: str, *, apply_rows=True, expand_sources=True) -> str:
        """Resolve every SQL scope against allowed columns; expand stars safely."""
        try:
            statements = sqlglot.parse(sql, read=self.dialect)
            if len(statements) != 1 or not isinstance(statements[0], exp.Query):
                raise QueryPolicyError()
            tree = normalize_identifiers(statements[0], dialect=self.parser_dialect)
            forbidden = (
                exp.Insert,
                exp.Update,
                exp.Delete,
                exp.Create,
                exp.Drop,
                exp.Alter,
                exp.Merge,
                exp.Copy,
                exp.Command,
                exp.Into,
            )
            if any(isinstance(node, forbidden) for node in tree.walk()):
                raise QueryPolicyError()
            if any(join.method == "NATURAL" for join in tree.find_all(exp.Join)):
                raise QueryPolicyError()
            private_functions = {
                "CurrentUser",
                "SessionUser",
                "CurrentSchema",
                "CurrentDatabase",
                "CurrentCatalog",
                "CurrentRole",
                "CurrentAccount",
                "Version",
            }
            if any(type(node).__name__ in private_functions for node in tree.walk()):
                raise QueryPolicyError()
            # Arbitrary UDFs can read files or external databases without naming
            # a protected column. Only common reporting functions are accepted.
            safe_anonymous = {
                "to_char",
                "date_format",
                "strftime",
                "strptime",
                "date_trunc",
                "ifnull",
                "isnull",
                "nvl",
                "nvl2",
                "decode",
                "format",
                "convert",
                "try_convert",
                "string_agg",
                "group_concat",
                "timestampdiff",
                "timestampadd",
                "datediff",
                "dateadd",
                "from_unixtime",
                "unix_timestamp",
                "formatdatetime",
                "todatetime",
                "todate",
                "tostartofmonth",
                "tostartofyear",
            }
            for func in tree.find_all(exp.Anonymous):
                if func.name.lower() not in safe_anonymous or isinstance(
                    func.parent, exp.Dot
                ):
                    raise QueryPolicyError()

            physical = []
            for scope in traverse_scope(tree):
                for _, source in scope.selected_sources.values():
                    if isinstance(source, Scope):
                        continue
                    if not isinstance(source, exp.Table) or not isinstance(
                        source.this, exp.Identifier
                    ):
                        raise QueryPolicyError()
                    name = self._name(source.this)
                    if name not in self.tables or not self.tables[name]:
                        raise QueryPolicyError()
                    if (
                        source.db
                        and self._name(source.args.get("db")) != self.namespace
                    ):
                        raise QueryPolicyError()
                    if (
                        source.catalog
                        and self._name(source.args.get("catalog")) != self.catalog
                    ):
                        raise QueryPolicyError()
                    physical.append(source)
            if not physical:
                raise QueryPolicyError()
            # Scope qualification is column-level validation, including WHERE,
            # JOIN, UNION, CTEs, correlated subqueries, ORDER/GROUP/HAVING and *.
            schema = MappingSchema(
                {
                    name: dict.fromkeys(columns, "UNKNOWN")
                    for name, columns in self.tables.items()
                },
                normalize=False,
                dialect=self.parser_dialect,
            )
            # Physical namespaces were checked above. Resolve by the allowed
            # local table name, then restore the validated namespace for execution.
            namespaces = {}
            for table in physical:
                namespaces[id(table)] = (
                    table.args.pop("db", None),
                    table.args.pop("catalog", None),
                )
            tree = qualify(
                tree,
                schema=schema,
                dialect=self.parser_dialect,
                validate_qualify_columns=True,
                allow_partial_qualification=False,
            )
            self._validate_columns(tree)
            if any(
                not isinstance(star.parent, exp.Count)
                for star in tree.find_all(exp.Star)
            ):
                raise QueryPolicyError()
            for table in physical:
                db, catalog = namespaces[id(table)]
                if db is not None:
                    table.set("db", db)
                if catalog is not None:
                    table.set("catalog", catalog)
                row_filter = self.filters.get(self._name(table.this))
                source_sql = (
                    self.sources.get(self._name(table.this)) if expand_sources else None
                )
                if source_sql:
                    source = sqlglot.parse_one(source_sql, read=self.dialect)
                    if not isinstance(source, exp.Query) or any(
                        isinstance(node, forbidden) for node in source.walk()
                    ):
                        raise QueryPolicyError()
                    original = source.subquery("_authorized_source")
                else:
                    original = table.copy()
                    original.set("alias", None)
                if apply_rows and row_filter:
                    alias = table.alias_or_name
                    # The predicate comes from server-side permission rules.
                    inner = exp.select(
                        *(
                            exp.column(name, quoted=True)
                            for name in self.tables[self._name(table.this)]
                        )
                    )
                    inner = inner.from_(original).where(
                        sqlglot.parse_one(row_filter, read=self.dialect)
                    )
                    table.replace(inner.subquery(alias, copy=False))
                elif source_sql:
                    table.replace(
                        exp.select(
                            *(
                                exp.column(name, quoted=True)
                                for name in self.tables[self._name(table.this)]
                            )
                        )
                        .from_(original)
                        .subquery(table.alias_or_name)
                    )
            return tree.sql(dialect=self.dialect)
        except QueryPolicyError:
            raise
        except Exception:
            # Never echo a forbidden identifier, schema or database error.
            raise QueryPolicyError() from None

    def _validate_columns(self, tree):
        # SQLGlot qualification intentionally permits some unresolved HAVING /
        # QUALIFY expressions. Authorization must inspect those columns too.
        for scope in traverse_scope(tree):

            def source_columns(source):
                if isinstance(source, exp.Table):
                    return self.tables.get(self._name(source.this), ())
                if isinstance(source, Scope):
                    return source.expression.named_selects
                return ()

            for column in scope.find_all(exp.Column):
                if column.is_star:
                    continue
                name = self._name(column.this)
                if column.table:
                    owner = self._name(column.args.get("table"))
                    current = scope
                    permitted = False
                    while current is not None:
                        selected = {
                            alias: source
                            for alias, (_, source) in current.selected_sources.items()
                        }
                        if owner in selected:
                            permitted = name in source_columns(selected[owner])
                            break
                        current = current.parent
                    if not permitted:
                        raise QueryPolicyError()
                else:
                    local_columns = {
                        name
                        for _, source in scope.selected_sources.values()
                        for name in source_columns(source)
                    }
                    aliases_allowed = column.find_ancestor(exp.Order) is not None
                    if name not in local_columns and not (
                        aliases_allowed and name in scope.expression.named_selects
                    ):
                        raise QueryPolicyError()


def load_policy(session, user, ds) -> QueryPolicy:
    from sqlbot_xpack.permissions.models.ds_rules import DsRules

    from apps.datasource.crud.permission import (
        get_column_permission_fields,
        get_row_permission_filters,
    )
    from apps.datasource.models.datasource import CoreDatasource, CoreField, CoreTable
    from apps.datasource.utils.utils import aes_decrypt

    dialect = dialect_for(ds.type)
    identity = f"{user.id}:{user.oid}:{ds.id}"
    if not isinstance(ds, CoreDatasource):
        tables = {
            table.name: tuple(field.name for field in (table.fields or []))
            for table in (ds.tables or [])
        }
        return QueryPolicy(
            tables,
            dialect,
            ds.db_schema or "",
            ds.dataBase or "",
            {table.name: table.rule for table in (ds.tables or []) if table.rule},
            identity,
            {table.name: table.sql for table in (ds.tables or []) if table.sql},
        )
    if str(ds.oid) != str(user.oid):
        raise QueryPolicyError()
    tables = (
        session.query(CoreTable)
        .populate_existing()
        .filter(CoreTable.ds_id == ds.id, CoreTable.checked.is_(True))
        .order_by(CoreTable.id)
        .all()
    )
    rules = session.query(DsRules).populate_existing().all()
    allowed = {}
    for table in tables:
        columns = (
            session.query(CoreField)
            .populate_existing()
            .filter(CoreField.table_id == table.id, CoreField.checked.is_(True))
            .order_by(CoreField.field_index, CoreField.id)
            .all()
        )
        columns = get_column_permission_fields(session, user, table, columns, rules)
        if columns:
            allowed[table.table_name] = tuple(column.field_name for column in columns)
    filters = (
        get_row_permission_filters(session, user, ds, tables=list(allowed))
        if allowed
        else []
    )
    conf = (
        json.loads(aes_decrypt(ds.configuration))
        if ds.type != "excel"
        else {"dbSchema": "public"}
    )
    namespace = conf.get("dbSchema") or (
        conf.get("database")
        if dialect == "mysql"
        else "public"
        if dialect == "postgres"
        else ""
    )
    return QueryPolicy(
        allowed,
        dialect,
        namespace or "",
        conf.get("database") or "",
        {item["table"]: item["filter"] for item in filters},
        identity,
    )


def execute_query(session, user, ds, sql, *, origin_column=False):
    from apps.db.db import exec_sql

    policy = load_policy(session, user, ds)
    safe_sql = policy.protect(sql)
    result = exec_sql(ds=ds, sql=safe_sql, origin_column=origin_column)
    if load_policy(session, user, ds).fingerprint != policy.fingerprint:
        raise QueryPolicyError("scope_changed")
    result[STAMP] = policy.fingerprint
    return result


def require_record(session, user, record, ds=None):
    """Previously returned data may not be reused after access is revoked."""
    from apps.datasource.models.datasource import CoreDatasource

    if not record or str(record.create_by) != str(user.id):
        raise QueryPolicyError()
    ds = ds or session.get(CoreDatasource, record.datasource)
    if ds is None:
        # Public data/export endpoints obtain the verified assistant context
        # from middleware; background tasks pass their datasource explicitly.
        try:
            from apps.system.crud.assistant import AssistantOutDsFactory
            from apps.system.schemas.permission import RequestContext

            assistant = getattr(RequestContext.get_request().state, "assistant", None)
            if (
                assistant
                and assistant.type in (1, 3)
                and str(assistant.oid) == str(user.oid)
            ):
                ds = AssistantOutDsFactory.get_instance(assistant).get_ds(
                    record.datasource
                )
        except Exception:
            raise QueryPolicyError() from None
    if ds is None or ds.id != record.datasource:
        raise QueryPolicyError()
    policy = load_policy(session, user, ds)
    try:
        saved = json.loads(record.data or "{}")
    except (ValueError, TypeError):
        raise QueryPolicyError("scope_changed") from None
    if saved.get(STAMP) != policy.fingerprint:
        raise QueryPolicyError("scope_changed")
    return policy
