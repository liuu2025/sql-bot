<script lang="ts" setup>
import { computed } from 'vue'
import { ElMenu } from 'element-plus-secondary'
import 'element-plus-secondary/theme-chalk/el-menu.css'
import { useRoute } from 'vue-router'
import MenuItem from './MenuItem.vue'
import { useUserStore } from '@/stores/user'
const userStore = useUserStore()
defineProps({
  collapse: Boolean,
})

const route = useRoute()
const activeMenu = computed(() => route.path)
// Keep one navigation in both question and model settings pages. Backend roles
// still determine access; single-user sessions hide per-user permission assignment.
const routerList = computed(() => [
  {
    path: '/chat/index',
    meta: { titleKey: 'menu.Data Q&A', iconActive: 'chat', iconDeActive: 'noChat' },
  },
  ...(userStore.isSpaceAdmin
    ? [
        {
          path: '/ds/index',
          meta: { titleKey: 'menu.Data Connections', iconActive: 'ds', iconDeActive: 'noDs' },
        },
      ]
    : []),
  ...(userStore.isAdmin
    ? [
        {
          path: '/system/model',
          meta: {
            titleKey: 'workbench.model_settings',
            iconActive: 'model',
            iconDeActive: 'noModel',
          },
        },
      ]
    : []),
  ...(userStore.isSpaceAdmin && !userStore.isSingleUserMode
    ? [
        {
          path: '/set/permission',
          meta: {
            titleKey: 'workspace.permission_configuration',
            iconActive: 'set',
            iconDeActive: 'noSet',
          },
        },
      ]
    : []),
])
</script>

<template>
  <el-menu :default-active="activeMenu" class="el-menu-demo ed-menu-vertical" :collapse="collapse">
    <MenuItem v-for="menu in routerList" :key="menu.path" :menu="menu"></MenuItem>
  </el-menu>
</template>

<style lang="less">
.ed-menu-vertical {
  --ed-menu-item-height: 40px;
  --ed-menu-bg-color: transparent;
  --ed-menu-base-level-padding: 4px;
  border-right: none;
  .ed-menu-item {
    height: 40px !important;
    border-radius: 6px !important;
    margin-bottom: 2px;
    &.is-active {
      background-color: #fff !important;
      border-radius: 6px;
      font-weight: 500;
    }
  }

  .ed-sub-menu .ed-sub-menu__title {
    border-radius: 6px;
  }

  .ed-sub-menu.is-active:not(.is-opened) {
    .ed-sub-menu__title {
      background-color: #fff !important;
      color: var(--ed-color-primary) !important;
      font-weight: 500;
    }
  }

  .ed-sub-menu.is-active.is-opened {
    .ed-sub-menu__title {
      color: var(--ed-color-primary) !important;
      font-weight: 500;
    }
  }

  .ed-sub-menu .ed-icon {
    margin-right: 8px;
  }
}
.ed-popper.is-light:has(.ed-menu--popup) {
  border: 1px solid #dee0e3;
  border-radius: 6px;
  box-shadow: 0px 4px 8px 0px #1f23291a;
  background: #eff1f0;
  overflow: hidden;
}
.ed-menu--popup {
  padding: 8px;
  background: #eff1f0;

  .ed-menu-item {
    padding: 9px 16px;
    height: 40px !important;
    border-radius: 6px;
    &.is-active {
      background-color: #fff !important;
      font-weight: 500;
    }
  }
}
.ed-sub-menu {
  .subTitleMenu {
    display: none;
  }
}

.ed-menu--popup-container .subTitleMenu {
  color: #646a73 !important;
  pointer-events: none;
}
</style>
