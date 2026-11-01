<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { datasourceApi } from '@/api/datasource'
import { modelApi } from '@/api/system'
import { useUserStore } from '@/stores/user'

defineEmits<{ start: [] }>()
const { t } = useI18n()
const router = useRouter()
const user = useUserStore()
const sources = ref<number | null>(null)
const models = ref<number | null>(null)
const checking = ref(false)
const failed = ref(false)
async function refresh() {
  checking.value = true
  failed.value = false
  const result = await Promise.allSettled([datasourceApi.list(), modelApi.list_by_ws()])
  sources.value =
    result[0].status === 'fulfilled' && Array.isArray(result[0].value)
      ? result[0].value.length
      : null
  models.value =
    result[1].status === 'fulfilled' && Array.isArray(result[1].value)
      ? result[1].value.length
      : null
  failed.value = result.some((item) => item.status === 'rejected')
  checking.value = false
}
onMounted(refresh)
</script>

<template>
  <section class="question-workbench motion-hero">
    <div class="eyebrow"><span />{{ t('workbench.eyebrow') }}</div>
    <h1>{{ t('workbench.welcome_title') }}</h1>
    <p class="intro">{{ t('workbench.welcome_desc') }}</p>
    <div class="readiness" aria-live="polite">
      <span>{{ t('workbench.readiness') }}</span
      ><b>{{
        checking ? t('workbench.checking') : t('workbench.source_count', { count: sources ?? '—' })
      }}</b
      ><i /> <b>{{ checking ? '…' : t('workbench.model_count', { count: models ?? '—' }) }}</b
      ><button :disabled="checking" @click="refresh">{{ t('workbench.refresh') }}</button>
    </div>
    <p v-if="failed" class="status-error" role="alert">{{ t('workbench.status_error') }}</p>
    <div class="setup-grid">
      <article class="motion-card motion-enter" data-spotlight data-tilt>
        <span class="step-number">01</span>
        <h2>{{ t('workbench.source_title') }}</h2>
        <p>{{ t('workbench.source_desc') }}</p>
        <button v-if="user.isSpaceAdmin" @click="router.push('/ds/index')">
          {{ t('workbench.source_action') }} ↗</button
        ><span v-else class="step-help">{{ t('workbench.ask_space_admin') }}</span>
      </article>
      <article class="motion-card motion-enter" data-spotlight data-tilt>
        <span class="step-number">02</span>
        <h2>{{ t('workbench.model_title') }}</h2>
        <p>{{ t('workbench.model_desc') }}</p>
        <button v-if="user.isAdmin" @click="router.push('/system/model')">
          {{ t('workbench.model_action') }} ↗</button
        ><span v-else class="step-help">{{ t('workbench.ask_admin') }}</span>
      </article>
      <article class="motion-card motion-enter" data-spotlight data-tilt>
        <span class="step-number">03</span>
        <h2>{{ t('workbench.ask_title') }}</h2>
        <p>{{ t('workbench.ask_desc') }}</p>
        <button @click="$emit('start')">{{ t('workbench.ask_action') }} →</button>
      </article>
    </div>
    <div class="question-example">
      <span>{{ t('workbench.example_label') }}</span>
      <p>{{ t('workbench.example') }}</p>
    </div>
    <div class="workbench-footer">
      <p>{{ t('workbench.result_hint') }}</p>
      <el-button size="large" type="primary" class="motion-button" @click="$emit('start')"
        >{{ t('workbench.ask_action') }} <span class="start-arrow">→</span></el-button
      >
    </div>
  </section>
</template>

<style scoped lang="less">
.question-workbench {
  width: 100%;
  max-width: 940px;
  padding: 36px;
  margin: auto;
  color: #263a54;
}
.eyebrow {
  font-size: 11px;
  color: #48779f;
  letter-spacing: 2px;
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}
.eyebrow span {
  width: 22px;
  height: 3px;
  background: #2a70a9;
  margin-right: 10px;
}
h1 {
  font-size: 34px;
  letter-spacing: -1px;
  line-height: 1.4;
  font-weight: 650;
}
.intro {
  margin-top: 12px;
  font-size: 14px;
  line-height: 1.9;
  color: #7b899d;
  max-width: 560px;
}
.readiness {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
  margin: 25px 0;
  color: #6d8097;
}
.readiness > span {
  color: #93a0b0;
}
.readiness b {
  font-weight: 500;
}
.readiness i {
  width: 1px;
  height: 10px;
  background: #d9e2ed;
}
.readiness button {
  background: none;
  border: 0;
  color: #3e7aa7;
  cursor: pointer;
}
.status-error {
  color: #b46a29;
  font-size: 12px;
  margin-bottom: 14px;
}
.setup-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.setup-grid article {
  padding: 22px 20px;
  border: 1px solid #e0e7f0;
  border-radius: 10px;
  background: #fcfdff;
}
.step-number {
  color: #7297b9;
  font-size: 12px;
  font-family: monospace;
}
.setup-grid h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 16px 0 10px;
}
.setup-grid p {
  font-size: 12px;
  color: #8390a1;
  line-height: 1.9;
  min-height: 68px;
}
.setup-grid button {
  margin-top: 17px;
  padding: 0;
  color: #376f9f;
  background: none;
  border: 0;
  font-size: 12px;
  cursor: pointer;
}
.step-help {
  display: block;
  margin-top: 17px;
  font-size: 11px;
  color: #8796a9;
}
.question-example {
  margin-top: 22px;
  padding: 16px 20px;
  border-left: 3px solid #9bbcd6;
  background: #f3f7fb;
  border-radius: 0 8px 8px 0;
}
.question-example span {
  color: #8396ac;
  font-size: 10px;
}
.question-example p {
  margin-top: 6px;
  color: #496681;
  font-size: 13px;
}
.workbench-footer {
  margin-top: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
}
.workbench-footer p {
  font-size: 11px;
  color: #8a98a9;
  line-height: 1.8;
  max-width: 430px;
}
.start-arrow {
  margin-left: 24px;
}
@media (max-width: 1100px) {
  .question-workbench {
    padding: 24px;
  }
  h1 {
    font-size: 28px;
  }
  .setup-grid {
    grid-template-columns: 1fr;
  }
  .setup-grid article {
    padding: 14px 18px;
  }
  .setup-grid h2 {
    display: inline;
    margin-left: 12px;
  }
  .setup-grid p {
    min-height: auto;
    margin-top: 8px;
  }
  .setup-grid button,
  .step-help {
    margin-top: 8px;
  }
  .workbench-footer {
    flex-wrap: wrap;
  }
}
@media (max-width: 600px) {
  .question-workbench {
    padding: 18px 12px;
  }
  h1 {
    font-size: 23px;
  }
}
</style>
