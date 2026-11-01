import ipaddress
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from apps.system.schemas.logout_schema import LogoutSchema
from apps.system.schemas.system_schema import BaseUserDTO, LoginPwdEditor
from common.core.deps import SessionDep, Trans
from common.utils.crypto import sqlbot_decrypt
from ..crud.user import authenticate, check_pwd_format, clean_user_cache, get_db_user
from common.core.security import create_access_token, default_pwd, md5pwd, verify_md5pwd
from common.core.config import settings
from common.core.schemas import Token
from sqlbot_xpack.authentication.manage import logout as xpack_logout
from apps.system.crud.password_policy import initial_pwd_disabled
from apps.system.models.system_model import WorkspaceModel

from common.audit.models.log_model import OperationType, OperationModules
from common.audit.schemas.logger_decorator import system_log, LogConfig

router = APIRouter(tags=["login"], prefix="/login")


@router.post("/access-token")
@system_log(LogConfig(
    operation_type=OperationType.LOGIN,
    module=OperationModules.USER,
    result_id_expr="id"
))
async def local_login(
    session: SessionDep,
    trans: Trans,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    origin_account = await sqlbot_decrypt(form_data.username)
    origin_pwd = await sqlbot_decrypt(form_data.password)
    user: BaseUserDTO = authenticate(session=session, account=origin_account, password=origin_pwd)
    if not user:
        raise HTTPException(status_code=400, detail=trans('i18n_login.account_pwd_error'))
    if not user.oid or user.oid == 0:
        raise HTTPException(status_code=400, detail=trans('i18n_login.no_associated_ws', msg = trans('i18n_concat_admin')))
    if user.status != 1:
        raise HTTPException(status_code=400, detail=trans('i18n_login.user_disable', msg = trans('i18n_concat_admin')))
    if user.origin is not None and user.origin != 0:
        raise HTTPException(status_code=400, detail=trans('i18n_login.origin_error'))
    if (
        user.id != 1
        and await initial_pwd_disabled(session)
        and verify_md5pwd(default_pwd(), user.password)
    ):
        return Token(access_token='', need_change_pwd=True)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    user_dict = user.to_dict()
    return Token(
        access_token=create_access_token(user_dict, expires_delta=access_token_expires),
        need_change_pwd=False,
    )


_LOCAL_IPV4_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "10.0.0.0/8",       # RFC 1918
        "172.16.0.0/12",    # RFC 1918
        "192.168.0.0/16",   # RFC 1918
        "127.0.0.0/8",      # IPv4 loopback
    )
)
_LOCAL_IPV6_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "::1/128",           # IPv6 loopback
        "fc00::/7",          # IPv6 ULA (RFC 4193)
    )
)


def _is_local_client_ip(host: str | None) -> bool:
    """Allow only loopback, RFC1918, ULA, and their IPv4-mapped forms."""
    try:
        client_ip = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    if isinstance(client_ip, ipaddress.IPv6Address) and client_ip.ipv4_mapped:
        client_ip = client_ip.ipv4_mapped
    networks = (
        _LOCAL_IPV4_NETWORKS
        if isinstance(client_ip, ipaddress.IPv4Address)
        else _LOCAL_IPV6_NETWORKS
    )
    return any(client_ip in network for network in networks)


def _origin_tuple(value: str) -> tuple[str, str, int] | None:
    """Return a normalized origin tuple, rejecting userinfo and path data."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            return None
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            return None
        if parsed.query or parsed.fragment or not parsed.hostname:
            return None
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), parsed.hostname.rstrip(".").lower(), port


def _is_same_origin_request(request: Request) -> bool:
    """Allow a same-origin browser request or an Origin-less CLI request."""
    fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
    if fetch_site and fetch_site not in {"same-origin", "none"}:
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    hostname = request.url.hostname
    if hostname and ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    request_origin = _origin_tuple(
        f"{request.url.scheme}://{hostname}"
        + (f":{request.url.port}" if request.url.port else "")
    )
    return request_origin is not None and _origin_tuple(origin) == request_origin


@router.post("/local-access-token")
async def local_access_token(
    request: Request, response: Response, session: SessionDep
) -> Token:
    """Issue a short-lived admin session for the isolated single-user stack."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if not settings.SQLBOT_LOCAL_SINGLE_USER_MODE:
        raise HTTPException(status_code=404, detail="Local single-user mode is disabled")
    if not _is_same_origin_request(request):
        raise HTTPException(status_code=403, detail="Local access requires a same-origin request")
    # Deliberately use the direct peer address only. Forwarded headers are not identity.
    client_host = request.client.host if request.client else None
    if not _is_local_client_ip(client_host):
        raise HTTPException(status_code=403, detail="Local access requires a private network")

    user = get_db_user(session=session, user_id=1)
    if (
        not user
        or user.id != 1
        or user.account != "admin"
        or user.status != 1
        or user.origin not in (None, 0)
        or not user.oid
        or session.get(WorkspaceModel, user.oid) is None
    ):
        raise HTTPException(status_code=503, detail="The local admin account is unavailable")

    # Build the claim set explicitly so passwords, names, and other DB fields never
    # become token claims. TokenMiddleware uses this marker to revoke local tokens
    # when the mode is later disabled.
    token_payload = {
        "id": user.id,
        "account": user.account,
        "oid": user.oid,
        "local_single_user": True,
    }
    access_token_expires = timedelta(
        minutes=settings.SQLBOT_LOCAL_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return Token(
        access_token=create_access_token(token_payload, expires_delta=access_token_expires),
        need_change_pwd=False,
    )


@router.post("/change-pwd")
@system_log(LogConfig(
    operation_type=OperationType.UPDATE_PWD,
    module=OperationModules.USER,
    result_id_expr="id"
))
async def login_change_pwd(session: SessionDep, trans: Trans, editor: LoginPwdEditor):
    origin_account = await sqlbot_decrypt(editor.account)
    origin_pwd = await sqlbot_decrypt(editor.pwd)
    new_pwd = await sqlbot_decrypt(editor.new_pwd)
    user: BaseUserDTO = authenticate(session=session, account=origin_account, password=origin_pwd)
    if not user:
        raise HTTPException(status_code=400, detail=trans('i18n_login.account_pwd_error'))
    if user.origin is not None and user.origin != 0:
        raise HTTPException(status_code=400, detail=trans('i18n_login.origin_error'))
    if not check_pwd_format(new_pwd):
        raise HTTPException(status_code=400, detail=trans('i18n_format_invalid', key = trans('i18n_user.password')))
    if await initial_pwd_disabled(session) and new_pwd == default_pwd():
        raise HTTPException(status_code=400, detail=trans('i18n_login.new_pwd_is_initial'))
    db_user = get_db_user(session=session, user_id=user.id)
    db_user.password = md5pwd(new_pwd)
    session.add(db_user)
    await clean_user_cache(user.id)
    return db_user

@router.post("/logout")
async def logout(session: SessionDep, request: Request, dto: LogoutSchema):
    if dto.origin != 0:
        return await xpack_logout(session, request, dto)
    return None