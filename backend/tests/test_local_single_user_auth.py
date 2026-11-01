"""Offline regression tests for the local single-user session boundary.

The application imports the closed-source xpack at startup, so these tests extract
only the changed functions from the backend source and replace DB/token boundaries
with small fakes. They do not claim coverage of a running FastAPI app or proxy.
"""

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
LOGIN_PATH = ROOT / "backend/apps/system/api/login.py"
AUTH_PATH = ROOT / "backend/apps/system/middleware/auth.py"


def _nodes(path: Path):
    return ast.parse(path.read_text(encoding="utf-8")).body


def _load_functions(path: Path, names: set[str], namespace: dict):
    selected = []
    for node in _nodes(path):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node = ast.fix_missing_locations(node)
            node.decorator_list = []
            node.returns = None
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                arg.annotation = None
            if node.args.vararg:
                node.args.vararg.annotation = None
            if node.args.kwarg:
                node.args.kwarg.annotation = None
            selected.append(node)
    assert len(selected) == len(names), f"missing extracted function: {names}"
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return {name: namespace[name] for name in names}


def _load_local_functions():
    namespace = {"ipaddress": __import__("ipaddress"), "urlsplit": __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit}
    for node in _nodes(LOGIN_PATH):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"_LOCAL_IPV4_NETWORKS", "_LOCAL_IPV6_NETWORKS"}
            for target in node.targets
        ):
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(LOGIN_PATH), "exec"), namespace)
    return _load_functions(
        LOGIN_PATH,
        {"_is_local_client_ip", "_origin_tuple", "_is_same_origin_request"},
        namespace,
    )


LOCAL = _load_local_functions()


def _request(*, client_host="127.0.0.1", headers=None, port=8000):
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "server": ("127.0.0.1", port),
        "client": (client_host, 40000),
        "path": "/api/v1/login/local-access-token",
        "raw_path": b"/api/v1/login/local-access-token",
        "query_string": b"",
        "headers": raw_headers,
    }
    return Request(scope)


class _FakeSession:
    def __init__(self, user, workspace=True):
        self.user = user
        self.workspace = workspace

    def get(self, model, key):
        return object() if self.workspace and key == self.user.oid else None


def _endpoint_context(*, enabled=True, user=None, workspace=True):
    captured = {}

    def create_access_token(payload, expires_delta):
        captured["payload"] = payload
        captured["expires_delta"] = expires_delta
        return jwt.encode(
            {**payload, "exp": datetime.now(timezone.utc) + expires_delta},
            "test-local-single-user-secret-32-bytes!",
            algorithm="HS256",
        )

    settings = SimpleNamespace(
        SQLBOT_LOCAL_SINGLE_USER_MODE=enabled,
        SQLBOT_LOCAL_ACCESS_TOKEN_EXPIRE_MINUTES=60,
    )
    user = user or SimpleNamespace(
        id=1,
        account="admin",
        oid=42,
        status=1,
        origin=0,
        password="do-not-copy",
        name="Local Admin",
    )
    namespace = {
        "ipaddress": __import__("ipaddress"),
        "urlsplit": __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit,
        "timedelta": timedelta,
        "HTTPException": HTTPException,
        "Response": Response,
        "Token": SimpleNamespace,
        "settings": settings,
        "get_db_user": Mock(return_value=user),
        "create_access_token": create_access_token,
        "WorkspaceModel": object,
    }
    _load_functions(
        LOGIN_PATH,
        {"_is_local_client_ip", "_origin_tuple", "_is_same_origin_request", "local_access_token"},
        namespace,
    )
    # Constants are needed by the helper loaded above.
    for name, value in LOCAL.items():
        namespace[name] = value
    # Re-extract the endpoint after helper names are installed.
    endpoint = _load_functions(LOGIN_PATH, {"local_access_token"}, namespace)["local_access_token"]
    return endpoint, captured, _FakeSession(user, workspace), user


def _run(endpoint, request, response, session):
    return asyncio.run(endpoint(request, response, session))


@pytest.mark.parametrize(
    "address, expected",
    [
        ("127.0.0.1", True),
        ("10.20.30.40", True),
        ("172.16.0.9", True),
        ("192.168.1.9", True),
        ("::1", True),
        ("fd12:3456::9", True),
        ("::ffff:192.168.1.9", True),
        ("8.8.8.8", False),
        ("100.64.0.1", False),  # shared/special range, not RFC1918
        ("169.254.1.1", False),  # link-local is not an allowed local UI peer
        ("2001:db8::1", False),
        ("not-an-ip", False),
    ],
)
def test_local_peer_allowlist_is_explicit(address, expected):
    assert LOCAL["_is_local_client_ip"](address) is expected


