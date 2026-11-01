import { createRouter, createWebHashHistory } from 'vue-router'
import LayoutDsl from '@/components/layout/WorkspaceLayout.vue'
import SinglePage from '@/components/layout/SinglePage.vue'
const login = () => import('@/views/login/index.vue')
const chat = () => import('@/views/chat/index.vue')
const DashboardEditor = () => import('@/views/dashboard/editor/index.vue')
const DashboardPreview = () => import('@//views/dashboard/preview/SQPreviewSingle.vue')
const Dashboard = () => import('@/views/dashboard/index.vue')
const Model = () => import('@/views/system/model/Model.vue')
// import Embedded from '@/views/system/embedded/index.vue'
// import SetAssistant from '@/views/system/embedded/iframe.vue'
const SystemEmbedded = () => import('@/views/system/embedded/Page.vue')
const Variables = () => import('@/views/system/variables/index.vue')

const assistantTest = () => import('@/views/system/embedded/Test.vue')
const assistant = () => import('@/views/embedded/index.vue')
const EmbeddedPage = () => import('@/views/embedded/page.vue')
const EmbeddedCommon = () => import('@/views/embedded/common.vue')
const Member = () => import('@/views/system/member/index.vue')
const Prompt = () => import('@/views/system/prompt/index.vue')
const Audit = () => import('@/views/system/audit/index.vue')
const Appearance = () => import('@/views/system/appearance/index.vue')
const Parameter = () => import('@/views/system/parameter/index.vue')
const Authentication = () => import('@/views/system/authentication/index.vue')
const Platform = () => import('@/views/system/platform/index.vue')
const Permission = () => import('@/views/system/permission/index.vue')
const User = () => import('@/views/system/user/User.vue')
const Workspace = () => import('@/views/system/workspace/index.vue')
const Page401 = () => import('@/views/error/index.vue')
const ChatPreview = () => import('@/views/chat/preview.vue')

import { watchRouter } from './watch'

