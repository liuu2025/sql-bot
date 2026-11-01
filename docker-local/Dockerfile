# 数析本地隔离运行镜像，仅供本地开发和验证使用。
# 与标准部署镜像的差异：
#   1. 使用公共 python/node 基础镜像
#   2. 不内置 PostgreSQL / supervisord / g2-ssr（PG 独立容器，图片渲染服务暂不启用）
#   3. 通过 BuildKit 具名上下文传入 backend/ 与 frontend/，避免把 .git 打进构建上下文
#
# 构建示例：
#   docker build -f docker-local/Dockerfile \
#     --build-context backend=./backend --build-context frontend=./frontend \
#     -t sqlbot-local-app:dev .

ARG NODE_IMAGE=node:24.22.0-bookworm-slim
ARG PY_IMAGE=python:3.11-slim-bookworm
ARG HF_ENDPOINT=https://huggingface.co
ARG UV_DEFAULT_INDEX=https://pypi.org/simple

############################
# 1. 前端构建
############################
FROM ${NODE_IMAGE} AS fe-builder
WORKDIR /build
ENV npm_config_fund=false \
    npm_config_audit=false \
    npm_config_progress=false \
    VITE_API_BASE_URL=./api/v1 \
    VITE_APP_TITLE=数析 \
    VITE_LOCAL_SINGLE_USER_MODE=true
COPY --from=frontend . /build/
RUN npm install --no-audit --no-fund
# 上游 build script: vue-tsc -b && vite build
RUN NODE_OPTIONS=--max_old_space_size=3072 npm run build -- --mode local-single-user

############################
# 2. 后端依赖
############################
FROM ${PY_IMAGE} AS py-builder
ARG UV_DEFAULT_INDEX
ARG HF_ENDPOINT
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=180 \
    HF_ENDPOINT=${HF_ENDPOINT} \
    HF_HOME=/opt/sqlbot/models

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /opt/sqlbot/app
COPY --from=backend pyproject.toml ./

# 先只装第三方依赖（不含本项目），便于复用构建层
# --extra cpu: torch 走 pytorch-cpu 索引（pyproject 已声明 [tool.uv.sources]）
# sqlbot-xpack 由 pyproject 中声明的具名 Python 索引提供
RUN uv sync --no-install-project --extra cpu --default-index ${UV_DEFAULT_INDEX}

COPY --from=backend . /opt/sqlbot/app
RUN uv sync --extra cpu --default-index ${UV_DEFAULT_INDEX}

# 预下载嵌入模型到 LOCAL_MODEL_PATH/embedding/shibing624_text2vec-base-chinese
# （settings.LOCAL_MODEL_PATH 默认 /opt/sqlbot/models）
RUN /opt/sqlbot/app/.venv/bin/python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='shibing624/text2vec-base-chinese', \
                  local_dir='/opt/sqlbot/models/embedding/shibing624_text2vec-base-chinese', \
                  local_dir_use_symlinks=False) ; \
print('embedding model ready')"

############################
# 3. 运行时
############################
FROM ${PY_IMAGE} AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/sqlbot/app \
    PATH=/opt/sqlbot/app/.venv/bin:$PATH \
    SQLBOT_HOME=/opt/sqlbot \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=py-builder /opt/sqlbot/app /opt/sqlbot/app
# 嵌入模型必须一起进运行镜像：EmbeddingModelCache 用 LOCAL_MODEL_PATH 下的本地目录，
# 目录缺失时 HuggingFace 会把该路径当仓库名去远端下载并失败。
COPY --from=py-builder /opt/sqlbot/models /opt/sqlbot/models
COPY --from=fe-builder /build/dist /opt/sqlbot/frontend/dist
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN mkdir -p /opt/sqlbot/images /opt/sqlbot/data/excel /opt/sqlbot/data/file /opt/sqlbot/logs \
    && chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /opt/sqlbot/app
EXPOSE 8000 8001
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
    CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/',timeout=5)" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
