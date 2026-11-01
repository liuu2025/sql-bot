#!/bin/sh
set -e

APP_DIR=/opt/sqlbot/app
cd "$APP_DIR"

echo "[entrypoint] waiting for database ..."
python3 - <<'PY'
import os, sys, time
import psycopg

dsn = os.environ.get("SQLBOT_DB_URL", "")
# SQLAlchemy 风格前缀 -> libpq 可识别形式
dsn = dsn.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
if not dsn:
    host = os.environ.get("POSTGRES_SERVER", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "root")
    pwd = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "sqlbot")
    from urllib.parse import quote
    dsn = f"postgresql://{quote(user)}:{quote(pwd)}@{host}:{port}/{db}"

deadline = time.time() + 180
while True:
    try:
        with psycopg.connect(dsn, connect_timeout=5):
            print("[entrypoint] database is ready")
            break
    except Exception as exc:
        if time.time() > deadline:
            print(f"[entrypoint] database not ready: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(3)
PY

# MCP 服务（main:mcp_app, 8001）：导入同一 main 模块，不重复执行 alembic 迁移
if [ "${SQLBOT_ENABLE_MCP:-true}" = "true" ]; then
  echo "[entrypoint] starting MCP server on :8001"
  uvicorn main:mcp_app --host 0.0.0.0 --port 8001 \
      --proxy-headers --forwarded-allow-ips='*' &
fi

echo "[entrypoint] starting web/api server on :8000 (cwd=$APP_DIR)"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 \
    --proxy-headers --forwarded-allow-ips='*'
