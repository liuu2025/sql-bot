import { request } from '@/utils/request'

export const modelApi = {
  queryAll: (keyword?: string) =>
    request.get('/system/aimodel', { params: keyword ? { keyword } : {} }),
  add: (data: any) => {
    const param = { ...data }
    if (param.api_key) {
      param.api_key = LicenseGenerator.sqlbotEncrypt(data.api_key)
    }
    if (param.api_domain) {
      param.api_domain = LicenseGenerator.sqlbotEncrypt(data.api_domain)
    }
    return request.post('/system/aimodel', param)
  },
  edit: (data: any) => {
    const param = { ...data }
    if (param.api_key) {
      param.api_key = LicenseGenerator.sqlbotEncrypt(data.api_key)
    }
    if (param.api_domain) {
      param.api_domain = LicenseGenerator.sqlbotEncrypt(data.api_domain)
    }
    return request.put('/system/aimodel', param)
  },
  delete: (id: number) => request.delete(`/system/aimodel/${id}`),
  query: (id: number) => request.get(`/system/aimodel/${id}`),
  setDefault: (id: number) => request.put(`/system/aimodel/default/${id}`),
  check: (data: any, controller?: AbortController) =>
    request.fetchStream('/system/aimodel/status', data, controller),
  // 拉取上游模型列表：api_domain / api_key 保持明文，服务端只做探测不落库
  fetchModels: (data: { api_domain: string; api_key?: string; model_id?: string }) =>
    request.post('/system/aimodel/models', data),
  presetList: () => request.get('/system/aimodel/preset'),
  presetAdd: (data: any) => request.post('/system/aimodel/preset', data),
  presetEdit: (data: any) => request.put('/system/aimodel/preset', data),
  presetDelete: (id: string) => request.delete(`/system/aimodel/preset/${id}`),
  platform: (id: number, lazy?: number, pid?: string) =>
    request.post(`/system/platform/org/${id}`, { lazy, pid }),
  userSync: (data: any) => request.post(`/system/platform/user/sync`, data),
  list_by_ws: () => request.get(`/system/aimodel/list/by_ws`),
}
