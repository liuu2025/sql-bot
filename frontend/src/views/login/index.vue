<template>
  <div
    v-if="showLoading"
    v-loading="true"
    :element-loading-text="t('qa.loading')"
    class="xpack-login-handler-mask"
    element-loading-background="#F5F6F7"
  ></div>

  <div
    ref="loginContainer"
    class="login-container"
    :class="{ 'hide-login-container': showLoading }"
  >
    <div v-if="showLoginImage" class="login-image-content">
      <div class="login-editorial">
        <span class="login-eyebrow">{{ t('workbench.login_eyebrow') }}</span>
        <h1>{{ t('workbench.login_title') }}</h1>
        <p>{{ t('workbench.login_desc') }}</p>
        <ol>
          <li>{{ t('workbench.login_step_1') }}</li>
          <li>{{ t('workbench.login_step_2') }}</li>
          <li>{{ t('workbench.login_step_3') }}</li>
        </ol>
        <small>{{ t('workbench.login_footer') }}</small>
      </div>
    </div>
    <div class="login-content">
      <div class="login-right">
        <div class="login-logo-icon">
          <img v-if="loginBg" height="52" :src="loginBg" alt="" />
          <el-icon v-else size="52"
            ><custom_small v-if="appearanceStore.themeColor !== 'default'"></custom_small>
            <LOGO_fold v-else></LOGO_fold
          ></el-icon>
          <span style="margin-left: 14px; font-size: 34px; font-weight: 900; color: #485559">{{
            appearanceStore.name
          }}</span>
        </div>
        <div v-if="appearanceStore.getShowSlogan" class="welcome">
          {{ appearanceStore.slogan ?? $t('common.intelligent_questioning_platform') }}
        </div>
        <div v-else class="welcome" style="height: 0"></div>
        <div class="login-form">
          <div class="default-login-tabs">
            <h2 class="title">{{ $t('common.login') }}</h2>
            <el-form
              ref="loginFormRef"
              class="form-content_error"
              :model="loginForm"
              :rules="rules"
              @keyup.enter="submitForm"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="loginForm.username"
                  clearable
                  :placeholder="$t('login.input_account')"
                  size="large"
                ></el-input>
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="loginForm.password"
                  :placeholder="$t('common.enter_your_password')"
                  type="password"
                  show-password
                  clearable
                  size="large"
                ></el-input>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" class="login-btn" @click="submitForm">{{
                  $t('common.login_')
                }}</el-button>
              </el-form-item>
            </el-form>
          </div>
          <Handler
            v-model:loading="showLoading"
            jsname="L2NvbXBvbmVudC9sb2dpbi9IYW5kbGVy"
            @switch-tab="switchTab"
          />
          <InitialPwdDialog
            v-model="initPwdDialogVisible"
            :account="loginForm.username"
            :old-pwd="loginForm.password"
            @pwd-saved="onInitPwdSaved"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useI18n } from 'vue-i18n'
import custom_small from '@/assets/svg/logo-custom_small.svg'
import LOGO_fold from '@/assets/LOGO-fold.svg'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import Handler from './xpack/Handler.vue'
import InitialPwdDialog from './InitialPwdDialog.vue'
import { toLoginSuccess } from '@/utils/utils'
import elementResizeDetectorMaker from 'element-resize-detector'

const showLoading = ref(true)
const router = useRouter()
const userStore = useUserStore()
const appearanceStore = useAppearanceStoreWithOut()
const { t } = useI18n()
const loginForm = ref({
  username: '',
  password: '',
})
const activeName = ref('simple')

// const isLdap = computed(() => activeName.value == 'ldap')

const loginBg = computed(() => {
  return appearanceStore.getLogin
})
const loginContainerWidth = ref(0)
const loginContainer = ref()
const showLoginImage = computed<boolean>(() => {
  return !(loginContainerWidth.value < 889)
})

