"""Actual SQL scope resolution and execution, without a model or private data."""

import sqlite3

import pytest

from apps.datasource.query_policy import QueryPolicy, QueryPolicyError


@pytest.fixture
def policy():
    return QueryPolicy(
        {"orders": ("id", "region", "amount"), "regions": ("id", "name")},
        dialect="sqlite",
        namespace="main",
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT phone FROM orders",
        "SELECT amount FROM orders WHERE phone = 'guess'",
        "SELECT amount FROM orders ORDER BY phone",
        "SELECT COUNT(phone) FROM orders",
        "SELECT region FROM orders GROUP BY region HAVING MIN(phone) > '0'",
        "SELECT o.id FROM orders o JOIN regions r ON o.phone = r.name",
        "SELECT id FROM orders WHERE EXISTS (SELECT 1 FROM regions r WHERE r.name = orders.phone)",
        "WITH x AS (SELECT phone FROM orders) SELECT * FROM x",
        "SELECT amount FROM orders UNION SELECT phone FROM orders",
        "WITH orders AS (SELECT phone FROM secrets) SELECT * FROM orders",
        "SELECT * FROM secrets",
        "SELECT * FROM private.orders",
        "SELECT id FROM orders; SELECT phone FROM orders",
        "DELETE FROM orders",
        "WITH changed AS (DELETE FROM orders RETURNING id) SELECT * FROM changed",
        "SELECT id INTO copied FROM orders",
        "SELECT pg_read_file('/etc/passwd') FROM orders",
        "SELECT private.some_function(amount) FROM orders",
        "SELECT orders.* || '' FROM orders",
        "SELECT region FROM orders NATURAL JOIN regions",
        "SELECT orders.id FROM orders JOIN regions USING(phone)",
        "SELECT current_user FROM orders",
        "WITH unused AS (SELECT amount AS phone FROM orders) SELECT region FROM orders GROUP BY region HAVING MIN(phone) > 0",
    ],
)
def test_guessed_or_indirect_access_is_denied(policy, sql):
    with pytest.raises(QueryPolicyError):
        policy.protect(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT region, SUM(amount) AS total FROM orders GROUP BY region",
        "SELECT o.* FROM orders o",
        "WITH x AS (SELECT region, amount FROM orders) SELECT * FROM x",
        "SELECT o.id FROM orders o JOIN regions r ON o.id = r.id",
        "SELECT id FROM orders WHERE EXISTS (SELECT 1 FROM regions r WHERE r.id = orders.id)",
        "SELECT id FROM orders UNION SELECT id FROM regions",
        "SELECT region, ROW_NUMBER() OVER (ORDER BY amount) AS ranking FROM orders",
        "SELECT COUNT(*) AS n FROM orders",
        "SELECT amount AS phone FROM orders ORDER BY phone",
        "SELECT * FROM main.orders",
    ],
)
def test_normal_reporting_queries_remain_valid(policy, sql):
    assert policy.protect(sql)


def test_star_and_cte_only_return_authorized_columns(policy):
    with sqlite3.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE orders(id INTEGER, region TEXT, amount INTEGER, phone TEXT)"
        )
        db.execute("INSERT INTO orders VALUES(1, 'east', 12, 'private-example')")
        sql = policy.protect("WITH x AS (SELECT * FROM orders) SELECT * FROM x")
        cursor = db.execute(sql)
        assert [item[0] for item in cursor.description] == ["id", "region", "amount"]
        assert cursor.fetchall() == [(1, "east", 12)]


def test_row_filter_is_deterministic_and_applies_inside_subqueries(policy):
    policy.filters = {"orders": "region = 'east'"}
    with sqlite3.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE orders(id INTEGER, region TEXT, amount INTEGER, phone TEXT)"
        )
        db.executemany(
            "INSERT INTO orders VALUES(?, ?, ?, ?)",
            [(1, "east", 10, "hidden-a"), (2, "west", 20, "hidden-b")],
        )
        result = db.execute(
            policy.protect("WITH x AS (SELECT * FROM orders) SELECT SUM(amount) FROM x")
        ).fetchone()
        assert result == (10,)


def test_fingerprint_changes_on_revocation_or_row_rule(policy):
    original = policy.fingerprint
    policy.tables["orders"] = ("id", "region")
    assert policy.fingerprint != original
    changed = policy.fingerprint
    policy.filters["orders"] = "region = 'east'"
    assert policy.fingerprint != changed


def test_quoted_postgres_columns_keep_their_identity():
    policy = QueryPolicy({"orders": ("PublicAmount",)})
    assert policy.protect('SELECT "PublicAmount" FROM orders')
    with pytest.raises(QueryPolicyError):
        policy.protect("SELECT publicamount FROM orders")


@pytest.mark.parametrize(
    "dialect,table,column,sql",
    [
        ("tsql", "Orders", "PublicAmount", "SELECT [PublicAmount] FROM [Orders]"),
        ("oracle", "ORDERS", "AMOUNT", "SELECT amount FROM orders"),
        ("mysql", "Orders", "PublicAmount", "SELECT `PublicAmount` FROM `Orders`"),
        ("clickhouse", "orders", "amount", "SELECT amount FROM orders"),
    ],
)
def test_reporting_dialects_preserve_authorized_identifiers(
    dialect, table, column, sql
):
    policy = QueryPolicy({table: (column,)}, dialect=dialect)
    assert policy.protect(sql)
    with pytest.raises(QueryPolicyError):
        policy.protect(
            sql.replace(column, "secret").replace("SELECT amount", "SELECT secret")
        )
