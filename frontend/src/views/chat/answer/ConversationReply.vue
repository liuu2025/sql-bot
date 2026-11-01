<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import MdComponent from '@/views/chat/component/MdComponent.vue'

export interface ConversationReplyData {
  kind: 'answer' | 'clarify' | 'result'
  message: string
  options?: Array<{ label: string; question: string }>
}

withDefaults(defineProps<{ reply: ConversationReplyData; canChoose?: boolean }>(), {
  canChoose: false,
})
const emits = defineEmits<{ choose: [question: string] }>()
const { t } = useI18n()
</script>

<template>
  <div class="conversation-reply" :class="reply.kind">
    <div v-if="reply.kind === 'clarify'" class="reply-title">{{ t('conversation.choose_condition') }}</div>
    <MdComponent :message="reply.message" />
    <div v-if="reply.kind === 'clarify' && reply.options?.length" class="reply-options">
      <el-button v-for="(option, index) in reply.options" :key="index" secondary
        :disabled="!canChoose" @click="emits('choose', option.question)">
        {{ option.label }}
      </el-button>
    </div>
    <p v-if="reply.kind === 'clarify'" class="reply-hint">
      {{ t(canChoose ? 'conversation.allow_input' : 'conversation.has_followup') }}
    </p>
  </div>
</template>

<style scoped lang="less">
.conversation-reply {
  padding: 16px 20px;
  margin: 8px 0;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
  &.clarify { background: #f4f8fc; border-color: #b8d0e5; }
  &.result { padding: 8px 0; border: 0; background: transparent; }
  .reply-title { margin-bottom: 10px; font-weight: 600; color: #254c73; }
  .reply-options { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;
    .ed-button { margin-left: 0; }
  }
  .reply-hint { margin: 12px 0 0; color: #6b7e90; font-size: 12px; }
}
</style>
