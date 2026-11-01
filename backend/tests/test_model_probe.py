import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from apps.system.crud.model_probe import chunk_text
from apps.system.crud.upstream_model import UpstreamModelError


def test_extracts_sdk_message_chunk():
    assert chunk_text(SimpleNamespace(content="连接成功")) == "连接成功"


def test_extracts_dict_and_text_blocks():
    assert chunk_text({"content": "ok"}) == "ok"
    assert (
        chunk_text(
            SimpleNamespace(
                content=[{"type": "text", "text": "2"}, {"type": "reasoning"}]
            )
        )
        == "2"
    )


def test_ignores_empty_and_non_text_chunks():
    for chunk in (None, {}, SimpleNamespace(content=None), {"content": [None, 1]}):
        assert chunk_text(chunk) == ""


def test_probe_reuses_saved_credentials_only_for_the_same_endpoint():
    # Isolate the actual resolver body from database/SDK startup dependencies.
    source = Path(__file__).resolve().parents[1] / "apps/system/crud/aimodel_manage.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.AsyncFunctionDef)
        and item.name == "resolve_probe_api_key"
    )
    namespace = {
        "Session": object,
        "AiModelDetail": object,
        "reveal_secret": AsyncMock(side_effect=lambda value: value),
    }
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
        namespace,
    )
    resolve = namespace["resolve_probe_api_key"]
    session = Mock()
    session.get.return_value = SimpleNamespace(
        api_domain="https://first.test/v1", api_key="saved-key"
    )
    assert asyncio.run(resolve(session, None, "1", "https://first.test")) == "saved-key"
    with pytest.raises(UpstreamModelError, match="endpoint_changed"):
        asyncio.run(resolve(session, None, "1", "https://second.test"))
    assert (
        asyncio.run(resolve(session, "new-key", "1", "https://second.test"))
        == "new-key"
    )