onMounted(async () => {
  const erd = elementResizeDetectorMaker()
  erd.listenTo(loginContainer.value, () => {
    nextTick(() => {
      loginContainerWidth.value = loginContainer.value?.offsetWidth
    })
  })
})
const rules = {
  username: [{ required: true, message: t('common.your_account_email_address'), trigger: 'blur' }],
  password: [{ required: true, message: t('common.the_correct_password'), trigger: 'blur' }],
}

const loginFormRef = ref()

const submitForm = () => {
  loginFormRef.value.validate((valid: boolean) => {
    if (valid) {
      userStore.login(loginForm.value).then((res: any) => {
        if (res?.need_change_pwd) {
          initPwdDialogVisible.value = true
          return
        }
        toLoginSuccess(router)
      })
    }
  })
}
const initPwdDialogVisible = ref(false)
const onInitPwdSaved = (newPwd: string) => {
  loginForm.value.password = newPwd
}
const switchTab = (name: string) => {
  activeName.value = name || 'simple'
}
</script>

<style lang="less" scoped>
.login-container {
  height: 100vh;
  width: 100vw;
  background-color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;

  .login-image-content {
    overflow: hidden;
    height: 100%;
    width: 40%;
    min-width: 400px;
    .login-image {
      background-size: 100% 100%;
      width: 100%;
      height: 100%;
    }
  }

  .login-content {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;

    .login-right {
      display: flex;
      align-items: center;
      flex-direction: column;
      position: relative;

      .login-logo-icon {
        width: auto;
        height: 52px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .welcome {
        margin: 8px 0 40px 0;
        font-weight: 400;
        font-size: 14px;
        line-height: 20px;
        color: #646a73;
      }

      .login-form {
        border: 1px solid #dee0e3;
        padding: 40px;
        width: 480px;
        min-height: 392px;
        border-radius: 12px;
        box-shadow: 0px 6px 24px 0px #1f232914;

        .form-content_error {
          .ed-form-item--default {
            margin-bottom: 24px;
            &.is-error {
              margin-bottom: 48px;
            }
          }
        }

        .title {
          font-weight: 500;
          font-style: Medium;
          font-size: 20px;
          line-height: 28px;
          margin-bottom: 24px;
        }

        .login-btn {
          width: 100%;
          height: 40px;
          font-size: 16px;
          border-radius: 6px;
        }

        .agreement {
          margin-top: 20px;
          text-align: center;
          color: #666;
        }
      }
    }
  }
}
.hide-login-container {
  display: none;
}

.xpack-login-handler-mask {
  position: fixed;
  width: 100vw;
  height: 100vh;
  left: 0;
  top: 0;
  z-index: 999;
}
</style>

<style scoped lang="less">
.login-container .login-image-content {
  width: 49%;
  min-width: 400px;
  padding: 7%;
  display: flex;
  align-items: center;
  background: #193958;
  background-image: radial-gradient(ellipse at 100% 0%, #376685 0%, transparent 60%);
  color: #fff;
}
.login-editorial {
  width: 100%;
}
.login-eyebrow {
  color: #a3c3db;
  font-size: 12px;
  letter-spacing: 3px;
}
.login-editorial h1 {
  white-space: pre-line;
  font-size: clamp(30px, 3.3vw, 52px);
  line-height: 1.5;
  margin: 38px 0 20px;
  font-weight: 500;
  letter-spacing: 1px;
}
.login-editorial p {
  color: #9eb7ce;
  font-size: 13px;
  line-height: 2;
}
.login-editorial ol {
  list-style: none;
  counter-reset: login-step;
  padding: 36px 0 48px;
}
.login-editorial li {
  counter-increment: login-step;
  border-bottom: 1px solid #ffffff16;
  padding: 16px 0;
  color: #cbdae8;
  font-size: 12px;
}
.login-editorial li:before {
  content: '0' counter(login-step);
  font-family: monospace;
  margin-right: 20px;
  color: #7296b4;
}
.login-editorial small {
  font-size: 10px;
  color: #7e9db7;
}
.login-container .login-content .login-right .login-logo-icon {
  margin-bottom: 24px;
}
</style>
