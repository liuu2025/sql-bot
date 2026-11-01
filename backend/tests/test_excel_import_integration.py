"""Opt-in real HTTP + PostgreSQL import checks, with an explicitly isolated DB."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SQLBOT_RUN_EXCEL_INTEGRATION") != "1",
    reason="Requires an explicitly isolated Excel import test database",
)


@pytest.fixture
def import_api(monkeypatch, tmp_path):
    import sqlbot_xpack  # noqa: F401
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    from starlette.exceptions import HTTPException

    from apps.datasource.api import datasource
    from apps.system.schemas.permission import RequestContextMiddleware
    from common.core.config import settings
    from common.core.db import get_session
    from common.core.response_middleware import ResponseMiddleware, exception_handler

    url = os.environ.get("SQLBOT_TEST_DATABASE_URL")
    if not url or "codex_excel_" not in (make_url(url).database or ""):
        pytest.fail("Provide a dedicated codex_excel_* test database")
    database = create_engine(url)
    monkeypatch.setattr(settings, "SQLBOT_DB_URL", url)
    # Match the failing deployment: ONLY SQLBOT_DB_URL points to the real DB.
    monkeypatch.setattr(settings, "POSTGRES_SERVER", "localhost")
    monkeypatch.setattr(datasource, "path", str(tmp_path))
    app = FastAPI()
    app.include_router(datasource.router)
    app.add_exception_handler(HTTPException, exception_handler.http_exception_handler)
    app.add_exception_handler(Exception, exception_handler.global_exception_handler)
    app.add_middleware(ResponseMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.middleware("http")
    async def identity(request, call_next):
        request.state.current_user = SimpleNamespace(
            isAdmin=True, weight=1, id=1, oid=1, language="zh-CN"
        )
        return await call_next(request)

    app.dependency_overrides[get_session] = lambda: Mock()
    monkeypatch.setattr(ResponseMiddleware, "instances", [])
    with database.connect() as connection:
        before = set(inspect(connection).get_table_names())
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield database, client
    finally:
        # The database is task-owned; remove only tables created by this test.
        with database.begin() as connection:
            for table in set(inspect(connection).get_table_names()) - before:
                assert table.startswith("excel_")
                quoted = connection.dialect.identifier_preparer.quote(table)
                connection.execute(text(f"DROP TABLE {quoted}"))
        database.dispose()


def upload(client, content):
    response = client.post(
        "/datasource/parseExcel", files={"file": ("orders.csv", content, "text/csv")}
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    return {
        "filePath": body["filePath"],
        "sheets": [
            {"sheetName": sheet["sheetName"], "fields": sheet["fields"]}
            for sheet in body["data"]
        ],
    }


def test_url_only_deployment_imports_rows_once_and_queries_same_database(import_api):
    from sqlalchemy import text

    from apps.db.engine import get_engine_conn

    database, client = import_api
    request = upload(
        client,
        b"order_id,amount,phone\nTEST-01,129.99,test-phone-01\nTEST-02,239.50,test-phone-02\n",
    )
    response = client.post("/datasource/importToDb", json=request)
    assert response.status_code == 200, response.text
    result = response.json()["data"]["sheets"][0]
    assert result["rows"] == 2
    with database.connect() as connection:
        actual = connection.execute(
            text(f'SELECT COUNT(*), SUM(amount) FROM "{result["tableName"]}"')
        ).one()
        assert actual[0] == 2  # Exactly one stored row per uploaded record.
        assert float(actual[1]) == pytest.approx(369.49)
    imported = get_engine_conn()
    try:
        with imported.connect() as connection:
            assert (
                connection.execute(
                    text(f'SELECT COUNT(*) FROM "{result["tableName"]}"')
                ).scalar_one()
                == 2
            )
    finally:
        imported.dispose()
    # Ordinary Excel datasource reads must resolve to the same container DB.
    from apps.datasource.models.datasource import CoreDatasource
    from apps.db.db import get_engine

    reader = get_engine(CoreDatasource(id=92001, type="excel"))
    try:
        with reader.connect() as connection:
            assert (
                connection.execute(
                    text(f'SELECT COUNT(*) FROM "{result["tableName"]}"')
                ).scalar_one()
                == 2
            )
    finally:
        reader.dispose()


def test_failed_second_sheet_rolls_back_first_sheet(import_api, monkeypatch):
    from sqlalchemy import inspect

    from apps.datasource.api import datasource

    database, client = import_api
    request = upload(client, b"order_id,amount\nTEST-01,129.99\n")
    request["sheets"].append(
        {"sheetName": "invalid", "fields": request["sheets"][0]["fields"]}
    )
    real_read = datasource.read_import_dataframe

    def fail_second(path, sheet_name, fields):
        if sheet_name == "invalid":
            raise ValueError("synthetic invalid second sheet")
        return real_read(path, sheet_name, fields)

    monkeypatch.setattr(datasource, "read_import_dataframe", fail_second)
    with database.connect() as connection:
        before = set(inspect(connection).get_table_names())
    response = client.post("/datasource/importToDb", json=request)
    assert response.status_code == 500, response.text
    with database.connect() as connection:
        assert set(inspect(connection).get_table_names()) == before


def test_csv_quotes_and_empty_cells_survive_single_import(import_api):
    from sqlalchemy import text

    database, client = import_api
    request = upload(
        client,
        '订单号,金额,备注\nTEST-01,10.25,"含逗号,与引号""样例"\nTEST-02,0,\n'.encode(),
    )
    response = client.post("/datasource/importToDb", json=request)
    assert response.status_code == 200, response.text
    table = response.json()["data"]["sheets"][0]["tableName"]
    with database.connect() as connection:
        rows = connection.execute(
            text(f'SELECT "订单号", "金额", "备注" FROM "{table}" ORDER BY "订单号"')
        ).all()
    assert len(rows) == 2
    assert rows[0][2] == '含逗号,与引号"样例'
    assert rows[1][1] == 0 and rows[1][2] is None
