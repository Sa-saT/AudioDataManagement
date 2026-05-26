<script setup lang="ts">
import WaveSurfer from 'wavesurfer.js'

const props = defineProps<{
  peaks: number[]
  durationSec: number
  src?: string
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const ws = ref<WaveSurfer | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)

const formatTime = (sec: number) => {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const totalLabel = computed(() => formatTime(props.durationSec))
const currentLabel = computed(() => formatTime(currentTime.value))

function buildWavePeaks(): [number[], number[]] {
  // wavesurfer accepts dual-channel arrays (top/bottom). We mirror the same peaks.
  return [props.peaks, props.peaks.map((p) => -p)]
}

onMounted(() => {
  if (!containerRef.value) return
  ws.value = WaveSurfer.create({
    container: containerRef.value,
    height: 48,
    waveColor: '#807d72',
    progressColor: '#40e0d0',
    cursorColor: '#40e0d0',
    cursorWidth: 1,
    barWidth: 2,
    barGap: 1,
    barRadius: 1,
    interact: true,
    peaks: buildWavePeaks(),
    duration: props.durationSec,
  })

  ws.value.on('play', () => (isPlaying.value = true))
  ws.value.on('pause', () => (isPlaying.value = false))
  ws.value.on('finish', () => {
    isPlaying.value = false
    currentTime.value = 0
  })
  ws.value.on('timeupdate', (t) => {
    currentTime.value = t
  })
  ws.value.on('interaction', (t) => {
    currentTime.value = t
  })
})

onBeforeUnmount(() => {
  ws.value?.destroy()
  ws.value = null
})

function toggle() {
  if (!ws.value) return
  // No real audio loaded → simulate playback via timer for the mock.
  if (!props.src) {
    if (isPlaying.value) {
      stopMock()
    } else {
      startMock()
    }
    return
  }
  ws.value.playPause()
}

let mockTimer: ReturnType<typeof setInterval> | null = null
function startMock() {
  isPlaying.value = true
  mockTimer = setInterval(() => {
    currentTime.value = Math.min(currentTime.value + 0.1, props.durationSec)
    ws.value?.setTime(currentTime.value)
    if (currentTime.value >= props.durationSec) stopMock(true)
  }, 100)
}
function stopMock(reset = false) {
  isPlaying.value = false
  if (mockTimer) clearInterval(mockTimer)
  mockTimer = null
  if (reset) {
    currentTime.value = 0
    ws.value?.setTime(0)
  }
}
onBeforeUnmount(() => {
  if (mockTimer) clearInterval(mockTimer)
})

defineExpose({ isPlaying })
</script>

<template>
  <div class="flex items-center gap-3">
    <button
      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors"
      :class="isPlaying ? 'bg-primary text-white' : 'bg-ink text-canvas hover:bg-primary'"
      :aria-label="isPlaying ? 'Pause' : 'Play'"
      @click="toggle"
    >
      <svg v-if="!isPlaying" width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
        <path d="M3 1.5v11l9-5.5z" />
      </svg>
      <svg v-else width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
        <rect x="2" y="1.5" width="3" height="9" rx="0.5" />
        <rect x="7" y="1.5" width="3" height="9" rx="0.5" />
      </svg>
    </button>

    <div class="flex-1">
      <div ref="containerRef" class="w-full"></div>
      <div class="mt-1 font-mono text-[11px] text-muted">
        {{ currentLabel }} / {{ totalLabel }}
      </div>
    </div>
  </div>
</template>
