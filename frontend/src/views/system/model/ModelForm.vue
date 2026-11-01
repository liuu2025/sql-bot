<script lang="ts" setup>
import { ref, reactive, onMounted, nextTick, computed, watch } from 'vue'
import { GENERIC_SUPPLIER_ID } from '@/entity/supplier'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus-secondary'
import { modelApi } from '@/api/system'
import { readModelProbe } from '@/utils/modelProbe'

withDefaults(
  defineProps<{
    activeName: string
    editModel: boolean
  }>(),
  {
    activeName: '',
    editModel: false,
  }
)

const { t } = useI18n()

const modelForm = reactive({
  id: '',
  supplier: GENERIC_SUPPLIER_ID,
  name: '',
  model_type: 0,
  base_model: '',
  api_key: '',
  api_domain: '',
  config_list: [],
  protocol: 1,
})

const endpointChanged = () => {
  modelForm.base_model = ''
  modelForm.api_key = ''
}

const modelRef = ref()
// 从服务地址 + 密钥动态拉取到的模型名
const remoteModelList = ref<string[]>([])
const fetchingModels = ref(false)
const fetchResult = ref('')
let modelRequest = 0
watch(
  () => [modelForm.api_domain, modelForm.api_key],
  () => {
    modelRequest += 1
    remoteModelList.value = []
    fetchResult.value = ''
  }
)
// 模型配置方案（服务地址 + 密钥 + 模型的命名快照）
const presetList = ref<any[]>([])
const presetDialogVisible = ref(false)
const presetName = ref('')
const presetSaving = ref(false)

const modelList = computed(() => remoteModelList.value.map((name) => ({ name })))

const rules = computed(() => ({
  api_domain: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('model.api_domain_name'),
      trigger: 'blur',
    },
  ],
  base_model: [{ required: true, message: t('model.the_basic_model_de'), trigger: 'change' }],
  api_key: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + 'API Key',
      trigger: 'blur',
    },
  ],
}))

const baseModelChange = () => {
  // 显示名称不再单独填写，始终跟随所选的服务端模型
  modelForm.name = modelForm.base_model
}

const initForm = (item?: any) => {
  modelForm.id = ''
  modelForm.supplier = GENERIC_SUPPLIER_ID
  modelForm.model_type = 0
  modelForm.protocol = 1
  modelForm.name = ''
  modelForm.base_model = ''
  modelForm.api_key = ''
  modelForm.api_domain = ''
  remoteModelList.value = []
  modelRef.value?.clearValidate()

  if (item) {
    Object.assign(modelForm, { ...item })
    // 显示名称不再单独维护，统一跟随服务端模型名（兼容历史自定义名称）
    modelForm.name = modelForm.base_model
  }
}

const emits = defineEmits(['submit'])

/** 按当前填写的服务地址与密钥，从服务端拉取上游可用模型 */
const fetchModels = async () => {
  if (!modelForm.api_domain) {
    ElMessage.warning(t('datasource.please_enter') + t('common.empty') + t('model.api_domain_name'))
    return
  }
  fetchingModels.value = true
  const requestId = ++modelRequest
  fetchResult.value = ''
  try {
    const res: any = await modelApi.fetchModels({
      api_domain: modelForm.api_domain,
      api_key: modelForm.api_key || undefined,
      model_id: modelForm.id || undefined,
    })
    if (requestId !== modelRequest) return
    const models: string[] = res?.models || []
    remoteModelList.value = models
    fetchResult.value = models.length
      ? t('model.fetch_models_success', { count: models.length })
      : t('workbench.model_list_empty')
    if (!models.length) {
      ElMessage.warning(t('model.fetch_models_failed'))
      return
    }
    if (!models.includes(modelForm.base_model)) {
      modelForm.base_model = models[0]
      baseModelChange()
    }
    ElMessage.success(t('model.fetch_models_success', { count: models.length }))
  } catch {
    if (requestId === modelRequest) fetchResult.value = t('workbench.fetch_failed')
  } finally {
    fetchingModels.value = false
  }
}

/** 用当前配置真实探活：复用后端 /status 的流式探测 */
const testConnection = async () => {
  if (!modelForm.api_domain || !modelForm.base_model) {
    ElMessage.warning(t('model.the_basic_model_de'))
    return
  }
  try {
    await readModelProbe(
      (controller) => modelApi.check({ ...modelForm, config_list: [] }, controller),
      {
        timeout: t('workbench.probe_timeout'),
        invalid: t('workbench.probe_invalid'),
        empty: t('workbench.probe_empty'),
      }
    )
    fetchResult.value = t('model.connection_success')
    ElMessage.success(t('model.connection_success'))
  } catch (error) {
    const detail = error instanceof Error ? error.message : t('workbench.probe_invalid')
    fetchResult.value = `${t('model.connection_failed')}：${detail}`
    ElMessage.error(fetchResult.value)
  }
}

const loadPresets = () => {
  modelApi
    .presetList()
    .then((res: any) => {
      presetList.value = res || []
    })
    .catch(() => {
      presetList.value = []
    })
}

