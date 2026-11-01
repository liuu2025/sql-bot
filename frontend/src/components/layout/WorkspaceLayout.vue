<script lang="ts" setup>
import { computed, onBeforeMount, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Menu from './Menu.vue'
import Person from './Person.vue'
import Mark from '@/assets/LOGO-fold.svg'
import { useUserStore } from '@/stores/user'
import { useEmitt } from '@/utils/useEmitt'
import { isMobile } from '@/utils/utils'
import { useMenuTitle } from './useMenuTitle'
import { useWorkbenchMotion } from '@/utils/useWorkbenchMotion'

const motionRoot = ref<HTMLElement | null>(null)
useWorkbenchMotion(motionRoot)

const router = useRouter()
const route = useRoute()
const user = useUserStore()
const getMenuTitle = useMenuTitle()
const collapse = ref(false)
const collapseCopy = ref(false)
const pageTitle = computed(() => getMenuTitle(route.meta))
let timer: ReturnType<typeof setTimeout> | undefined
function handleCollapseChange(value = true) {
  collapseCopy.value = value
  clearTimeout(timer)
  timer = setTimeout(() => {
    collapse.value = value
  }, 100)
}
useEmitt({ name: 'collapse-change', callback: handleCollapseChange })
onUnmounted(() => clearTimeout(timer))
onBeforeMount(() => {
  if (isMobile()) {
    collapse.value = true
    collapseCopy.value = true
  }
})
</script>

<template>
  <div ref="motionRoot" class="system-layout" :class="{ 'navigation-collapsed': collapse }">
    <aside class="left-side" :class="{ 'left-side-collapse': collapse }">
      <button
        class="workspace-brand"
        :title="$t('workbench.product')"
        @click="router.push('/chat/index')"
      >
        <Mark class="brand-mark" />
        <span v-if="!collapse"
          ><strong>{{ $t('workbench.product') }}</strong
          ><small>{{ $t('workbench.product_desc') }}</small></span
        >
      </button>
      <p v-if="!collapse" class="nav-caption">
        {{ $t('workbench.navigation') }}
      </p>
      <div class="navigation"><Menu :collapse="collapseCopy" /></div>
      <div class="bottom">
        <div v-if="!collapse" class="sidebar-note">
          <span class="signal-dot" />{{ $t('workbench.sidebar_note') }}
        </div>
        <div class="personal-info">
          <Person :collapse="collapse" />
          <button
            class="fold"
            :aria-label="$t(collapse ? 'workbench.expand' : 'workbench.collapse')"
            @click="handleCollapseChange(!collapse)"
          >
            {{ collapse ? '»' : '«' }}
          </button>
        </div>
      </div>
    </aside>
    <div class="right-main" :class="{ 'right-side-collapse': collapse }">
      <header class="workspace-header">
        <div class="page-heading">
          <span>{{ $t('workbench.navigation') }}</span
          ><i>/</i><strong>{{ pageTitle }}</strong>
        </div>
        <div class="header-tools">
          <button
            v-if="user.isAdmin && route.path !== '/system/model'"
            @click="router.push('/system/model')"
          >
            {{ $t('workbench.model_settings') }} <span>↗</span>
          </button>
        </div>
      </header>
      <div class="content"><router-view /></div>
    </div>
  </div>
</template>

<style lang="less" scoped>
.system-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  background: #eef2f6;
  color: #243249;
}
.left-side {
  width: 232px;
  min-width: 232px;
  display: flex;
  flex-direction: column;
  padding: 24px 16px 16px;
  background: #f8fafc;
  border-right: 1px solid #dee5ee;
}
.workspace-brand {
  display: flex;
  align-items: center;
  text-align: left;
  border: 0;
  background: none;
  cursor: pointer;
  margin-bottom: 28px;
  color: #182c48;
}
.brand-mark {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  margin-right: 10px;
}
.workspace-brand strong {
  display: block;
  font-size: 22px;
  letter-spacing: 3px;
}
.workspace-brand small {
  font-size: 10px;
  color: #748298;
  letter-spacing: 1px;
}
.nav-caption {
  font-size: 11px;
  color: #8793a5;
  letter-spacing: 2px;
  margin: 26px 8px 10px;
}
.navigation {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.bottom {
  padding-top: 16px;
}
.personal-info {
  display: flex;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid #e4eaf1;
}
.sidebar-note {
  display: flex;
  align-items: center;
  font-size: 11px;
  color: #7a879b;
  padding: 12px 6px 20px;
}
.signal-dot {
  width: 6px;
  height: 6px;
  background: #2278aa;
  border-radius: 50%;
  margin-right: 7px;
}
.workspace-link {
  width: 100%;
  padding: 10px;
  margin-bottom: 10px;
  background: #eaf0f7;
  border: 0;
  border-radius: 8px;
  color: #315079;
  cursor: pointer;
}
.fold {
  margin-left: auto;
  background: none;
  border: 0;
  border-radius: 6px;
  font-size: 22px;
  padding: 2px 8px;
  color: #687a93;
  cursor: pointer;
}
.right-main {
  flex: 1;
  width: calc(100% - 232px);
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 66px;
  padding: 0 28px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}
.page-heading {
  display: flex;
  align-items: center;
  font-size: 13px;
  gap: 14px;
}
.page-heading span {
  color: #8090a5;
}
.page-heading i {
  font-style: normal;
  color: #c0cad8;
}
.page-heading strong {
  font-weight: 600;
}
.header-tools {
  display: flex;
  align-items: center;
  gap: 14px;
}
.header-tools button {
  border: 1px solid #dce4ef;
  background: #fff;
  color: #315a86;
  border-radius: 7px;
  padding: 6px 12px;
  cursor: pointer;
}
.header-tools button span {
  margin-left: 12px;
}
.role-tag {
  font-size: 11px;
  color: #78869a;
}
.content {
  flex: 1;
  min-height: 0;
  margin: 18px;
  padding: 20px 24px 0;
  border: 1px solid #dfe6ee;
  border-radius: 12px;
  background: #fff;
  overflow: auto;
}
.content:has(.no-padding) {
  padding: 0;
}
.left-side-collapse {
  width: 68px;
  min-width: 68px;
  padding: 24px 12px 12px;
}
.left-side-collapse .brand-mark {
  margin-right: 0;
}
.left-side-collapse .personal-info {
  flex-wrap: wrap;
  gap: 12px;
}
.left-side-collapse .fold {
  margin: auto;
}
@media (max-width: 900px) {
  .workspace-header {
    padding: 0 16px;
    min-height: 56px;
  }
  .content {
    margin: 10px;
    padding: 12px;
  }
  .role-tag {
    display: none;
  }
}
@media (max-width: 600px) {
  .page-heading > span,
  .page-heading i {
    display: none;
  }
  .header-tools button {
    font-size: 11px;
    padding: 6px;
  }
  .header-tools button span {
    display: none;
  }
  .content {
    margin: 6px;
    border-radius: 8px;
  }
}
</style>