export const routes = [
  {
    path: '/login',
    name: 'login',
    component: login,
  },
  {
    path: '/chat',
    component: LayoutDsl,
    redirect: '/chat/index',
    children: [
      {
        path: 'index',
        name: 'chat',
        component: chat,
        props: (route: any) => {
          return { startChatDsId: route.query.start_chat }
        },
        meta: { titleKey: 'menu.Data Q&A', iconActive: 'chat', iconDeActive: 'noChat' },
      },
    ],
  },
  {
    path: '/dsTable',
    component: SinglePage,
    children: [
      {
        path: ':dsId/:dsName',
        name: 'dsTable',
        component: () => import('@/views/ds/TableList.vue'),
        props: true,
      },
    ],
  },
  /* {
    path: '/ds',
    component: LayoutDsl,
    name: 'ds-menu',
    redirect: '/ds/index',
    children: [
      {
        path: 'index',
        name: 'ds',
        component: Datasource,
        meta: { titleKey: 'menu.Data Connections', iconActive: 'ds', iconDeActive: 'noDs' },
      },
    ],
  }, */
  {
    path: '/dashboard',
    component: LayoutDsl,
    redirect: '/dashboard/index',
    children: [
      {
        path: 'index',
        name: 'dashboard',
        component: Dashboard,
        meta: {
          titleKey: 'dashboard.dashboard',
          iconActive: 'dashboard',
          iconDeActive: 'noDashboard',
        },
      },
    ],
  },
  {
    path: '/set',
    name: 'set',
    component: LayoutDsl,
    redirect: '/set/permission',
    meta: { titleKey: 'workspace.set', iconActive: 'set', iconDeActive: 'noSet' },
    children: [
      {
        path: '/set/member',
        name: 'member',
        component: Member,
        meta: { titleKey: 'workspace.member_management' },
      },
      {
        path: '/set/permission',
        name: 'permission',
        component: Permission,
        meta: { titleKey: 'workspace.permission_configuration' },
      },
      /* {
        path: '/set/assistant',
        name: 'setAssistant',
        component: SetAssistant,
        meta: { titleKey: 'embedded.assistant_app' },
      }, */
      {
        path: '/set/optimization',
        redirect: '/set/permission',
        meta: { titleKey: 'workspace.permission_configuration' },
      },
      {
        path: '/set/professional',
        redirect: '/set/permission',
        meta: { titleKey: 'workspace.permission_configuration' },
      },
      {
        path: '/set/training',
        redirect: '/set/permission',
        meta: { titleKey: 'workspace.permission_configuration' },
      },
      {
        path: '/set/prompt',
        name: 'prompt',
        component: Prompt,
        meta: { titleKey: 'prompt.customize_prompt_words' },
      },
    ],
  },
  {
    path: '/canvas',
    name: 'canvas',
    component: DashboardEditor,
    meta: { title: 'canvas', icon: 'dashboard' },
  },
  {
    path: '/dashboard-preview',
    name: 'preview',
    component: DashboardPreview,
    meta: { title: 'DashboardPreview', icon: 'dashboard' },
  },
  {
    path: '/system',
    name: 'system',
    component: LayoutDsl,
    redirect: '/system/model',
    meta: { hidden: true },
    children: [
      {
        path: 'user',
        name: 'user',
        component: User,
        meta: { titleKey: 'user.user_management', iconActive: 'user', iconDeActive: 'noUser' },
      },
      {
        path: 'workspace',
        name: 'workspace',
        component: Workspace,
        meta: {
          titleKey: 'user.workspace',
          iconActive: 'workspace',
          iconDeActive: 'noWorkspace',
        },
      },
      {
        path: 'model',
        name: 'model',
        component: Model,
        meta: {
          titleKey: 'workbench.model_settings',
          iconActive: 'model',
          iconDeActive: 'noModel',
        },
      },
      {
        path: 'embedded',
        name: 'embedded',
        component: SystemEmbedded,
        meta: {
          titleKey: 'embedded.embedded_management',
          iconActive: 'embedded',
          iconDeActive: 'noEmbedded',
        },
      },
      {
        path: 'setting',
        meta: { titleKey: 'system.system_settings', iconActive: 'set', iconDeActive: 'noSet' },
        redirect: 'system_/appearance',
        name: 'setting',
        children: [
          {
            path: 'appearance',
            name: 'appearance',
            component: Appearance,
            meta: { titleKey: 'system.appearance_settings' },
          },
          {
            path: 'parameter',
            name: 'parameter',
            component: Parameter,
            meta: { titleKey: 'parameter.parameter_configuration' },
          },
          {
            path: 'variables',
            name: 'variables',
            component: Variables,
            meta: { titleKey: 'variables.system_variables' },
          },
          {
            path: 'authentication',
            name: 'authentication',
            component: Authentication,
            meta: { titleKey: 'system.authentication_settings' },
          },
          {
            path: 'platform',
            name: 'platform',
            component: Platform,
            meta: { titleKey: 'platform.title' },
          },
        ],
      },
      {
        path: 'audit',
        name: 'audit',
        component: Audit,
        meta: { titleKey: 'audit.system_log', iconActive: 'log', iconDeActive: 'noLog' },
      },
    ],
  },

  {
    path: '/assistant',
    name: 'assistant',
    component: assistant,
  },
  {
    path: '/embeddedPage',
    name: 'embeddedPage',
    component: EmbeddedPage,
  },
  {
    path: '/embeddedCommon',
    name: 'embeddedCommon',
    component: EmbeddedCommon,
  },
  {
    path: '/assistantTest',
    name: 'assistantTest',
    component: assistantTest,
  },
  {
    path: '/chatPreview',
    name: 'chatPreview',
    component: ChatPreview,
  },
  {
    path: '/admin-login',
    name: 'admin-login',
    component: login,
  },
  {
    path: '/401',
    name: '401',
    hidden: true,
    meta: {},
    component: Page401,
  },
]
const router = createRouter({
  history: createWebHashHistory(),
  routes,
})
watchRouter(router)
export default router
