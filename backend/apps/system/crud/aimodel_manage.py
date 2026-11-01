import json

from sqlmodel import Session, select, or_

from apps.system.models.system_model import (
    AiModelBrief,
    AiModelDetail,
    AiModelPreset,
    AiModelWorkspaceMapping,
)
from apps.system.schemas.ai_model_schema import (
    AiModelConfigItem,
    AiModelPresetCreator,
    AiModelPresetEditor,
)
from common.core.db import engine
from common.utils.crypto import sqlbot_decrypt, sqlbot_encrypt
from common.utils.time import get_timestamp
from common.utils.utils import SQLBotLogUtil


async def async_model_info():
    with Session(engine) as session:
        model_list = session.exec(select(AiModelDetail)).all()
        any_model_change = False
        if model_list:
            for model in model_list:
                current_model_change = False
                if model.api_domain.startswith("http"):
                    if model.api_key:
                        model.api_key = await sqlbot_encrypt(model.api_key)
                    if model.api_domain:
                        model.api_domain = await sqlbot_encrypt(model.api_domain)
                    any_model_change = True
                    current_model_change = True
                if model.supplier and model.supplier == 12:
                    model.supplier = 15
                    any_model_change = True
                    current_model_change = True
                if current_model_change:
                    session.add(model)
        if any_model_change:
            session.commit()
            SQLBotLogUtil.info("✅ 异步加密已有模型的密钥和地址完成")


def get_ai_model_list_by_workspace(session: Session, workspace_id: int, with_default: bool = True):
    sub_stmt = (
        select(AiModelWorkspaceMapping.ai_model_id)
        .where(AiModelWorkspaceMapping.workspace_id == workspace_id)
        .distinct()
    )

    # 查询：关联的模型 + default_model 为 True 的模型，默认模型排第一
    base_condition = AiModelDetail.id.in_(sub_stmt)
    if with_default:
        where_condition = or_(base_condition, AiModelDetail.default_model == True)
    else:
        where_condition = base_condition
    stmt = (
        select(
            AiModelDetail.id,
            AiModelDetail.name,
            AiModelDetail.default_model,
            AiModelDetail.supplier,
        )
        .where(where_condition)
        .order_by(AiModelDetail.default_model.desc())
    )
    rows = session.exec(stmt).all()

    return [
        AiModelBrief(
            id=row[0],
            name=row[1],
            default_model=row[2],
            supplier=row[3],
        )
        for row in rows
    ]


async def reveal_secret(value: str | None) -> str | None:
    """读取密文；历史明文数据（未加密过的行）原样返回，避免升级后不可用。"""
    if not value:
        return None
    try:
        return await sqlbot_decrypt(value)
    except Exception:
        return value


async def resolve_probe_api_key(
    session: Session, api_key: str | None, model_id: str | None, api_domain: str | None = None
) -> str | None:
    """探测模型列表时决定用哪个密钥。

    显式传入的密钥优先；否则回落到 model_id 对应模型已保存的密钥，
    这样编辑既有模型时无需重新粘贴 API Key。
    """
    if api_key:
        return api_key
    if not model_id:
        return None
    try:
        db_model = session.get(AiModelDetail, int(model_id))
    except (TypeError, ValueError):
        return None
    if not db_model or not db_model.api_key:
        return None
    if api_domain:
        from apps.system.crud.upstream_model import normalize_base_url, UpstreamModelError
        saved_domain = await reveal_secret(db_model.api_domain)
        if normalize_base_url(api_domain) != normalize_base_url(saved_domain):
            raise UpstreamModelError("endpoint_changed")
    return await reveal_secret(db_model.api_key)


def list_ai_model_presets(session: Session) -> list[AiModelPreset]:
    stmt = select(AiModelPreset).order_by(
        AiModelPreset.create_time.desc(), AiModelPreset.name
    )
    return list(session.exec(stmt).all())


def get_ai_model_preset(session: Session, preset_id: int) -> AiModelPreset | None:
    return session.get(AiModelPreset, preset_id)


def preset_name_exists(
    session: Session, name: str, exclude_id: int | None = None
) -> bool:
    stmt = select(AiModelPreset).where(AiModelPreset.name == name)
    if exclude_id is not None:
        stmt = stmt.where(AiModelPreset.id != exclude_id)
    return session.exec(stmt).first() is not None


async def save_ai_model_preset(
    session: Session, creator: AiModelPresetCreator | AiModelPresetEditor
) -> AiModelPreset:
    payload = creator.model_dump(exclude_unset=True)
    raw_config = payload.pop("config_list", None) or []
    payload["config"] = json.dumps(
        [
            item.model_dump(exclude_unset=True) if hasattr(item, "model_dump") else item
            for item in raw_config
        ]
    )

    api_domain = payload.get("api_domain") or ""
    payload["api_domain"] = await sqlbot_encrypt(api_domain)
    if payload.get("api_key"):
        payload["api_key"] = await sqlbot_encrypt(payload["api_key"])
    else:
        payload.pop("api_key", None)

    preset_id = payload.pop("id", None)
    if preset_id:
        db_preset = session.get(AiModelPreset, int(preset_id))
        if not db_preset:
            return None
        db_preset.sqlmodel_update(payload)
        session.add(db_preset)
        session.commit()
        session.refresh(db_preset)
        return db_preset

    preset = AiModelPreset(**payload)
    preset.create_time = get_timestamp()
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def delete_ai_model_preset(session: Session, preset_id: int) -> None:
    db_preset = session.get(AiModelPreset, preset_id)
    if db_preset is None:
        return
    session.delete(db_preset)
    session.commit()


async def to_preset_editor(preset: AiModelPreset) -> AiModelPresetEditor:
    config_list: list[AiModelConfigItem] = []
    if preset.config:
        try:
            config_list = [AiModelConfigItem(**item) for item in json.loads(preset.config)]
        except Exception:
            config_list = []
    return AiModelPresetEditor(
        id=preset.id,
        name=preset.name,
        supplier=preset.supplier,
        model_type=preset.model_type,
        base_model=preset.base_model,
        api_domain=await reveal_secret(preset.api_domain) or "",
        api_key=await reveal_secret(preset.api_key),
        protocol=preset.protocol,
        config_list=config_list,
    )

