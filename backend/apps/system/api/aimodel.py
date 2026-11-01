import asyncio
import json
from typing import List, Union

from fastapi import APIRouter, Path, Query, Body
from fastapi.responses import StreamingResponse
from sqlmodel import func, select, update, delete

from apps.ai_model.model_factory import LLMConfig, LLMFactory
from apps.swagger.i18n import PLACEHOLDER_PREFIX
from apps.system.crud.aimodel_manage import (
    delete_ai_model_preset,
    get_ai_model_list_by_workspace,
    get_ai_model_preset,
    list_ai_model_presets,
    preset_name_exists,
    resolve_probe_api_key,
    save_ai_model_preset,
    to_preset_editor,
)
from apps.system.crud.upstream_model import UpstreamModelError, fetch_model_ids
from apps.system.crud.model_probe import chunk_text
from apps.system.models.system_model import AiModelDetail, AiModelWorkspaceMapping, AiModelBrief
from apps.system.schemas.ai_model_schema import (
    AiModelConfigItem,
    AiModelCreator,
    AiModelEditor,
    AiModelGridItem,
    AiModelPresetCreator,
    AiModelPresetEditor,
    AiModelProbe,
)
from apps.system.schemas.permission import SqlbotPermission, require_permissions
from common.core.deps import SessionDep, Trans, CurrentUser
from common.utils.crypto import sqlbot_decrypt
from common.utils.time import get_timestamp
from common.utils.utils import SQLBotLogUtil, prepare_model_arg

router = APIRouter(tags=["system_model"], prefix="/system/aimodel")
from common.audit.models.log_model import OperationType, OperationModules
from common.audit.schemas.logger_decorator import LogConfig, system_log


