<script setup lang="ts">
import type { AudioTrack, DownloadApiResponse } from '~/types/audio'
import { useAuthStore } from '~/stores/auth'
import { useAudiosStore } from '~/stores/audios'
import { errorMessageJa } from '~/utils/errorMessageJa'

const props = defineProps<{ track: AudioTrack }>()
const auth = useAuthStore()
const audios = useAudiosStore()
const api = useApi()

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

// 自分の音源かどうか (creator/admin が自分のアップロード音源を見ているとき)
const isOwnAudio = computed(() =>
  (auth.role === 'creator' || auth.role === 'admin') &&
  auth.user?.id === props.track.creatorId
)

// DL ボタン表示条件:
//   user   → 常に表示 (token check あり)
//   creator → 自分の音源のみ (token不要)
//   admin  → 常に表示 (token不要)
const showDlButton = computed(() => {
  if (auth.role === 'user') return true
  if (auth.role === 'creator') return isOwnAudio.value
  if (auth.role === 'admin') return true
  return false
})

// admin / creator の DL は token消費なし・sold にしない
const isFreeDownload = computed(() =>
  auth.role === 'admin' || auth.role === 'creator'
)

// ─── Edit flow ───────────────────────────────────
const editOpen = ref(false)

// ─── Delete flow ─────────────────────────────────
const deleteOpen = ref(false)
const delLoading = ref(false)
const delError = ref<string | null>(null)

async function executeDelete() {
  delLoading.value = true
  delError.value = null
  try {
    await api.delete(`/api/v1/audios/${props.track.id}`)
    deleteOpen.value = false
    audios.removeAudio(props.track.id)
  } catch (err) {
    delError.value = errorMessageJa(err)
  } finally {
    delLoading.value = false
  }
}

// ─── Download flow ───────────────────────────────
const confirmOpen = ref(false)
const dlLoading = ref(false)
const dlError = ref<string | null>(null)

function openConfirm() {
  if (!auth.canDownload) {
    alert('音源をダウンロードするには Activate してください。')
    return
  }
  // user のみ token チェック (creator/admin は token不要)
  if (!isFreeDownload.value && auth.tokensRemaining < props.track.tokenCost) {
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

        <!-- DL ボタン: user=常時 / creator=自分の音源のみ / admin=常時 -->
        <button
          v-if="showDlButton"
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

    <div class="flex min-w-0 items-start gap-2 pt-1">
      <!-- メタ情報 -->
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <span class="truncate text-[14px] font-medium text-ink">{{ track.title }}</span>
          <span
            v-if="isNew"
            class="shrink-0 rounded-[3px] bg-accent px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest text-white"
          >NEW</span>
          <span
            v-if="isOwnAudio && track.isPublic === false"
            class="shrink-0 rounded-[3px] border border-muted-soft px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest text-muted"
          >DRAFT</span>
        </div>
        <div class="mt-0.5 flex items-center gap-2 text-[12px] text-body">
          <template v-if="showCreator">
            <span>{{ track.creatorName }}</span>
            <span class="h-1 w-1 rounded-full bg-muted" />
          </template>
          <span class="font-mono">{{ track.youtubeSafe ? 'YT安心' : 'YT要確認' }}</span>
          <span class="h-1 w-1 rounded-full bg-muted" />
          <span class="font-mono font-semibold text-ink">{{ track.tokenCost }} tk</span>
        </div>
        <div v-if="track.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
          <span
            v-for="tag in track.tags"
            :key="tag"
            class="rounded-full border border-hairline-strong bg-surface-strong/80 px-2 py-0.5 font-mono text-[10px] font-semibold text-body-strong transition-colors hover:border-primary hover:text-primary-active"
          >{{ tag }}</span>
        </div>
      </div>

      <!-- 編集・削除ボタン (最右、自分の音源のみ) -->
      <div v-if="isOwnAudio" class="flex shrink-0 items-center gap-1.5 pt-0.5">
        <button class="btn-edit flex items-center justify-center rounded-md border p-1.5" aria-label="編集" @click.stop="editOpen = true">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4Z"/>
          </svg>
        </button>
        <button class="btn-delete flex items-center justify-center rounded-md border p-1.5" aria-label="削除" @click.stop="deleteOpen = true">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 編集モーダル -->
    <AudioEditModal
      v-model:open="editOpen"
      :track="track"
    />

    <!-- 削除確認モーダル -->
    <ConfirmModal
      v-model:open="deleteOpen"
      title="音源を削除"
      :message="`「${track.title}」を削除します。この操作は取り消せません。`"
      confirm-label="削除する"
      cancel-label="やめる"
      variant="danger"
      :confirm-loading="delLoading"
      :error-message="delError"
      @confirm="executeDelete"
    />

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
      <!-- user: token消費・sold説明 -->
      <template v-if="!isFreeDownload">
        <p class="text-[12px] text-muted">
          この音源は <span class="text-accent font-medium">単発販売</span> のため、
          ダウンロード後は他ユーザの Dashboard から消えます。再ダウンロードは My Downloads から無料です。
        </p>
        <p class="mt-3 font-mono text-[12px]">
          消費: <span class="text-accent font-semibold">{{ track.tokenCost }} tk</span>
          / 残量見込: {{ Math.max(0, auth.tokensRemaining - track.tokenCost) }} tk
        </p>
      </template>
      <!-- creator/admin: 無料・Dashboard残留 -->
      <template v-else>
        <p class="text-[12px] text-muted">
          token消費なし。ダウンロード後も音源は Dashboard に残ります。
        </p>
      </template>
    </ConfirmModal>
  </div>
</template>

<style scoped>
.btn-edit  { border-color:#20b2aa55; background:#20b2aa10; color:#20b2aa; transition:background 150ms; }
.btn-edit:hover  { background:#20b2aa22; }
.btn-delete { border-color:#ff69b455; background:#ff69b410; color:#ff69b4; transition:background 150ms; }
.btn-delete:hover { background:#ff69b422; }
</style>
