"""Explicit disposable-PG acceptance: real routes, metadata and SQL execution."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessageChunk
from sqlalchemy import text
from sqlbot_xpack.permissions.models.ds_permission import DsPermission
from sqlmodel import Session
from test_embedding_parameters_integration import knowledge_environment, pytestmark  # noqa: F401
from test_table_parameters_integration import table_environment, task  # noqa: F401

from apps.chat.models.chat_model import ChatFinishStep
from apps.datasource.crud.datasource import get_tables_sample_data
from apps.datasource.models.datasource import (
    ColumnSchema,
    CoreDatasource,
    CoreField,
    CoreTable,
)
from apps.datasource.query_policy import QueryPolicyError, execute_query, load_policy


@pytest.fixture
def privacy_environment(table_environment, monkeypatch):  # noqa: F811
    database, client, ds_id = table_environment
    DsPermission.__table__.create(database)
    with database.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE sales_alpha(id INTEGER, region TEXT, amount INTEGER, phone TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO sales_alpha VALUES(1, 'east', 10, 'private-a'), (2, 'west', 20, 'private-b')"
            )
        )
    with Session(database) as session:
        table = (
            session.query(CoreTable).filter(CoreTable.table_name == "sales_alpha").one()
        )
        for index, name in enumerate(("region", "amount", "phone"), 2):
            session.add(
                CoreField(
                    ds_id=ds_id,
                    table_id=table.id,
                    field_name=name,
                    field_type="TEXT" if name != "amount" else "INTEGER",
                    field_index=index,
                    checked=name != "phone",
                )
            )
        session.commit()

    @contextmanager
    def business_session(_ds):
        with Session(database) as session:
            yield session

    monkeypatch.setattr("apps.db.db.get_session", business_session)
    monkeypatch.setattr("apps.system.schemas.permission.engine", database)
    # Keep audit, permissions, routers and persistence real; vector generation
    # is unrelated to this permission test and stays offline.
    monkeypatch.setattr(
        "apps.datasource.crud.datasource.run_save_table_embeddings", lambda *_a: None
    )
    monkeypatch.setattr(
        "apps.datasource.crud.datasource.run_save_ds_embeddings", lambda *_a: None
    )
    from apps.chat.api.chat import router as chat_router
    from apps.datasource.api.datasource import router as ds_router

    client.app.include_router(ds_router)
    client.app.include_router(chat_router)
    yield database, client, ds_id


class Provider:
    def __init__(self, sql):
        self.sql = sql
        self.contexts = []

    def stream(self, messages):
        context = "\n".join(message.content for message in messages)
        self.contexts.append(context)
        value = (
            json.dumps({"success": True, "sql": self.sql, "tables": ["sales_alpha"]})
            if "【Schema】" in context
            else "sales"
        )
        yield AIMessageChunk(content=value)


def ask(database, ds_id, sql):
    service = task(database, ds_id)
    service.llm = Provider(sql)
    result = list(
        service.run_task(
            in_chat=False, stream=False, finish_step=ChatFinishStep.QUERY_DATA
        )
    )[-1]
    return service, result


def test_allowed_query_runs_and_disabled_fields_never_enter_model_context(
    privacy_environment,
):
    database, _client, ds_id = privacy_environment
    service, result = ask(
        database,
        ds_id,
        "SELECT region, SUM(amount) AS total FROM sales_alpha GROUP BY region",
    )
    assert result["success"], result
    assert sorted((row["region"], row["total"]) for row in result["data"]["data"]) == [
        ("east", 10),
        ("west", 20),
    ]
    assert all(
        "phone" not in context and "private-a" not in context
        for context in service.llm.contexts
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT phone FROM sales_alpha",
        "SELECT amount FROM sales_alpha WHERE phone = 'private-a'",
        "WITH x AS (SELECT phone FROM sales_alpha) SELECT * FROM x",
        "SELECT amount FROM sales_alpha UNION SELECT phone FROM sales_alpha",
    ],
)
def test_model_guess_is_stopped_before_database_execution(
    privacy_environment, monkeypatch, sql
):
    database, _client, ds_id = privacy_environment

    def forbidden(**_kwargs):
        raise AssertionError("an unauthorized query reached the datasource")

    monkeypatch.setattr("apps.db.db.exec_sql", forbidden)
    _service, result = ask(database, ds_id, sql)
    assert not result["success"]
    assert "允许问数" in result["message"] and "private-a" not in result["message"]


def test_samples_and_star_use_the_same_column_and_row_scope(
    privacy_environment, monkeypatch
):
    database, _client, ds_id = privacy_environment
    monkeypatch.setattr(
        "apps.datasource.crud.permission.get_row_permission_filters",
        lambda *_a, **_kw: [{"table": "sales_alpha", "filter": "region = 'east'"}],
    )
    with Session(database) as session:
        ds = session.get(CoreDatasource, ds_id)
        user = SimpleNamespace(id=1, oid=1)
        result = execute_query(session, user, ds, "SELECT * FROM sales_alpha")
        assert result["fields"] == ["id", "region", "amount"]
        assert len(result["data"]) == 1 and result["data"][0]["region"] == "east"
        sample = get_tables_sample_data(session, user, ds, ["sales_alpha"])
        assert '"east"' in sample
        assert (
            "west" not in sample and "phone" not in sample and "private-" not in sample
        )


def test_admin_switch_revokes_cached_data_analysis_export_and_history(
    privacy_environment,
):
    database, client, ds_id = privacy_environment
    service, result = ask(database, ds_id, "SELECT region, amount FROM sales_alpha")
    assert result["success"], result
    record_id = service.record.id
    assert client.get(f"/chat/record/{record_id}/data").status_code == 200
    with Session(database) as session:
        field = session.query(CoreField).filter(CoreField.field_name == "amount").one()
        payload = field.model_dump()
        payload["checked"] = False
    response = client.post("/datasource/editField", json=payload)
    assert response.status_code == 200, response.text
    response = client.get(f"/chat/record/{record_id}/data")
    assert response.status_code == 400 and "重新查询" in response.text
    response = client.get(
        f"/chat/record/{record_id}/excel/export/{service.chat_question.chat_id}"
    )
    assert response.status_code == 400 and "重新查询" in response.text
    response = client.get(f"/chat/{service.chat_question.chat_id}/with_data")
    assert response.status_code == 200, response.text
    assert "east" not in response.text and "SELECT" not in response.text
    calls = len(service.llm.contexts)
    with Session(database) as session:
        with pytest.raises(QueryPolicyError):
            list(service.generate_analysis(session))
    assert len(service.llm.contexts) == calls
    with Session(database) as session:
        assert (
            "amount"
            not in load_policy(
                session,
                SimpleNamespace(id=1, oid=1),
                session.get(CoreDatasource, ds_id),
            ).tables["sales_alpha"]
        )


def test_sync_preserves_disabled_fields_and_requires_enabling_new_columns(
    privacy_environment,
):
    from apps.datasource.crud.datasource import sync_fields

    database, _client, ds_id = privacy_environment
    with Session(database) as session:
        table = (
            session.query(CoreTable).filter(CoreTable.table_name == "sales_alpha").one()
        )
        ds = session.get(CoreDatasource, ds_id)
        sync_fields(
            session,
            ds,
            table,
            [
                ColumnSchema(name, "TEXT", "")
                for name in ("id", "region", "amount", "phone", "new_secret")
            ],
        )
        fields = {
            field.field_name: field.checked
            for field in session.query(CoreField).filter(CoreField.table_id == table.id)
        }
        assert fields["amount"] and not fields["phone"] and not fields["new_secret"]


def test_user_column_rules_narrow_the_global_scope(privacy_environment):
    from sqlbot_xpack.permissions.models.ds_rules import DsRules

    database, _client, ds_id = privacy_environment
    with Session(database) as session:
        table = (
            session.query(CoreTable).filter(CoreTable.table_name == "sales_alpha").one()
        )
        field = session.query(CoreField).filter(CoreField.field_name == "amount").one()
        permission = DsPermission(
            name="hide amount",
            type="column",
            ds_id=ds_id,
            table_id=table.id,
            permissions=json.dumps([{"field_id": field.id, "enable": False}]),
            enable=True,
        )
        session.add(permission)
        session.flush()
        session.add(
            DsRules(
                oid=1,
                name="restricted",
                permission_list=[permission.id],
                user_list=[2],
                enable=True,
            )
        )
        session.commit()
        ds = session.get(CoreDatasource, ds_id)
        user = SimpleNamespace(id=2, oid=1)
        assert load_policy(session, user, ds).tables["sales_alpha"] == ("id", "region")
        with pytest.raises(QueryPolicyError):
            execute_query(session, user, ds, "SELECT amount FROM sales_alpha")
        assert execute_query(session, user, ds, "SELECT region FROM sales_alpha")[
            "data"
        ]
