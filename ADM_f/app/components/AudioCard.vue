<script setup lang="ts">
import type { AudioTrack, DownloadApiResponse } from '~/types/audio'
import { useAuthStore } from '~/stores/auth'
import { useAudiosStore } from '~/stores/audios'
import { errorMessageJa } from '~/utils/errorMessageJa'

const props = defineProps<{ track: AudioTrack }>()
const auth = useAuthStore()
const audios = useAudiosStore()

const playerRef = ref<{ isPlaying: boolean } | null>(null)
const isPlaying = computed(() => playerRef.value?.isPlaying ?? false)

const isFav = ref(false)
const toggleFav = () => { isFav.value = !isFav.value }

const isNew = computed(() => {
  if (!props.track.publishedAt) return false
  const pub = new Date(props.track.publishedAt).getTime()
  return Date.now() - pub < 7 * 24 * 60 * 60 * 1000
})

const showCreator = computed(() =>
  auth.role === 'creator' || auth.role === 'admin'
)
const showFavCount = computed(() =>
  auth.role === 'creator' || auth.role === 'admin'
)

// ─── Download flow ───────────────────────────────
const confirmOpen = ref(false)
const dlLoading = ref(false)
const dlError = ref<string | null>(null)

function openConfirm() {
  if (!auth.canDownload) {
    alert('音源をダウンロードするには Activate してください。')
    return
  }
  if (auth.tokensRemaining < props.track.tokenCost) {
    alert(`トークン残量が不足しています。必要 ${props.track.tokenCost} / 残量 ${auth.tokensRemaining}`)
    return
  }
  dlError.value = null
  confirmOpen.value = true
}

async function executeDownload() {
  dlLoading.value = true
  dlError.value = null
  try {
    const api = useApi()
    const res = await api.post<DownloadApiResponse>(
      `/api/v1/audios/${props.track.id}/download`,
    )
    if (res.remaining_tokens !== null) {
      auth.applyRemainingTokens(res.remaining_tokens)
    }
    // backend は相対パスを返すので apiBaseUrl を付与してファイル保存
    const baseURL = useRuntimeConfig().public.apiBaseUrl as string
    const dlUrl = res.download_url.startsWith('http')
      ? res.download_url
      : `${baseURL}${res.download_url}`
    const a = document.createElement('a')
    a.href = dlUrl
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)

    confirmOpen.value = false
    // 単発販売: 売切のため一覧から除去
    audios.removeAudio(props.track.id)
  } catch (err: unknown) {
    dlError.value = errorMessageJa(err)
  } finally {
    dlLoading.value = false
  }
}
</script>

<template>
  <div
    class="card grid items-start gap-4 px-4 py-3 transition-all duration-200 hover:-translate-y-px"
    :class="isPlaying ? 'border-primary' : 'hover:border-primary'"
    style="grid-template-columns: 260px 1fr"
  >
    <WaveformPlayer
      ref="playerRef"
      :audio-id="track.id"
      :peaks="track.peaks"
      :duration-sec="track.durationSec"
    >
      <template #actions>
        <button
          class="flex items-center gap-1 transition-colors"
          :class="isFav ? 'text-accent' : 'text-muted hover:text-accent'"
          :aria-label="isFav ? 'お気に入り解除' : 'お気に入り'"
          @click.stop="toggleFav"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"
            :fill="isFav ? 'currentColor' : 'none'">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
          <span v-if="showFavCount" class="font-mono text-[11px]">
            {{ (track.favoriteCount ?? 0) + (isFav ? 1 : 0) }}
          </span>
        </button>

        <button
          class="flex items-center justify-center rounded-md border border-hairline bg-white/60 p-1 text-muted transition-colors hover:border-primary hover:text-primary-active disabled:opacity-40"
          :disabled="!auth.canDownload"
          :aria-label="auth.canDownload ? 'ダウンロード' : 'ダウンロード (Activate 必須)'"
          @click.stop="openConfirm"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
          </svg>
        </button>
      </template>
    </WaveformPlayer>

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
        <span class="h-1 w-1 rounded-full bg-muted-soft" />
        <span class="font-mono">{{ track.tokenCost }} tk</span>
      </div>
      <div v-if="track.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
        <span
          v-for="tag in track.tags"
          :key="tag"
          class="rounded-full border border-hairline bg-white/60 px-2 py-0.5 font-mono text-[10px] font-medium text-body transition-colors hover:border-primary hover:text-primary-active"
        >{{ tag }}</span>
      </div>
    </div>

    <!-- DL 確認モーダル -->
    <ConfirmModal
      v-model:open="confirmOpen"
      title="ダウンロードの確認"
      :confirm-label="`${track.tokenCost} tk を消費して購入`"
      cancel-label="やめる"
      :confirm-loading="dlLoading"
      :error-message="dlError"
      @confirm="executeDownload"
    >
      <p class="mb-2">
        <span class="font-medium text-ink">{{ track.title }}</span>
        をダウンロードします。
      </p>
      <p class="text-[12px] text-muted">
        この音源は <span class="text-accent font-medium">単発販売</span> のため、
        ダウンロード後は他ユーザの Dashboard から消えます。再ダウンロードは My Downloads から無料です。
      </p>
      <p class="mt-3 font-mono text-[12px]">
        消費: <span class="text-accent font-semibold">{{ track.tokenCost }} tk</span>
        / 残量見込: {{ Math.max(0, auth.tokensRemaining - track.tokenCost) }} tk
      </p>
    </ConfirmModal>
  </div>
</template>
