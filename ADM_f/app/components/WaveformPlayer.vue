<script setup lang="ts">
import WaveSurfer from 'wavesurfer.js'
import { useStreamPlayer } from '~/composables/useStreamPlayer'

const props = defineProps<{
  /** Audio ID (uuid). Required for real streaming. */
  audioId: string
  peaks: number[]
  durationSec: number
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const ws = ref<WaveSurfer | null>(null)

const player = useStreamPlayer(props.audioId)

const formatTime = (sec: number) => {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const totalLabel = computed(() => formatTime(props.durationSec))
const currentLabel = computed(() => formatTime(player.currentTime.value))

function buildWavePeaks(): [number[], number[]] {
  return [props.peaks, props.peaks.map((p) => -p)]
}

// WaveSurfer の表示用 progress を currentTime に同期
watch(() => player.currentTime.value, (t) => {
  if (ws.value) ws.value.setTime(t)
})

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

  // クリック位置 (0..1 の比率) を秒に変換して seekTo
  ws.value.on('interaction', (t) => {
    // t は秒 (duration が与えられているので直接秒数)
    void player.seekTo(t)
  })
})

onBeforeUnmount(() => {
  player.stop()
  ws.value?.destroy()
  ws.value = null
})

async function toggle() {
  if (player.isPlaying.value) {
    player.pause()
  } else {
    await player.resume()
  }
}

defineExpose({
  isPlaying: computed(() => player.isPlaying.value),
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
      <!-- Loading spinner -->
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
      <div ref="containerRef" class="w-full" />
      <div class="mt-1 flex items-center gap-3">
        <span class="font-mono text-[11px] text-muted">
          {{ currentLabel }} / {{ totalLabel }}
        </span>
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
