"""OpenAI 兼容服务的模型列表探测。

用于「添加模型」时按用户填写的服务地址与密钥动态拉取可用模型，
避免把供应商模型清单写死在前端常量里。

设计约定：
- 只做探测，不落库；密钥由调用方以明文传入，本模块不持久化任何凭据。
- URL 归一化与响应解析拆成纯函数，便于离线单测。
- 失败统一抛 UpstreamModelError，用 code 表达失败类别，由上层映射成 locale 文案，
  不在本层拼接用户可见文案。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

DEFAULT_TIMEOUT = 15

CODE_EMPTY_DOMAIN = "empty_domain"
CODE_BAD_DOMAIN = "bad_domain"
CODE_TIMEOUT = "timeout"
CODE_CONNECT = "connect"
CODE_HTTP = "http"
CODE_FORMAT = "format"


class UpstreamModelError(Exception):
    """上游模型服务返回了不可用的结果。"""

    def __init__(
        self,
        code: str,
        message: str = "",
        status_code: int | None = None,
    ):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message
        self.status_code = status_code


def normalize_base_url(base_url: str | None) -> str:
    """归一化模型服务地址；根地址补 /v1，供应商已有路径保持原样。

    兼容根域名、/v1、自定义前缀以及末尾带斜杠的写法，
    与官方 OpenAI 兼容端点及常见中转站的约定一致。
    """
    base = (base_url or "").strip()
    if not base:
        raise UpstreamModelError(CODE_EMPTY_DOMAIN)
    parts = urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UpstreamModelError(CODE_BAD_DOMAIN)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise UpstreamModelError(CODE_BAD_DOMAIN)
    base = base.rstrip("/")
    if not parts.path.strip("/"):
        base = f"{base}/v1"
    return base


def build_models_url(base_url: str | None) -> str:
    return f"{normalize_base_url(base_url)}/models"


def parse_model_ids(payload: Any) -> list[str]:
    """从 OpenAI 兼容的 `GET /models` 响应里提取模型 id 列表。

    只接受 `{"data": [{"id": "..."}]}` 结构；其它结构抛 CODE_FORMAT，
    由上层转成「返回格式不正确」的用户提示。
    """
    if not isinstance(payload, dict):
        raise UpstreamModelError(CODE_FORMAT, "response is not a json object")
    items = payload.get("data")
    if not isinstance(items, list):
        raise UpstreamModelError(CODE_FORMAT, "response has no data list")
    model_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            model_ids.add(model_id.strip())
    return sorted(model_ids)


def fetch_model_ids(
    api_domain: str | None,
    api_key: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[str]:
    """同步请求 `{base}/models` 并返回模型 id 列表。

    同步实现配合 `asyncio.to_thread` 使用，避免在事件循环中执行外部 HTTP。
    上游返回非 200 时保留状态码与响应片段，供上层拼装用户可见提示。
    """
    url = build_models_url(api_domain)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise UpstreamModelError(CODE_TIMEOUT, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise UpstreamModelError(
            CODE_CONNECT, f"{exc.__class__.__name__}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise UpstreamModelError(
            CODE_HTTP,
            (response.text or "")[:200],
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstreamModelError(CODE_FORMAT, (response.text or "")[:200]) from exc

    return parse_model_ids(payload)
