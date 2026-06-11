<script setup lang="ts">
// アプリ起動時のスプラッシュ。セッション初回のみ、約 1.5s で消える。
// Ken Burns 微ズーム + 中央ロゴ + ヴィネット + クリック/ESC で skip。
// prefers-reduced-motion: reduce のときは即スキップ。

const SESSION_KEY = 'pathfinder.splashShown'
const DURATION_MS = 1500

const visible = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

function dismiss() {
  visible.value = false
  if (timer) { clearTimeout(timer); timer = null }
}

function onKey(ev: KeyboardEvent) {
  if (ev.key === 'Escape') dismiss()
}

onMounted(() => {
  if (typeof window === 'undefined') return
  if (sessionStorage.getItem(SESSION_KEY) === '1') return
  // モーション抑制設定のユーザは即スキップ
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    sessionStorage.setItem(SESSION_KEY, '1')
    return
  }
  sessionStorage.setItem(SESSION_KEY, '1')
  visible.value = true
  window.addEventListener('keydown', onKey)
  timer = setTimeout(dismiss, DURATION_MS)
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('keydown', onKey)
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <Transition name="splash">
    <div
      v-if="visible"
      class="splash-root"
      role="img"
      aria-label="Pathfinder スプラッシュ"
      @click="dismiss"
    >
      <img src="/recoding_studio.png" alt="" class="splash-image" />
      <div class="splash-vignette" />
      <div class="splash-brand">
        <h1 class="splash-title">Pathfinder</h1>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.splash-root {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #0d0d0d;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 画像本体: Ken Burns でゆっくり拡大 */
.splash-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.78;
  transform-origin: center;
  animation: ken-burns 1.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* ヴィネット (端を暗く落とすシネマ感) */
.splash-vignette {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.55) 90%),
    linear-gradient(180deg, rgba(0,0,0,0.15) 0%, transparent 30%, transparent 70%, rgba(0,0,0,0.3) 100%);
  pointer-events: none;
}

/* 中央ブランド: 画像より僅か遅れて入り、消える時に上に微移動 */
.splash-brand {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  text-align: center;
  animation: brand-fade 1.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.splash-title {
  font-size: 56px;
  font-weight: 300;
  letter-spacing: -0.03em;
  color: #fff;
  text-shadow: 0 2px 22px rgba(0,0,0,0.65);
  margin: 0;
  line-height: 1;
}
.splash-tagline {
  font-size: 13px;
  letter-spacing: 0.08em;
  color: rgba(255,255,255,0.78);
  text-shadow: 0 1px 8px rgba(0,0,0,0.6);
  margin: 0;
}

/* Ken Burns: 軽い拡大 + 微パン */
@keyframes ken-burns {
  0%   { transform: scale(1.0) translate(0, 0); }
  100% { transform: scale(1.06) translate(-1.5%, -1%); }
}

/* ブランド要素: 0→入→保持→上に消える */
@keyframes brand-fade {
  0%   { opacity: 0; transform: translateY(8px); }
  20%  { opacity: 1; transform: translateY(0); }
  70%  { opacity: 1; transform: translateY(0); }
  100% { opacity: 0; transform: translateY(-6px); }
}

/* Vue Transition: ルート fade (in 0.25s / out 0.5s クロスフェード) */
.splash-enter-active { transition: opacity 0.25s ease-out; }
.splash-leave-active { transition: opacity 0.5s ease-in; }
.splash-enter-from,
.splash-leave-to { opacity: 0; }

@media (prefers-reduced-motion: reduce) {
  .splash-image { animation: none; }
  .splash-brand { animation: none; opacity: 1; }
}
</style>
