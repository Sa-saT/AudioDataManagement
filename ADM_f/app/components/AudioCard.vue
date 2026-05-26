<script setup lang="ts">
import type { AudioTrack } from '~/types/audio'
import { useAuthStore } from '~/stores/auth'

const props = defineProps<{ track: AudioTrack }>()
const auth = useAuthStore()

const yenFmt = new Intl.NumberFormat('ja-JP')
const price = computed(() => `¥${yenFmt.format(props.track.price)}`)

const onDownload = () => {
  if (!auth.canDownload) {
    alert('音源をダウンロードするには /activate からアクティベートしてください。')
    return
  }
  // mock — real backend will stream the file
  alert(`(mock) ダウンロード開始: ${props.track.title}`)
}
</script>

<template>
  <div class="card flex items-stretch gap-4 px-4 py-3">
    <!-- Waveform + transport -->
    <div class="min-w-0 flex-1">
      <WaveformPlayer
        :peaks="track.peaks"
        :duration-sec="track.durationSec"
        :src="track.src"
      />
    </div>

    <!-- Right rail: actions + meta -->
    <div class="flex w-[300px] shrink-0 flex-col justify-between gap-2">
      <div class="flex items-center gap-2">
        <button
          class="grid h-7 w-7 place-items-center rounded-md border border-hairline-strong bg-surface-card text-muted hover:text-primary"
          aria-label="お気に入り"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="12 2 15 9 22 9.5 17 14.5 18.5 22 12 18 5.5 22 7 14.5 2 9.5 9 9 12 2" />
          </svg>
        </button>
        <button
          class="grid h-7 w-7 place-items-center rounded-md border border-hairline-strong bg-surface-card text-error hover:bg-error/10"
          aria-label="ダウンロード"
          @click="onDownload"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v12" />
            <path d="m7 10 5 5 5-5" />
            <path d="M5 21h14" />
          </svg>
        </button>
        <button
          class="grid h-7 w-7 place-items-center rounded-md border border-hairline-strong bg-surface-card text-muted hover:text-ink"
          aria-label="カート"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="9" cy="20" r="1.5" />
            <circle cx="18" cy="20" r="1.5" />
            <path d="M3 4h2l2.5 11h11l2-8H6" />
          </svg>
        </button>
        <div class="ml-auto font-mono text-[12px] text-ink">{{ price }}</div>
      </div>

      <div class="min-w-0">
        <div class="truncate text-[14px] font-medium text-ink">{{ track.title }}</div>
        <div class="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
          <span class="pill bg-surface-strong">{{ track.creatorName }}</span>
          <span class="font-mono">#{{ track.id.slice(-5) }}</span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[10px] text-muted">
        <span>類似作品 {{ track.similarWorks }}</span>
        <span :class="track.youtubeSafe ? 'text-success' : 'text-muted-soft'">
          YouTube{{ track.youtubeSafe ? '安心' : '要確認' }}
        </span>
      </div>
    </div>
  </div>
</template>
