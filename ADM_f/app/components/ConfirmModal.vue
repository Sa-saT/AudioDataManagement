<script setup lang="ts">
/**
 * 不可逆操作 (DL など) 用の確認モーダル。
 * - v-model:open でバインド
 * - confirm slot / cancel slot で内容カスタマイズ
 * - confirmDisabled, confirmLoading props で進行中UI
 */
const props = withDefaults(defineProps<{
  open: boolean
  title?: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  confirmLoading?: boolean
  confirmDisabled?: boolean
  /** confirm 後のエラーメッセージ (表示用) */
  errorMessage?: string | null
  /** confirm ボタンの色 (default: ink → primary) */
  variant?: 'primary' | 'danger'
}>(), {
  title: '確認',
  confirmLabel: '実行',
  cancelLabel: 'キャンセル',
  confirmLoading: false,
  confirmDisabled: false,
  errorMessage: null,
  variant: 'primary',
})

const emit = defineEmits<{
  'update:open': [v: boolean]
  confirm: []
  cancel: []
}>()

function onCancel() {
  if (props.confirmLoading) return
  emit('cancel')
  emit('update:open', false)
}
function onConfirm() {
  if (props.confirmLoading || props.confirmDisabled) return
  emit('confirm')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-start justify-center bg-black/25 pt-24 backdrop-blur-sm"
        @click.self="onCancel"
      >
        <div class="card mx-4 w-full max-w-[440px] p-6">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-[16px] font-semibold text-ink">{{ title }}</h2>
            <button
              class="text-muted hover:text-ink disabled:opacity-30"
              :disabled="confirmLoading"
              @click="onCancel"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <div class="mb-4 text-[13px] text-body">
            <slot>
              <p v-if="message">{{ message }}</p>
            </slot>
          </div>

          <p
            v-if="errorMessage"
            class="mb-4 rounded-md border border-accent/40 bg-accent/5 px-3 py-2 text-[12px] text-accent"
          >{{ errorMessage }}</p>

          <div class="flex justify-end gap-2">
            <button
              class="rounded-md border border-hairline bg-white/60 px-4 py-1.5 text-[13px] text-body transition-colors hover:border-ink hover:text-ink disabled:opacity-40"
              :disabled="confirmLoading"
              @click="onCancel"
            >{{ cancelLabel }}</button>
            <button
              class="flex items-center gap-2 rounded-md px-4 py-1.5 text-[13px] font-medium text-canvas transition-colors disabled:opacity-50"
              :class="variant === 'danger' ? 'bg-accent hover:bg-accent/85' : 'bg-ink hover:bg-primary hover:text-white'"
              :disabled="confirmLoading || confirmDisabled"
              @click="onConfirm"
            >
              <svg
                v-if="confirmLoading"
                class="animate-spin"
                width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
              ><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              {{ confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-enter-active, .confirm-leave-active {
  transition: opacity 180ms ease;
}
.confirm-enter-active > div, .confirm-leave-active > div {
  transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 180ms ease;
}
.confirm-enter-from, .confirm-leave-to { opacity: 0; }
.confirm-enter-from > div { transform: translateY(-12px) scale(0.96); opacity: 0; }
.confirm-leave-to > div { transform: translateY(-6px); opacity: 0; }
</style>
