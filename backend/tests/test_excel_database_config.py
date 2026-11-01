"""Excel connections must follow the same system database as the application."""

from unittest.mock import Mock
from urllib.parse import parse_qs

import pytest
from sqlalchemy.engine import URL, make_url

from apps.db import engine as excel_engine
from common.core.config import settings


@pytest.fixture(autouse=True)
def postgres_fields(monkeypatch):
    for name, value in {
        "SQLBOT_DB_URL": "",
        "POSTGRES_SERVER": "fallback-db",
        "POSTGRES_PORT": 5544,
        "POSTGRES_USER": "fallback-user",
        "POSTGRES_PASSWORD": "fallback-test-only",
        "POSTGRES_DB": "fallback-data",
    }.items():
        monkeypatch.setattr(settings, name, value)


def test_separate_fields_remain_supported():
    conf = excel_engine.get_engine_config()
    assert (conf.host, conf.port, conf.database) == (
        "fallback-db",
        5544,
        "fallback-data",
    )
    assert (conf.username, conf.password, conf.dbSchema) == (
        "fallback-user",
        "fallback-test-only",
        "public",
    )


@pytest.mark.parametrize(
    "driver", ["postgresql+psycopg", "postgresql+psycopg2", "postgresql"]
)
def test_url_overrides_all_fallback_fields(monkeypatch, driver):
    target = URL.create(
        driver,
        username="url-user",
        password="test@:/% only",
        host="container-db",
        port=6432,
        database="url-data",
        query={"sslmode": "require", "application_name": "excel test"},
    )
    monkeypatch.setattr(
        settings, "SQLBOT_DB_URL", target.render_as_string(hide_password=False)
    )
    conf = excel_engine.get_engine_config()
    assert (conf.host, conf.port, conf.database) == ("container-db", 6432, "url-data")
    assert (conf.username, conf.password) == ("url-user", "test@:/% only")
    assert parse_qs(conf.extraJdbc)["sslmode"] == ["require"]
    assert parse_qs(conf.extraJdbc)["application_name"] == ["excel test"]
    actual = make_url(excel_engine.get_engine_uri(conf))
    assert actual.drivername == "postgresql+psycopg2"
    assert (actual.host, actual.port, actual.database, actual.password) == (
        "container-db",
        6432,
        "url-data",
        "test@:/% only",
    )
    assert actual.query["application_name"] == "excel test"


def test_url_without_port_uses_postgres_default(monkeypatch):
    monkeypatch.setattr(
        settings, "SQLBOT_DB_URL", "postgresql://test:test@container-db/imports"
    )
    assert excel_engine.get_engine_config().port == 5432


def test_ipv6_and_reserved_credentials_roundtrip(monkeypatch):
    url = URL.create(
        "postgresql+psycopg",
        username="test/user@local",
        password="test/:?@%",
        host="::1",
        port=5432,
        database="test imports",
    )
    monkeypatch.setattr(
        settings, "SQLBOT_DB_URL", url.render_as_string(hide_password=False)
    )
    actual = make_url(excel_engine.get_engine_uri(excel_engine.get_engine_config()))
    assert (actual.host, actual.username, actual.password, actual.database) == (
        "::1",
        "test/user@local",
        "test/:?@%",
        "test imports",
    )


def test_import_engine_uses_url_and_psycopg2_copy_driver(monkeypatch):
    monkeypatch.setattr(
        settings,
        "SQLBOT_DB_URL",
        "postgresql+psycopg://test:test@container-db:6543/imports?sslmode=require",
    )
    create = Mock()
    monkeypatch.setattr(excel_engine, "create_engine", create)
    excel_engine.get_engine_conn()
    url = make_url(create.call_args.args[0])
    assert (url.drivername, url.host, url.port, url.database) == (
        "postgresql+psycopg2",
        "container-db",
        6543,
        "imports",
    )
    assert url.query["sslmode"] == "require"
    assert create.call_args.kwargs["connect_args"]["connect_timeout"] == 30


def test_non_postgres_url_is_rejected_without_localhost_fallback(monkeypatch):
    monkeypatch.setattr(
        settings, "SQLBOT_DB_URL", "mysql+pymysql://test:test@container-db/imports"
    )
    with pytest.raises(ValueError, match="PostgreSQL"):
        excel_engine.get_engine_config()