/** 把方案里的服务地址、密钥与模型一次性回填到表单（模型参数不再保存） */
const applyPreset = (preset: any) => {
  modelForm.supplier = GENERIC_SUPPLIER_ID
  modelForm.model_type = 0
  modelForm.protocol = 1
  modelForm.base_model = preset.base_model
  modelForm.name = preset.base_model
  modelForm.api_domain = preset.api_domain
  modelForm.api_key = preset.api_key || ''
  remoteModelList.value = []
  nextTick(() => {
    modelRef.value?.clearValidate()
  })
  ElMessage.success(t('model.preset_applied', { name: preset.name }))
}

const savePreset = () => {
  if (!modelForm.api_domain || !modelForm.base_model) {
    ElMessage.warning(t('model.the_basic_model_de'))
    return
  }
  presetName.value = `${modelForm.base_model}`.trim()
  presetDialogVisible.value = true
}

const confirmSavePreset = async () => {
  const name = presetName.value.trim()
  if (!name) {
    ElMessage.warning(t('model.preset_name_required'))
    return
  }
  presetSaving.value = true
  try {
    await modelApi.presetAdd({
      name,
      supplier: GENERIC_SUPPLIER_ID,
      model_type: 0,
      base_model: modelForm.base_model,
      api_domain: modelForm.api_domain,
      api_key: modelForm.api_key || null,
      protocol: 1,
      config_list: [],
    })
    presetDialogVisible.value = false
    ElMessage.success(t('model.preset_saved'))
    loadPresets()
  } catch {
    // 失败提示由请求层统一弹出（后端返回的 locale 文案）
  } finally {
    presetSaving.value = false
  }
}

const removePreset = (preset: any) => {
  ElMessageBox.confirm(t('model.preset_delete_confirm', { name: preset.name }), {
    confirmButtonType: 'primary',
    type: 'warning',
    autofocus: false,
  })
    .then(() => {
      modelApi
        .presetDelete(preset.id)
        .then(() => {
          ElMessage.success(t('model.preset_deleted'))
          loadPresets()
        })
        .catch(() => {})
    })
    .catch(() => {})
}

const submitModel = () => {
  modelRef.value.validate((res: any) => {
    if (res) {
      emits('submit', {
        ...modelForm,
        // 显示名称固定跟随服务端模型名，兼容历史记录里自定义过的名称
        name: modelForm.base_model,
        // 模型参数交给上游默认值，不再由本系统覆盖
        config_list: [],
      })
    }
  })
}

onMounted(() => {
  setTimeout(() => {
    modelRef.value?.clearValidate()
  }, 100)
  loadPresets()
})

defineExpose({
  initForm,
  submitModel,
  testConnection,
  savePreset,
})
</script>