def test_same_origin_browser_request_uses_origin_not_api_path():
    request = _request(
        headers={
            "Origin": "http://127.0.0.1:8000",
            "Sec-Fetch-Site": "same-origin",
        }
    )
    assert LOCAL["_is_same_origin_request"](request) is True


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
        {"Origin": "http://evil.example:8000", "Sec-Fetch-Site": "same-origin"},
        {"Origin": "http://127.0.0.1:8000/path", "Sec-Fetch-Site": "same-origin"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_origin_or_fetch_metadata_is_rejected(headers):
    assert LOCAL["_is_same_origin_request"](_request(headers=headers)) is False


def test_originless_cli_request_is_allowed():
    assert LOCAL["_is_same_origin_request"](_request()) is True


def test_mode_defaults_disabled_in_config_source():
    source = (ROOT / "backend/common/core/config.py").read_text(encoding="utf-8")
    assert "SQLBOT_LOCAL_SINGLE_USER_MODE: bool = False" in source


def test_mode_off_rejects_without_touching_account():
    endpoint, _, session, _ = _endpoint_context(enabled=False)
    response = Response()
    with pytest.raises(HTTPException) as exc:
        _run(endpoint, _request(), response, session)
    assert exc.value.status_code == 404
    session.user = None


def test_local_success_has_short_lived_marked_sanitized_token_and_no_cache():
    endpoint, captured, session, _ = _endpoint_context()
    response = Response()
    result = _run(endpoint, _request(), response, session)
    decoded = jwt.decode(
        result.access_token,
        "test-local-single-user-secret-32-bytes!",
        algorithms=["HS256"],
    )
    assert decoded["local_single_user"] is True
    assert decoded["exp"] > datetime.now(timezone.utc).timestamp()
    assert captured["expires_delta"] == timedelta(minutes=60)
    assert captured["payload"] == {
        "id": 1,
        "account": "admin",
        "oid": 42,
        "local_single_user": True,
    }
    assert "password" not in captured["payload"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


@pytest.mark.parametrize(
    "user, workspace, expected_status",
    [
        (SimpleNamespace(id=1, account="not-admin", oid=42, status=1, origin=0), True, 503),
        (SimpleNamespace(id=1, account="admin", oid=42, status=0, origin=0), True, 503),
        (SimpleNamespace(id=1, account="admin", oid=42, status=1, origin=7), True, 503),
        (SimpleNamespace(id=1, account="admin", oid=0, status=1, origin=0), True, 503),
        (SimpleNamespace(id=1, account="admin", oid=42, status=1, origin=0), False, 503),
    ],
)
def test_invalid_fixed_admin_or_workspace_is_rejected(user, workspace, expected_status):
    endpoint, _, session, _ = _endpoint_context(user=user, workspace=workspace)
    with pytest.raises(HTTPException) as exc:
        _run(endpoint, _request(), Response(), session)
    assert exc.value.status_code == expected_status


def test_public_peer_cannot_use_forwarded_private_address():
    endpoint, _, session, _ = _endpoint_context()
    request = _request(
        client_host="8.8.8.8",
        headers={"X-Forwarded-For": "127.0.0.1"},
    )
    with pytest.raises(HTTPException) as exc:
        _run(endpoint, request, Response(), session)
    assert exc.value.status_code == 403


def test_disabled_mode_rejects_already_issued_marked_token():
    source = AUTH_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "validateToken"
    )
    method.decorator_list = []
    method.returns = None
    for arg in [*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs]:
        arg.annotation = None
    class _Settings:
        SECRET_KEY = "test-local-single-user-secret-32-bytes!"
        TOKEN_KEY = "X-SQLBOT-TOKEN"
        SQLBOT_LOCAL_SINGLE_USER_MODE = False

    namespace = {
        "jwt": jwt,
        "settings": _Settings,
        "security": SimpleNamespace(ALGORITHM="HS256"),
        "TokenPayload": lambda **kwargs: kwargs,
        "get_authorization_scheme_param": lambda value: value.split(" ", 1),
        "Session": None,
        "get_user_info": None,
        "UserInfoDTO": None,
        "SQLBotLogUtil": SimpleNamespace(exception=lambda *args, **kwargs: None),
    }
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(AUTH_PATH), "exec"), namespace)
    token = jwt.encode(
        {"id": 1, "account": "admin", "oid": 42, "local_single_user": True},
        _Settings.SECRET_KEY,
        algorithm="HS256",
    )
    valid, detail = asyncio.run(
        namespace["validateToken"](None, f"Bearer {token}", lambda *args, **kwargs: "translated")
    )
    assert valid is False
    assert detail == "Local single-user mode is disabled"


def test_forwarded_headers_are_not_used_for_local_identity():
    source = LOGIN_PATH.read_text(encoding="utf-8")
    endpoint_source = ast.get_source_segment(
        source,
        next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.AsyncFunctionDef) and node.name == "local_access_token"),
    )
    assert "X-Forwarded-For" not in endpoint_source
    assert "request.client.host" in endpoint_source
