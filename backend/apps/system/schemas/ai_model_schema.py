
from typing import List, Optional
from pydantic import BaseModel, Field

from apps.swagger.i18n import PLACEHOLDER_PREFIX
from common.core.schemas import BaseCreatorDTO

class AiModelItem(BaseModel):
    name: str = Field(description=f"{PLACEHOLDER_PREFIX}model_name")
    model_type: int = Field(description=f"{PLACEHOLDER_PREFIX}model_type")
    base_model: str = Field(description=f"{PLACEHOLDER_PREFIX}base_model")
    supplier: int = Field(description=f"{PLACEHOLDER_PREFIX}supplier")
    protocol: int = Field(description=f"{PLACEHOLDER_PREFIX}protocol")
    default_model: bool = Field(default=False, description=f"{PLACEHOLDER_PREFIX}default_model")

class AiModelGridItem(AiModelItem, BaseCreatorDTO):
    ws_mapping_count: int = Field(default=0, description="workspace mapping count")

class AiModelConfigItem(BaseModel):
    key: str = Field(description=f"{PLACEHOLDER_PREFIX}arg_name")
    val: object = Field(description=f"{PLACEHOLDER_PREFIX}arg_val")
    name: str = Field(description=f"{PLACEHOLDER_PREFIX}arg_show_name")
    
class AiModelCreator(AiModelItem):
    api_domain: str = Field(description=f"{PLACEHOLDER_PREFIX}api_domain")
    api_key: str = Field(description=f"{PLACEHOLDER_PREFIX}api_key")
    config_list: List[AiModelConfigItem] = Field(description=f"{PLACEHOLDER_PREFIX}config_list")
    
class AiModelEditor(AiModelCreator, BaseCreatorDTO):
    pass

class AiModelProbe(BaseModel):
    """按服务地址与密钥探测可用模型列表的入参。

    只用于探测，不持久化 api_key；api_key 允许为空，
    此时由服务端回落到 model_id 对应模型已保存的密钥。
    """

    api_domain: str = Field(description=f"{PLACEHOLDER_PREFIX}api_domain")
    api_key: Optional[str] = Field(default=None, description=f"{PLACEHOLDER_PREFIX}api_key")
    model_id: Optional[str] = Field(default=None, description=f"{PLACEHOLDER_PREFIX}model_id")

class AiModelPresetItem(BaseModel):
    name: str = Field(description=f"{PLACEHOLDER_PREFIX}preset_name")
    supplier: int = Field(description=f"{PLACEHOLDER_PREFIX}supplier")
    model_type: int = Field(default=0, description=f"{PLACEHOLDER_PREFIX}model_type")
    base_model: str = Field(description=f"{PLACEHOLDER_PREFIX}base_model")
    api_domain: str = Field(description=f"{PLACEHOLDER_PREFIX}api_domain")
    api_key: Optional[str] = Field(default=None, description=f"{PLACEHOLDER_PREFIX}api_key")
    protocol: int = Field(default=1, description=f"{PLACEHOLDER_PREFIX}protocol")
    config_list: List[AiModelConfigItem] = Field(
        default_factory=list, description=f"{PLACEHOLDER_PREFIX}config_list"
    )

class AiModelPresetCreator(AiModelPresetItem):
    pass

class AiModelPresetEditor(AiModelPresetCreator, BaseCreatorDTO):
    pass
