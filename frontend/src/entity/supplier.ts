import icon_common_openai from '@/assets/model/icon_common_openai.png'

type ModelArg = { key: string; val?: string | number; type: string; range?: string }
type ModelOption = { name: string; api_domain?: string; args?: Array<ModelArg> }
type ModelConfig = {
  api_domain: string
  common_args?: Array<ModelArg>
  model_options?: Array<ModelOption>
}
type Supplier = {
  id: number
  name: string
  icon: string
  type: string
  is_private?: boolean
  model_config: Record<number, ModelConfig>
}

/**
 * 只保留一个「通用 OpenAI 兼容」供应商。
 *
 * 官方服务和中转站都按同一套 OpenAI 协议接入，区别只在服务地址与密钥；
 * 可用模型不再写死在前端，而是在表单里按「服务地址 + 密钥」实时拉取。
 * 模型参数也不在前端预设，一律沿用服务端对该模型的默认值，避免与上游
 * 的新旧字段（如 max_tokens / max_completion_tokens）冲突。
 * `supplier` 仅作为前端展示的载体，后端由 `protocol` 决定使用哪个客户端。
 */
export const GENERIC_SUPPLIER_ID = 15

export const supplierList: Array<Supplier> = [
  {
    id: GENERIC_SUPPLIER_ID,
    name: 'OpenAI 兼容服务',
    icon: icon_common_openai,
    type: 'openai',
    is_private: true,
    model_config: {
      0: {
        api_domain: '',
        model_options: [],
      },
    },
  },
]

/**
 * 历史数据的 supplier 可能是一到十三的旧供应商 id，统一回落到通用供应商，
 * 避免卡片图标/名称出现空白。
 */
export const get_supplier = (supplier_id: number) => {
  return supplierList.find((item: Supplier) => item.id === supplier_id) || supplierList[0]
}