@router.post("/status", include_in_schema=False)
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def check_llm(info: AiModelCreator, trans: Trans):
    async def generate():
        try:
            additional_params = {item.key: prepare_model_arg(item.val) for item in info.config_list if
                                 item.key and item.val}
            config = LLMConfig(
                model_type="openai" if info.protocol == 1 else "vllm",
                model_name=info.base_model,
                api_key=info.api_key,
                api_base_url=info.api_domain,
                additional_params=additional_params,
            )
            llm_instance = LLMFactory.create_llm(config)
            async for chunk in llm_instance.llm.astream("1+1=?"):
                text = chunk_text(chunk)
                if text:
                    yield json.dumps({"content": text}) + "\n"

        except Exception as e:
            SQLBotLogUtil.error(f"Error checking LLM: {e}")
            error_msg = trans('i18n_llm.validate_error', msg=str(e))
            yield json.dumps({"error": error_msg}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/default", include_in_schema=False)
async def check_default(session: SessionDep, trans: Trans):
    db_model = session.exec(
        select(AiModelDetail).where(AiModelDetail.default_model == True)
    ).first()
    if not db_model:
        raise Exception(trans('i18n_llm.miss_default'))


@router.put("/default/{id}", summary=f"{PLACEHOLDER_PREFIX}system_model_default",
            description=f"{PLACEHOLDER_PREFIX}system_model_default")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(LogConfig(operation_type=OperationType.UPDATE, module=OperationModules.AI_MODEL, resource_id_expr="id"))
async def set_default(session: SessionDep, id: int = Path(description="ID")):
    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise ValueError(f"AiModelDetail with id {id} not found")
    if db_model.default_model:
        return

    try:
        session.exec(
            update(AiModelDetail).values(default_model=False)
        )
        db_model.default_model = True
        session.add(db_model)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e


@router.post("/models", include_in_schema=False)
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def fetch_available_models(
        session: SessionDep,
        trans: Trans,
        probe: AiModelProbe
):
    """按服务地址与密钥拉取上游可用模型列表，供「添加模型」时下拉选择。

    只做探测，不落库；api_key 为空时回落到 model_id 对应模型已保存的密钥，
    便于编辑既有模型时无需重新粘贴密钥。
    """
    try:
        api_key = await resolve_probe_api_key(session, probe.api_key, probe.model_id, probe.api_domain)
        models = await asyncio.to_thread(fetch_model_ids, probe.api_domain, api_key)
    except UpstreamModelError as e:
        if e.code == 'endpoint_changed':
            raise Exception(trans('i18n_llm.fetch_models_key_required'))
        if e.code == 'timeout':
            raise Exception(trans('i18n_llm.fetch_models_timeout'))
        if e.code in ('empty_domain', 'bad_domain'):
            raise Exception(trans('i18n_llm.api_domain_invalid'))
        if e.code == 'http':
            raise Exception(
                trans('i18n_llm.fetch_models_http_error', code=e.status_code, msg=e.message)
            )
        if e.code == 'format':
            raise Exception(trans('i18n_llm.fetch_models_invalid', msg=e.message))
        raise Exception(trans('i18n_llm.fetch_models_connect_error', msg=e.message))
    return {'models': models}


@router.get("/preset", response_model=List[AiModelPresetEditor],
            summary=f"{PLACEHOLDER_PREFIX}system_model_preset_grid",
            description=f"{PLACEHOLDER_PREFIX}system_model_preset_grid")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def query_presets(session: SessionDep):
    presets = list_ai_model_presets(session)
    return [await to_preset_editor(preset) for preset in presets]


@router.post("/preset", response_model=AiModelPresetEditor,
             summary=f"{PLACEHOLDER_PREFIX}system_model_preset_create",
             description=f"{PLACEHOLDER_PREFIX}system_model_preset_create")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(LogConfig(operation_type=OperationType.CREATE, module=OperationModules.AI_MODEL,
                      result_id_expr="id"))
async def add_preset(
        session: SessionDep,
        trans: Trans,
        creator: AiModelPresetCreator
):
    name = (creator.name or '').strip()
    if not name:
        raise Exception(trans('i18n_llm.preset_name_required'))
    if preset_name_exists(session, name):
        raise Exception(trans('i18n_llm.preset_name_exists', msg=name))
    creator.name = name
    preset = await save_ai_model_preset(session, creator)
    if preset is None:
        raise Exception(trans('i18n_llm.preset_not_found'))
    return await to_preset_editor(preset)


@router.put("/preset", response_model=AiModelPresetEditor,
            summary=f"{PLACEHOLDER_PREFIX}system_model_preset_update",
            description=f"{PLACEHOLDER_PREFIX}system_model_preset_update")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(LogConfig(operation_type=OperationType.UPDATE, module=OperationModules.AI_MODEL,
                      resource_id_expr="editor.id"))
async def update_preset(
        session: SessionDep,
        trans: Trans,
        editor: AiModelPresetEditor
):
    preset_id = int(editor.id)
    if get_ai_model_preset(session, preset_id) is None:
        raise Exception(trans('i18n_llm.preset_not_found'))
    name = (editor.name or '').strip()
    if not name:
        raise Exception(trans('i18n_llm.preset_name_required'))
    if preset_name_exists(session, name, exclude_id=preset_id):
        raise Exception(trans('i18n_llm.preset_name_exists', msg=name))
    editor.name = name
    preset = await save_ai_model_preset(session, editor)
    if preset is None:
        raise Exception(trans('i18n_llm.preset_not_found'))
    return await to_preset_editor(preset)


@router.delete("/preset/{id}", summary=f"{PLACEHOLDER_PREFIX}system_model_preset_del",
               description=f"{PLACEHOLDER_PREFIX}system_model_preset_del")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(LogConfig(operation_type=OperationType.DELETE, module=OperationModules.AI_MODEL,
                      resource_id_expr="id"))
async def remove_preset(
        session: SessionDep,
        trans: Trans,
        id: int = Path(description="ID")
):
    if get_ai_model_preset(session, id) is None:
        raise Exception(trans('i18n_llm.preset_not_found'))
    delete_ai_model_preset(session, id)


@router.get("", response_model=list[AiModelGridItem], summary=f"{PLACEHOLDER_PREFIX}system_model_grid",
            description=f"{PLACEHOLDER_PREFIX}system_model_grid")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def query(
        session: SessionDep,
        keyword: Union[str, None] = Query(default=None, max_length=255, description=f"{PLACEHOLDER_PREFIX}keyword")
):
    # 子查询：统计每个 model 绑定的 workspace 数量
    count_sub = (
        select(
            AiModelWorkspaceMapping.ai_model_id,
            func.count().label("ws_mapping_count")
        )
        .group_by(AiModelWorkspaceMapping.ai_model_id)
        .subquery()
    )
    statement = (
        select(
            AiModelDetail.id,
            AiModelDetail.name,
            AiModelDetail.model_type,
            AiModelDetail.base_model,
            AiModelDetail.supplier,
            AiModelDetail.protocol,
            AiModelDetail.default_model,
            func.coalesce(count_sub.c.ws_mapping_count, 0).label("ws_mapping_count"),
        )
        .outerjoin(count_sub, AiModelDetail.id == count_sub.c.ai_model_id)
    )
    if keyword is not None:
        statement = statement.where(AiModelDetail.name.like(f"%{keyword}%"))
    statement = statement.order_by(AiModelDetail.default_model.desc(), AiModelDetail.name, AiModelDetail.create_time)
    items = session.exec(statement).all()
    return items


@router.get("/{id}", response_model=AiModelEditor, summary=f"{PLACEHOLDER_PREFIX}system_model_query",
            description=f"{PLACEHOLDER_PREFIX}system_model_query")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def get_model_by_id(
        session: SessionDep,
        id: int = Path(description="ID")
):
    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise ValueError(f"AiModelDetail with id {id} not found")

    config_list: List[AiModelConfigItem] = []
    if db_model.config:
        try:
            raw = json.loads(db_model.config)
            config_list = [AiModelConfigItem(**item) for item in raw]
        except Exception:
            pass
    try:
        if db_model.api_key:
            db_model.api_key = await sqlbot_decrypt(db_model.api_key)
        if db_model.api_domain:
            db_model.api_domain = await sqlbot_decrypt(db_model.api_domain)
    except Exception:
        pass
    data = AiModelDetail.model_validate(db_model).model_dump(exclude_unset=True)
    data.pop("config", None)
    data["config_list"] = config_list
    return AiModelEditor(**data)


@router.post("", summary=f"{PLACEHOLDER_PREFIX}system_model_create",
             description=f"{PLACEHOLDER_PREFIX}system_model_create")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(LogConfig(operation_type=OperationType.CREATE, module=OperationModules.AI_MODEL, result_id_expr="id"))
async def add_model(
        session: SessionDep,
        creator: AiModelCreator
):
    data = creator.model_dump(exclude_unset=True)
    data["config"] = json.dumps([item.model_dump(exclude_unset=True) for item in creator.config_list])
    data.pop("config_list", None)
    detail = AiModelDetail.model_validate(data)
    detail.create_time = get_timestamp()
    count = session.exec(select(func.count(AiModelDetail.id))).one()
    if count == 0:
        detail.default_model = True
    session.add(detail)
    session.commit()
    return detail


@router.put("", summary=f"{PLACEHOLDER_PREFIX}system_model_update",
            description=f"{PLACEHOLDER_PREFIX}system_model_update")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(
    LogConfig(operation_type=OperationType.UPDATE, module=OperationModules.AI_MODEL, resource_id_expr="editor.id"))
async def update_model(
        session: SessionDep,
        editor: AiModelEditor
):
    id = int(editor.id)
    data = editor.model_dump(exclude_unset=True)
    data["config"] = json.dumps([item.model_dump(exclude_unset=True) for item in editor.config_list])
    data.pop("config_list", None)
    db_model = session.get(AiModelDetail, id)
    # update_data = AiModelDetail.model_validate(data)
    db_model.sqlmodel_update(data)
    session.add(db_model)
    session.commit()


@router.delete("/{id}", summary=f"{PLACEHOLDER_PREFIX}system_model_del",
               description=f"{PLACEHOLDER_PREFIX}system_model_del")
@require_permissions(permission=SqlbotPermission(role=['admin']))
@system_log(LogConfig(operation_type=OperationType.DELETE, module=OperationModules.AI_MODEL, resource_id_expr="id"))
async def delete_model(
        session: SessionDep,
        trans: Trans,
        id: int = Path(description="ID")
):
    item = session.get(AiModelDetail, id)
    if item.default_model:
        raise Exception(trans('i18n_llm.delete_default_error', key=item.name))
    session.delete(item)
    session.commit()


@router.get("/{id}/ws_mapping", response_model=List[str], summary=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping",
            description=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def get_model_ws_mapping_by_id(
        session: SessionDep,
        id: int = Path(description="ID")
):
    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise ValueError(f"AiModelDetail with id {id} not found")

    # 根据 ai_model_id 查询关联的 workspace_id 列表
    stmt = (
        select(AiModelWorkspaceMapping.workspace_id)
        .where(AiModelWorkspaceMapping.ai_model_id == id)
        .distinct()
    )
    ws_ids: List[int] = session.exec(stmt).all()

    return [str(ws_id) for ws_id in ws_ids]


@router.put("/{id}/ws_mapping", response_model=List[str], summary=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping_update",
            description=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping_update")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def update_model_ws_mapping_by_id(
        session: SessionDep,
        id: int = Path(description="ID"),
        ws_ids: List[str] = Body(description="workspace id list"),
):
    if ws_ids is None:
        ws_ids = []
    # 提前去重
    ws_ids = list({int(ws_id) for ws_id in ws_ids})

    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise ValueError(f"AiModelDetail with id {id} not found")

    # 根据 ai_model_id 更新关联的 workspace_id 列表
    # 1. 批量删除旧映射
    session.execute(
        delete(AiModelWorkspaceMapping)
        .where(AiModelWorkspaceMapping.ai_model_id == id)
    )

    # 2. 插入去重后的映射关系
    for ws_id in ws_ids:
        session.add(
            AiModelWorkspaceMapping(ai_model_id=id, workspace_id=ws_id)
        )

    session.commit()

    return [str(ws_id) for ws_id in ws_ids]


# 新增映射（在已有基础上追加）
@router.post("/{id}/ws_mapping", response_model=List[str], summary=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping_add",
             description=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping_add")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def add_model_ws_mapping_by_id(
        session: SessionDep,
        id: int = Path(description="ID"),
        ws_ids: List[str] = Body(description="workspace id list"),
):
    if ws_ids is None:
        ws_ids = []
    ws_ids = list({int(ws_id) for ws_id in ws_ids})

    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise ValueError(f"AiModelDetail with id {id} not found")

    # 查询已存在的映射，过滤掉重复的
    existing_stmt = (
        select(AiModelWorkspaceMapping.workspace_id)
        .where(
            AiModelWorkspaceMapping.ai_model_id == id,
            AiModelWorkspaceMapping.workspace_id.in_(ws_ids),
        )
    )
    existing_ws_ids = set(session.exec(existing_stmt).all())

    # 只插入不存在的映射
    new_ws_ids = [ws_id for ws_id in ws_ids if ws_id not in existing_ws_ids]
    for ws_id in new_ws_ids:
        session.add(
            AiModelWorkspaceMapping(ai_model_id=id, workspace_id=ws_id)
        )

    session.commit()

    # 返回完整的映射列表
    all_stmt = (
        select(AiModelWorkspaceMapping.workspace_id)
        .where(AiModelWorkspaceMapping.ai_model_id == id)
        .distinct()
    )
    all_ws_ids: List[int] = session.exec(all_stmt).all()

    return [str(ws_id) for ws_id in all_ws_ids]


# 删除指定映射
@router.delete("/{id}/ws_mapping", response_model=List[str],
               summary=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping_delete",
               description=f"{PLACEHOLDER_PREFIX}system_model_ws_mapping_delete")
@require_permissions(permission=SqlbotPermission(role=['admin']))
async def delete_model_ws_mapping_by_id(
        session: SessionDep,
        id: int = Path(description="ID"),
        ws_ids: List[str] = Body(description="workspace id list"),
):
    if ws_ids is None:
        ws_ids = []
    ws_ids = list({int(ws_id) for ws_id in ws_ids})

    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise ValueError(f"AiModelDetail with id {id} not found")

    # 只删除指定的映射
    if ws_ids:
        session.execute(
            delete(AiModelWorkspaceMapping)
            .where(
                AiModelWorkspaceMapping.ai_model_id == id,
                AiModelWorkspaceMapping.workspace_id.in_(ws_ids),
            )
        )

    session.commit()

    # 返回剩余的映射列表
    stmt = (
        select(AiModelWorkspaceMapping.workspace_id)
        .where(AiModelWorkspaceMapping.ai_model_id == id)
        .distinct()
    )
    remaining_ws_ids: List[int] = session.exec(stmt).all()

    return [str(ws_id) for ws_id in remaining_ws_ids]


@router.get("/list/by_ws", response_model=List[AiModelBrief], summary=f"{PLACEHOLDER_PREFIX}system_model_list_by_ws",
            description=f"{PLACEHOLDER_PREFIX}system_model_list_by_ws")
@require_permissions(permission=SqlbotPermission(role=['ws_admin']))
async def get_model_by_ws(
        session: SessionDep,
        current_user: CurrentUser
):
    return get_ai_model_list_by_workspace(session, current_user.oid, False)
