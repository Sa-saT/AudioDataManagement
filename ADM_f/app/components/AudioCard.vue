<script setup lang="ts">
import type { AudioTrack } from '~/types/audio'
import { useAuthStore } from '~/stores/auth'

const props = defineProps<{ track: AudioTrack }>()
const auth = useAuthStore()

const playerRef = ref<{ isPlaying: boolean } | null>(null)
const isPlaying = computed(() => playerRef.value?.isPlaying ?? false)

const isFav = ref(false)
const toggleFav = () => { isFav.value = !isFav.value }

const isNew = computed(() => {
  const pub = new Date(props.track.publishedAt).getTime()
  return Date.now() - pub < 7 * 24 * 60 * 60 * 1000
})

const showCreator = computed(() =>
  auth.role === 'creator' || auth.role === 'admin'
)
const showFavCount = computed(() =>
  auth.role === 'creator' || auth.role === 'admin'
)

const onDownload = () => {
  if (!auth.canDownload) {
    alert('音源をダウンロードするには Activate してください。')
    return
  }
  alert(`(mock) ダウンロード開始: ${props.track.title}`)
}
</script>

<template>
  <div
    class="card grid items-start gap-4 px-4 py-3 transition-all duration-200 hover:-translate-y-px"
    :class="isPlaying ? 'border-primary' : 'hover:border-primary'"
    style="grid-template-columns: 260px 1fr"
  >
    <!-- Left: waveform + actions row below -->
    <div class="flex flex-col gap-2">
      <WaveformPlayer
        ref="playerRef"
        :peaks="track.peaks"
        :duration-sec="track.durationSec"
        :src="track.src"
      />

      <!-- 波形下のアクション行: ♥ + DL -->
      <div class="flex items-center justify-end gap-3 pl-[52px]">
        <button
          class="flex items-center gap-1 transition-colors"
          :class="isFav ? 'text-accent' : 'text-muted hover:text-accent'"
          :aria-label="isFav ? 'お気に入り解除' : 'お気に入り'"
          @click.stop="toggleFav"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"
            :fill="isFav ? 'currentColor' : 'none'">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
          <span v-if="showFavCount" class="font-mono text-[11px]">
            {{ (track.favoriteCount ?? 0) + (isFav ? 1 : 0) }}
          </span>
        </button>

        <button
          class="flex items-center justify-center rounded-md border border-hairline bg-white/60 p-1.5 text-muted transition-colors hover:border-primary hover:text-primary-active"
          aria-label="ダウンロード"
          @click.stop="onDownload"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Right: meta + tags -->
    <div class="min-w-0 pt-1">
      <div class="flex items-center gap-2">
        <span class="truncate text-[14px] font-medium text-ink">{{ track.title }}</span>
        <span
          v-if="isNew"
          class="shrink-0 rounded-[3px] bg-accent px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest text-white"
        >NEW</span>
      </div>
      <div class="mt-0.5 flex items-center gap-2 text-[12px] text-muted">
        <template v-if="showCreator">
          <span>{{ track.creatorName }}</span>
          <span class="h-1 w-1 rounded-full bg-muted-soft" />
        </template>
        <span class="font-mono">{{ track.youtubeSafe ? 'YT安心' : 'YT要確認' }}</span>
      </div>
      <div v-if="track.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
        <span
          v-for="tag in track.tags"
          :key="tag"
          class="rounded-full border border-hairline bg-white/60 px-2 py-0.5 font-mono text-[10px] font-medium text-body transition-colors hover:border-primary hover:text-primary-active"
        >{{ tag }}</span>
      </div>
    </div>
  </div>
</template>
