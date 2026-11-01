import urllib.parse
from typing import List

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from apps.datasource.models.datasource import DatasourceConf
from common.core.config import settings
from common.utils.locale import I18n


def get_engine_config():
    # Excel import and subsequent queries must use the application's system DB.
    # A URL-only Docker deployment must never fall back to localhost defaults.
    if settings.SQLBOT_DB_URL:
        url = make_url(settings.SQLBOT_DB_URL)
        if url.get_backend_name() != "postgresql":
            raise ValueError(I18n()(lang="zh-CN")("i18n_ds_excel_requires_postgres"))
        return DatasourceConf(
            username=url.username or "", password=url.password or "",
            host=url.host or "", port=url.port or 5432, database=url.database or "",
            extraJdbc=urllib.parse.urlencode(url.query, doseq=True),
            dbSchema="public", timeout=30,
        )
    return DatasourceConf(username=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
                          host=settings.POSTGRES_SERVER, port=settings.POSTGRES_PORT, database=settings.POSTGRES_DB,
                          dbSchema="public", timeout=30) # read engine config


def get_engine_uri(conf: DatasourceConf):
    return URL.create(
        "postgresql+psycopg2", username=conf.username, password=conf.password,
        host=conf.host, port=conf.port, database=conf.database,
        query=dict(urllib.parse.parse_qsl(conf.extraJdbc, keep_blank_values=True)),
    ).render_as_string(hide_password=False)


def get_engine_conn():
    conf = get_engine_config()
    db_url = get_engine_uri(conf)
    engine = create_engine(db_url,
                           connect_args={"options": f"-c search_path={conf.dbSchema}", "connect_timeout": conf.timeout},
                           pool_timeout=conf.timeout)
    return engine


def get_data_engine():
    engine = get_engine_conn()
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session


def create_table(session, table_name: str, fields: List[any]):
    # field type relation
    list = []
    for f in fields:
        if "object" in f["type"]:
            f["relType"] = "text"
        elif "int" in f["type"]:
            f["relType"] = "bigint"
        elif "float" in f["type"]:
            f["relType"] = "numeric"
        elif "datetime" in f["type"]:
            f["relType"] = "timestamp"
        else:
            f["relType"] = "text"
        list.append(f'"{f["name"]}" {f["relType"]}')

    sql = f"""
            CREATE TABLE "{table_name}" (
                {", ".join(list)}
            );
            """
    session.execute(text(sql))
    session.commit()


def insert_data(session, table_name: str, fields: List[any], data: List[any]):
    engine = get_engine_conn()
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        stmt = table.insert().values(data)
        conn.execute(stmt)
        conn.commit()