<template>
  <div class="model-form" :class="editModel && 'is-edit_model'">
    <div v-if="!editModel" class="model-name">{{ activeName }}</div>
    <el-scrollbar>
      <div class="form-content">
        <p class="model-form-guide">{{ t('workbench.model_form_guide') }}</p>
        <el-form
          ref="modelRef"
          :rules="rules"
          label-position="top"
          :model="modelForm"
          style="width: 100%"
          @submit.prevent
        >
          <el-form-item class="custom-require" prop="api_domain">
            <template #label>
              <span class="custom-require_danger">{{ t('model.api_domain_name') }}</span>
              <span class="enter">{{ t('model.api_domain_tip') }}</span>
            </template>
            <el-input
              v-model="modelForm.api_domain"
              @input="endpointChanged"
              clearable
              :placeholder="
                $t('datasource.please_enter') + $t('common.empty') + $t('model.api_domain_name')
              "
            />
          </el-form-item>
          <p class="model-form-guide">{{ t('workbench.local_model_hint') }}</p>
          <el-form-item prop="api_key" label="API Key">
            <el-input
              v-model="modelForm.api_key"
              @input="modelForm.base_model = ''"
              clearable
              :placeholder="$t('datasource.please_enter') + $t('common.empty') + 'API Key'"
              type="password"
              show-password
            />
          </el-form-item>
          <el-form-item class="custom-require" prop="base_model">
            <template #label>
              <span class="custom-require_danger">{{ t('model.basic_model') }}</span>
              <span class="enter">{{ t('model.enter_to_add') }}</span>
              <el-tooltip effect="dark" :content="t('model.fetch_models_tip')" placement="top">
                <el-button
                  link
                  type="primary"
                  class="fetch-models_btn"
                  :loading="fetchingModels"
                  @click="fetchModels"
                >
                  {{ t('model.fetch_models') }}
                </el-button>
              </el-tooltip>
            </template>
            <el-select
              v-model="modelForm['base_model']"
              style="width: 100%"
              filterable
              allow-create
              default-first-option
              :reserve-keyword="false"
              @change="baseModelChange"
            >
              <el-option
                v-for="item in modelList"
                :key="item.name"
                :label="item.name"
                :value="item.name"
              />
            </el-select>
          </el-form-item>
        </el-form>
        <p v-if="fetchResult" class="fetch-result" role="status">{{ fetchResult }}</p>
        <div class="preset-section">
          <div class="preset-title">{{ t('model.preset_section_title') }}</div>
          <div v-if="!presetList.length" class="preset-empty">{{ t('model.preset_empty') }}</div>
          <div
            v-for="preset in presetList"
            :key="preset.id"
            class="preset-item"
            @click="applyPreset(preset)"
          >
            <span class="preset-name ellipsis">{{ preset.name }}</span>
            <span class="preset-model ellipsis">{{ preset.base_model }}</span>
            <span class="preset-domain ellipsis">{{ preset.api_domain }}</span>
            <span class="preset-actions">
              <el-button link type="primary">{{ t('model.preset_apply') }}</el-button>
              <el-button link type="danger" @click.stop="removePreset(preset)">
                {{ $t('common.delete') }}
              </el-button>
            </span>
          </div>
        </div>
      </div>
    </el-scrollbar>
    <el-dialog
      v-model="presetDialogVisible"
      :title="t('model.save_as_preset')"
      width="420px"
      append-to-body
    >
      <el-input
        v-model="presetName"
        maxlength="100"
        :placeholder="t('model.preset_name_placeholder')"
        @keyup.enter="confirmSavePreset"
      />
      <template #footer>
        <el-button secondary @click="presetDialogVisible = false">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" :loading="presetSaving" @click="confirmSavePreset">
          {{ $t('common.save') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="less" scoped>
.model-form {
  width: calc(100% - 280px);
  position: absolute;
  right: 0;
  top: 56px;
  height: calc(100% - 120px);
  .model-name {
    height: 56px;
    width: 100%;
    padding-left: 24px;
    border-bottom: 1px solid #1f232926;
    font-weight: 500;
    font-size: 16px;
    line-height: 24px;
    display: flex;
    align-items: center;
  }
  & > .ed-scrollbar {
    .form-content {
      width: 800px;
      margin: 0 auto;
      padding-top: 24px;
      height: 100%;
      padding-bottom: 80px;

      .ed-form-item--default {
        margin-bottom: 16px;

        &.is-error {
          margin-bottom: 40px;
        }
      }

      :deep(
        .custom-require.ed-form-item.is-required:not(.is-no-asterisk).asterisk-right
          > .ed-form-item__label:after
      ) {
        display: none;
      }

      :deep(.flex-inline .ed-form-item__label) {
        display: inline-flex;
        align-items: center;
      }

      .enter {
        font-weight: 400;
        font-size: 14px;
        line-height: 22px;
        color: #ff8800;
        margin-left: 8px;
      }

      .custom-require_danger::after {
        color: var(--ed-color-danger);
        content: '*';
        margin-left: 2px;
      }

      .advance-setting {
        display: flex;
        align-items: center;
        font-weight: 500;
        font-size: 14px;
        line-height: 22px;
        cursor: pointer;

        .ed-icon {
          margin-left: 8px;
        }

        &.expand {
          .ed-icon {
            transform: rotate(180deg);
          }
        }
      }

      .model-params {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-weight: 400;
        font-size: 14px;
        line-height: 22px;
        margin: 16px 0 8px 0;

        .btn {
          height: 26px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 4px;
          border-radius: 6px;
          cursor: pointer;

          &:hover {
            background-color: #1f23291a;
          }
        }

        .ed-icon {
          margin-right: 4px;
        }
      }

      .params-table {
        border-radius: 6px;
        border: 1px solid #dee0e3;
        border-top: none;
        border-bottom: none;
        overflow-y: auto;

        &.bottom-border {
          border-bottom: 1px solid #dee0e3;
        }
        :deep(.ed-table .ed-table__cell) {
          padding: 7px 0;
        }

        :deep(.ed-table .cell) {
          line-height: 24px;
        }
      }

      .params-table_pagination {
        margin-top: 8px;

        .ed-pagination {
          justify-content: flex-end;
        }

        :deep(.ed-pager li.number:hover) {
          background-color: var(--ed-color-primary-1a, #1cba901a);
        }
      }

      .operation-column_text {
        .ed-button {
          color: #646a73;
          height: 24px;
        }
        .ed-button:not(.is-disabled):hover {
          background: #1f23291a;
        }
        .ed-button + .ed-button {
          margin-left: 8px;
        }
      }
    }
  }

  &.is-edit_model {
    width: 100%;
    .form-content {
      padding-bottom: 24px;
    }
  }
}
</style>

<style lang="less" scoped>
.fetch-models_btn {
  margin-left: 12px;
  padding: 0;
  height: auto;
}
.preset-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(31, 35, 41, 0.15);
  .preset-title {
    font-weight: 500;
    margin-bottom: 8px;
  }
  .preset-empty {
    color: #8f959e;
    font-size: 12px;
  }
  .preset-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    &:hover {
      background: rgba(51, 112, 255, 0.08);
    }
    .preset-name {
      max-width: 220px;
      font-weight: 500;
    }
    .preset-model,
    .preset-domain {
      max-width: 260px;
      color: #8f959e;
      font-size: 12px;
    }
    .preset-actions {
      margin-left: auto;
      display: flex;
      align-items: center;
    }
  }
}
</style>
