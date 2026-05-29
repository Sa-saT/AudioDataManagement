<script setup lang="ts">
/**
 * エラー表示用の汎用ポップアップ。
 * - v-model:open で表示制御
 * - message: 主メッセージ (errorMessageJa で変換済み想定)
 * - code: 任意のエラーコード (デバッグ補助で末尾に小さく表示)
 * - icon: バリアントによる視覚 (error / warning)
 */
const props = withDefaults(defineProps<{
  open: boolean
  message: string | null
  code?: string | null
  title?: string
  variant?: 'error' | 'warning'
}>(), {
  code: null,
  title: 'エラー',
  variant: 'error',
})

const emit = defineEmits<{
  'update:open': [v: boolean]
}>()

function close() {
  emit('update:open', false)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="err-pop">
      <div
        v-if="props.open && props.message"
        class="fixed inset-0 z-[60] flex items-start justify-center bg-black/30 pt-24 backdrop-blur-sm"
        @click.self="close"
      >
        <div class="card mx-4 w-full max-w-[440px] p-6">
          <div class="mb-4 flex items-start gap-3">
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
              :class="props.variant === 'error' ? 'bg-accent/15 text-accent' : 'bg-[#f0a840]/15 text-[#b07000]'"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="13"/>
                <circle cx="12" cy="16.5" r="0.6" fill="currentColor" stroke="none"/>
              </svg>
            </div>
            <div class="min-w-0 flex-1">
              <h2 class="text-[15px] font-semibold text-ink">{{ props.title }}</h2>
              <p class="mt-1 whitespace-pre-line text-[13px] leading-relaxed text-body">{{ props.message }}</p>
              <p
                v-if="props.code"
                class="mt-2 font-mono text-[10px] uppercase tracking-widest text-muted"
              >code: {{ props.code }}</p>
            </div>
            <button
              class="shrink-0 text-muted transition-colors hover:text-ink"
              :aria-label="'閉じる'"
              @click="close"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="flex justify-end">
            <button
              class="rounded-md bg-ink px-4 py-1.5 text-[13px] font-medium text-canvas transition-colors hover:bg-primary hover:text-white"
              @click="close"
            >閉じる</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.err-pop-enter-active, .err-pop-leave-active { transition: opacity 180ms ease; }
.err-pop-enter-active > div, .err-pop-leave-active > div {
  transition: transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 180ms ease;
}
.err-pop-enter-from, .err-pop-leave-to { opacity: 0; }
.err-pop-enter-from > div { transform: translateY(-14px) scale(0.95); opacity: 0; }
.err-pop-leave-to > div { transform: translateY(-6px); opacity: 0; }
</style>
