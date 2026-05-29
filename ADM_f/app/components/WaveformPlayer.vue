<script setup lang="ts">
// WAVEFORM_SHADER_SPEC.md §4 準拠。
// wavesurfer.js を撤去し WebGL2/Canvas2D で peaks v2 を描画する。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

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

// デザイントークン (RGB 0..1 に変換済み)
//  washi = #807d72 / turquoise = #40e0d0 / dark turquoise = #20b2aa / tomato = #ff6347
const colors = ref<WaveformColors>({
  wave:      [0x80 / 255, 0x7d / 255, 0x72 / 255],
  progress:  [0x40 / 255, 0xe0 / 255, 0xd0 / 255],
  rms:       [0x20 / 255, 0xb2 / 255, 0xaa / 255],
  hoverGlow: [0xff / 255, 0x63 / 255, 0x47 / 255],
})

// ─── prefers-reduced-motion ───────────────────────
const reducedMotion = ref(false)
let motionMql: MediaQueryList | null = null
function onMotionChange(ev: MediaQueryListEvent | MediaQueryList) {
  reducedMotion.value = ev.matches
}

// ─── Compose WebGL renderer ───────────────────────
const { mode, setHover, init, kick } = useWaveformGL({
  canvasRef,
  peaksSource: peaksRef,
  playPos,
  isPlaying: computed(() => player.isPlaying.value),
  colors,
  gamma: props.gamma ?? 0.4,
  reducedMotion,
})

// ─── Interaction handlers ─────────────────────────
function hitRatio(ev: MouseEvent): number {
  const el = containerRef.value
  if (!el) return 0
  const rect = el.getBoundingClientRect()
  return Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width))
}

function onClick(ev: MouseEvent) {
  const r = hitRatio(ev)
  void player.seekTo(r * props.durationSec)
}

function onMove(ev: MouseEvent) {
  if (reducedMotion.value) return
  setHover(hitRatio(ev))
}
function onLeave() { setHover(null) }

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
})

onBeforeUnmount(() => {
  player.stop()
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

defineExpose({
  isPlaying: computed(() => player.isPlaying.value),
  renderMode: computed(() => mode.value),
})
</script>

<template>
  <div class="flex items-center gap-3">
    <button
      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors"
      :class="player.isPlaying.value ? 'bg-primary text-white' : 'bg-ink text-canvas hover:bg-primary'"
      :aria-label="player.isPlaying.value ? 'Pause' : 'Play'"
      :disabled="player.isLoading.value"
      @click="toggle"
    >
      <svg v-if="player.isLoading.value" class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
      <svg v-else-if="!player.isPlaying.value" width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
        <path d="M3 1.5v11l9-5.5z" />
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
        @mousemove="onMove"
        @mouseleave="onLeave"
      >
        <canvas
          ref="canvasRef"
          class="block h-full w-full"
        />
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
