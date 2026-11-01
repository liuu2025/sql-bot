import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN.json'
import elementZhLocale from 'element-plus-secondary/es/locale/lang/zh-cn'

// 本项目只提供简体中文一种界面语言，不再维护多语言包与语言切换入口
export const DEFAULT_LOCALE = 'zh-CN'

const messages = {
  'zh-CN': {
    ...zhCN,
    el: elementZhLocale,
  },
}

export const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  globalInjection: true,
  messages,
})

export const getElementLocale = () => elementZhLocale
