<script lang="ts" setup>
import { ref, computed } from 'vue'
import Default_avatar_custom from '@/assets/img/Default-avatar.svg'
import icon_key_outlined from '@/assets/svg/icon-key_outlined.svg'
import icon_logout_outlined from '@/assets/svg/icon_logout_outlined.svg'
import { useI18n } from 'vue-i18n'
import PwdForm from './PwdForm.vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { toLoginPage } from '@/utils/utils'
import { useCache } from '@/utils/useCache'

const { wsCache } = useCache()
const router = useRouter()
const userStore = useUserStore()
const pwdFormRef = ref()
const { t } = useI18n()
defineProps({
  collapse: { type: [Boolean], required: true },
  inSysmenu: { type: [Boolean], default: false },
})

const name = computed(() => (userStore.isAdmin ? t('workbench.local_account') : userStore.getName))
const account = computed(() => userStore.getAccount)
const isLocalUser = computed(() => !userStore.getOrigin)
const isSingleUserMode = computed(() => userStore.isSingleUserMode)

const isClient = computed(() => {
  return !!wsCache.get('sqlbot-platform-client')
})

const platFlag = computed(() => {
  const platformInfo = userStore.getPlatformInfo
  return platformInfo?.origin || 0
})
const dialogVisible = ref(false)
const popoverRef = ref()

const openPwd = () => {
  dialogVisible.value = true
}
const closePwd = () => {
  dialogVisible.value = false
}
const savePwdHandler = () => {
  pwdFormRef.value?.submit()
}
const logout = async () => {
  if (!(await userStore.logout())) {
    router.push(toLoginPage(router?.currentRoute?.value?.fullPath || ''))
    // router.push('/login')
  }
}
</script>

<template>
  <el-popover
    ref="popoverRef"
    trigger="click"
    popper-class="system-person"
    :placement="collapse ? 'right' : 'top-start'"
  >
    <template #reference>
      <button class="person" :title="name" :class="collapse && 'collapse'">
        <el-icon size="32">
          <Default_avatar_custom></Default_avatar_custom>
        </el-icon>
        <span v-if="!collapse" class="name ellipsis">{{ name }}</span>
      </button></template
    >
    <div class="popover">
      <div class="popover-content">
        <div class="info">
          <el-icon class="avatar-custom" size="40">
            <Default_avatar_custom></Default_avatar_custom>
          </el-icon>
          <div :title="name" class="top ellipsis">{{ name }}</div>
          <div :title="account" class="bottom ellipsis">{{ account }}</div>
        </div>
        <div v-if="!isSingleUserMode && isLocalUser && !platFlag" class="popover-item" @click="openPwd">
          <el-icon size="16">
            <icon_key_outlined></icon_key_outlined>
          </el-icon>
          <div class="datasource-name">{{ $t('user.change_password') }}</div>
        </div>
        <div style="height: 4px; width: 100%"></div>
        <div v-if="!isSingleUserMode && !isClient" class="popover-item mr4" @click="logout">
          <el-icon size="16">
            <icon_logout_outlined></icon_logout_outlined>
          </el-icon>
          <div class="datasource-name">{{ $t('common.logout') }}</div>
        </div>
      </div>
    </div>
  </el-popover>

  <el-dialog v-model="dialogVisible" :title="t('user.upgrade_pwd.title')" width="600">
    <pwd-form v-if="dialogVisible" ref="pwdFormRef" @pwd-saved="closePwd" />
    <template #footer>
      <div class="dialog-footer">
        <el-button secondary @click="closePwd">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="savePwdHandler">{{ t('common.save') }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="less" scoped>
.person {
  padding: 0 8px;
  display: flex;
  align-items: center;
  cursor: pointer;
  width: 156px;
  height: 40px;
  border: none;
  background-color: transparent;
  position: relative;

  &.collapse {
    min-width: 48px;
    margin-left: -4px;
    position: relative;
    margin-top: -6px;
    margin-bottom: 16px;

    .default-avatar {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
    }
  }

  .name {
    font-weight: 400;
    font-size: 14px;
    line-height: 22px;
    margin-left: 8px;
    max-width: 85px;
  }

  &::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 100%;
    height: 100%;
    border-radius: 6px;
  }

  &:hover,
  &:focus {
    &::after {
      background: #1f23291a;
    }
  }

  &:active {
    &::after {
      background: #1f232926;
    }
  }
}
</style>

<style lang="less">
.system-person.system-person {
  padding: 0;
  width: 200px !important;
  box-shadow: 0px 4px 8px 0px #1f23291a;
  border: 1px solid #dee0e3;
  position: relative;
  border-radius: 6px;

  &::after {
    content: '';
    position: absolute;
    bottom: 40px;
    left: 0;
    height: 1px;
    width: 100%;
    background: #dee0e3;
  }

  &::before {
    content: '';
    position: absolute;
    top: 62px;
    left: 0;
    height: 1px;
    width: 100%;
    background: #dee0e3;
  }

  .popover {
    .info {
      height: 62px;
      padding: 8px;
      margin-bottom: 4px;

      .avatar-custom {
        float: left;
        margin: 3px 8px 0 7px;
      }

      .top {
        float: left;
        font-weight: 500;
        font-size: 16px;
        line-height: 24px;
        width: calc(100% - 60px);
      }

      .bottom {
        float: left;
        font-weight: 400;
        font-size: 14px;
        line-height: 22px;
        width: calc(100% - 60px);
      }
    }
    .popover-item {
      height: 32px;
      display: flex;
      align-items: center;
      padding-left: 8px;
      padding-right: 4px;
      position: relative;
      cursor: pointer;
      margin: 0 4px;
      border-radius: 6px;
      &:hover {
        background-color: #1f23291a;
      }
      &:active {
        background-color: #1f232926;
      }
      .datasource-name {
        margin-left: 8px;
      }

      &.mr4 {
        margin: 4px;
      }

      .right {
        margin-left: auto;
      }
    }
  }
}
</style>
