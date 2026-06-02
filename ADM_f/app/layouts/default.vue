<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useSystemStore } from '~/stores/system'

const auth = useAuthStore()
const system = useSystemStore()

// B案: 401 SESSION_INVALIDATED でログアウトされた瞬間にポップアップ表示
function dismissSessionInvalidated() {
  auth.clearSessionInvalidatedMessage()
}

// 単一セッション制のための定期 ping (60秒に1回) + ウィンドウ復帰時の即時 ping。
// これにより、別端末で activate されてから最大 60秒以内に旧端末がログアウトされる。
let pingTimer: ReturnType<typeof setInterval> | null = null
function pingIfActivated() {
  if (auth.isActivated) void system.sessionPing()
}
function onVisibilityChange() {
  if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
    pingIfActivated()
  }
}
onMounted(() => {
  pingTimer = setInterval(pingIfActivated, 60_000)
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', pingIfActivated)
  }
})
onBeforeUnmount(() => {
  if (pingTimer) clearInterval(pingTimer)
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('focus', pingIfActivated)
  }
})
</script>

<template>
  <div class="flex h-screen flex-col overflow-hidden">
    <TopNav />

    <div class="flex-1 overflow-hidden">
      <slot />
    </div>

    <footer class="shrink-0" style="background:transparent;">
      <div class="mx-auto flex h-11 max-w-[1200px] items-center justify-center gap-6 px-6">
        <span class="text-[12px] font-semibold text-ink" style="text-shadow:0 1px 3px rgba(255,255,255,0.85);">© {{ new Date().getFullYear() }} Pathfinder</span>
        <span class="font-mono text-[11px] font-medium text-body-strong" style="text-shadow:0 1px 3px rgba(255,255,255,0.85);">v0.3.0</span>
      </div>
    </footer>

    <!-- B案: 別端末で activate された時の強制ログアウト通知 -->
    <ConfirmModal
      :open="auth.sessionInvalidatedMessage !== null"
      title="ログアウトされました"
      variant="danger"
      confirm-label="再アクティベートへ"
      cancel-label="閉じる"
      @update:open="(v) => { if (!v) dismissSessionInvalidated() }"
      @confirm="dismissSessionInvalidated"
      @cancel="dismissSessionInvalidated"
    >
      <p class="text-[13px] text-body">{{ auth.sessionInvalidatedMessage }}</p>
      <p class="mt-2 text-[11px] text-muted">
        セキュリティ上の理由により、同じ .lic ファイルでアクティベートできる端末は 1 つだけです。
        他の端末でアクティベートを行うと、それまでのセッションは自動的にログアウトされます。
      </p>
    </ConfirmModal>
  </div>
</template>
