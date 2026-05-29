<script setup lang="ts">
// WAVEFORM_SHADER_SPEC.md §4 準拠 (改訂: 単一色 + 再生済み dim)。
// wavesurfer.js を撤去し WebGL2/Canvas2D で peaks v2 を描画する。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { PeaksAny } from '~/components/waveform/peaks'
import { useWaveformGL, type WaveformColors } from '~/components/waveform/useWaveformGL'
import { useStreamPlayer } from '~/composables/useStreamPlayer'

const props = defineProps<{
  audioId: string
  peaks: PeaksAny
  durationSec: number
  /** ガンマ補正係数 (default 0.4)。小音を持ち上げる強さ */
  gamma?: number
}>()

// ─── DOM refs ─────────────────────────────────────
const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

const player = useStreamPlayer(props.audioId)

// ─── Time labels ──────────────────────────────────
const formatTime = (sec: number) => {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
const totalLabel = computed(() => formatTime(props.durationSec))
const currentLabel = computed(() => formatTime(player.currentTime.value))

// ─── Reactive state for shader ────────────────────
const playPos = computed(() =>
  props.durationSec > 0
    ? Math.min(1, Math.max(0, player.currentTime.value / props.durationSec))
    : 0,
)
const peaksRef = computed(() => props.peaks)

// 単一色 = wavesurfer 時の waveColor (#807d72 washi グレー)。
// 再生済みはシェーダー側で alpha を下げて dim 表示。
const colors = ref<WaveformColors>({
  wave: [0x80 / 255, 0x7d / 255, 0x72 / 255],
})

// ─── reduced-motion (再生ボタン EQ アニメだけに影響) ─────
const reducedMotion = ref(false)
let motionMql: MediaQueryList | null = null
function onMotionChange(ev: MediaQueryListEvent | MediaQueryList) {
  reducedMotion.value = ev.matches
}

// ─── Compose WebGL renderer ───────────────────────
const { mode, init, kick } = useWaveformGL({
  canvasRef,
  peaksSource: peaksRef,
  playPos,
  isPlaying: computed(() => player.isPlaying.value),
  colors,
  gamma: props.gamma ?? 0.4,
})

// ─── Interaction (クリックシークのみ。ホバー演出は削除) ─────
function hitRatio(ev: MouseEvent): number {
  const el = containerRef.value
  if (!el) return 0
  const rect = el.getBoundingClientRect()
  return Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width))
}
function onClick(ev: MouseEvent) {
  void player.seekTo(hitRatio(ev) * props.durationSec)
}

// ─── Lifecycle ────────────────────────────────────
let resizeObs: ResizeObserver | null = null
onMounted(() => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    motionMql = window.matchMedia('(prefers-reduced-motion: reduce)')
    reducedMotion.value = motionMql.matches
    motionMql.addEventListener('change', onMotionChange)
  }
  init()
  if (canvasRef.value) {
    resizeObs = new ResizeObserver(() => kick())
    resizeObs.observe(canvasRef.value)
  }
  if (player.isPlaying.value && !reducedMotion.value) startViz()
})

onBeforeUnmount(() => {
  player.stop()
  stopViz()
  resizeObs?.disconnect()
  resizeObs = null
  if (motionMql) {
    motionMql.removeEventListener('change', onMotionChange)
    motionMql = null
  }
})

async function toggle() {
  if (player.isPlaying.value) player.pause()
  else await player.resume()
}

// 再生中 EQ ビジュアライザ用: 24本のバー高さを JS で完全ランダムに更新
// → CSS animation のループ周期が無くなり、真に予測不能な動きになる
const VIZ_BAR_COUNT = 24
const vizScales = ref<number[]>(Array(VIZ_BAR_COUNT).fill(0.3))
const vizOpacity = ref<number[]>(Array(VIZ_BAR_COUNT).fill(0.5))
let vizTimer: number | null = null

function randomBarScale(): number {
  // 確率分布で「たまに大きく跳ねる」感を作る
  const r = Math.random()
  if (r < 0.18) return 1.9 + Math.random() * 0.8     // 1.9 – 2.7 (sharp peak)
  if (r < 0.45) return 1.0 + Math.random() * 0.8     // 1.0 – 1.8 (medium)
  if (r < 0.75) return 0.4 + Math.random() * 0.5     // 0.4 – 0.9 (small)
  return 0.08 + Math.random() * 0.25                 // 0.08 – 0.33 (silent)
}

function tickViz() {
  for (let i = 0; i < VIZ_BAR_COUNT; i++) {
    vizScales.value[i] = randomBarScale()
    vizOpacity.value[i] = 0.45 + Math.min(0.55, (vizScales.value[i] ?? 0) / 2.7 * 0.55)
  }
}

function startViz() {
  if (vizTimer !== null) return
  tickViz()
  // 100ms ごとに全バー再ランダム化 → CSS transition で隣接フレーム間を補間
  vizTimer = window.setInterval(tickViz, 100)
}
function stopViz() {
  if (vizTimer !== null) {
    clearInterval(vizTimer)
    vizTimer = null
  }
}

watch(() => player.isPlaying.value, (playing) => {
  if (playing && !reducedMotion.value) startViz()
  else stopViz()
})

defineExpose({
  isPlaying: computed(() => player.isPlaying.value),
  renderMode: computed(() => mode.value),
})
</script>

<template>
  <div class="flex items-center gap-3">
    <button
      class="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors"
      :class="player.isPlaying.value ? 'bg-primary text-white' : 'bg-[#808080] text-canvas hover:bg-primary'"
      :aria-label="player.isPlaying.value ? 'Pause' : 'Play'"
      :disabled="player.isLoading.value"
      @click="toggle"
    >
      <!-- Loading spinner -->
      <svg v-if="player.isLoading.value" class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>

      <!-- Idle: ▶ -->
      <svg v-else-if="!player.isPlaying.value" width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
        <path d="M3 1.5v11l9-5.5z" />
      </svg>

      <!-- Playing: 円形 EQ ビジュアライザ (reduced-motion 時は ■ ポーズ) -->
      <svg
        v-else-if="!reducedMotion"
        viewBox="0 0 32 32"
        class="eq-viz h-7 w-7"
        aria-hidden="true"
      >
        <g v-for="i in VIZ_BAR_COUNT" :key="i" :transform="`rotate(${(i - 1) * 15} 16 16)`">
          <rect
            x="15.1"
            y="2"
            width="1.8"
            height="5"
            rx="0.9"
            fill="currentColor"
            class="eq-bar"
            :style="{
              transform: `scaleY(${vizScales[i - 1]})`,
              opacity: vizOpacity[i - 1],
            }"
          />
        </g>
      </svg>
      <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
        <rect x="2" y="1.5" width="3" height="9" rx="0.5" />
        <rect x="7" y="1.5" width="3" height="9" rx="0.5" />
      </svg>
    </button>

    <div class="min-w-0 flex-1">
      <div
        ref="containerRef"
        class="relative h-12 w-full cursor-pointer select-none"
        @click="onClick"
      >
        <canvas ref="canvasRef" class="block h-full w-full" />
      </div>
      <div class="mt-1 flex items-center gap-3">
        <span class="font-mono text-[11px] text-muted">
          {{ currentLabel }} / {{ totalLabel }}
        </span>
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* バー scaleY と opacity は JS から書き換え。CSS は補間 (transition) のみ担当 */
.eq-bar {
  transform-box: fill-box;
  transform-origin: center bottom;
  transition:
    transform 110ms cubic-bezier(0.2, 0.7, 0.3, 1.2),
    opacity 110ms linear;
}
</style>
