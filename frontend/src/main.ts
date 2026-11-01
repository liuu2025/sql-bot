import 'core-js/features/object/has-own'
// @ts-ignore: css-has-pseudo/browser lacks official type definitions
import cssHasPseudo from 'css-has-pseudo/browser'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
// ElMessageBox / ElLoading 只以 JS API 调用，从未出现在任何模板里，
// unplugin-vue-components 的按需解析因此不会引入它们的样式，
// 导致确认弹窗背景透明、遮罩层缺失、加载遮罩无样式。这里显式补齐。
// 必须放在 style.less 之前，让项目自己的 .confirm-no_icon 等覆盖生效。
import 'element-plus-secondary/theme-chalk/el-message-box.css'
import 'element-plus-secondary/theme-chalk/el-loading.css'
import './style.less'
import './workspace.less'
import './motion.less'
import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import VueDOMPurifyHTML from 'vue-dompurify-html'
import { isSupportFlexGap } from './utils/utils'

// import 'element-plus/dist/index.css'

cssHasPseudo(document)

isSupportFlexGap()

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(i18n)
app.use(VueDOMPurifyHTML)
app.mount('#app')
