<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })
useHead({ title: 'My Downloads — Pathfinder' })

const auth = useAuthStore()
const api = useApi()

interface DownloadItem {
  id: string
  title: string
  creator: { id: string; display_name: string }
  duration_sec: number
  token_cost: number
  tags: string[]
  peaks: number[]
  downloaded_at: string | null
  tokens_consumed: number
  file_size_bytes: number
  copy_exists: boolean
}

interface DownloadsResponse {
  items: DownloadItem[]
  storage_used_bytes: number
}

const items = ref<DownloadItem[]>([])
const storageUsedBytes = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  auth.hydrate()
  if (auth.isActivated) await fetchDownloads()
})

async function fetchDownloads() {
  loading.value = true
  error.value = null
  try {
    const res = await api.get<DownloadsResponse>('/api/v1/me/downloads')
    items.value = res.items
    storageUsedBytes.value = res.storage_used_bytes
  } catch (err) {
    error.value = errorMessageJa(err)
  } finally {
    loading.value = false
  }
}

// ─── Re-download ──────────────────────────────────
const dlLoading = ref<string | null>(null)  // audio_id | null

async function redownload(item: DownloadItem) {
  if (dlLoading.value) return
  dlLoading.value = item.id
  try {
    const baseURL = useRuntimeConfig().public.apiBaseUrl as string
    const res = await api.get<{ url: string }>(`/api/v1/me/downloads/${item.id}/copy-url`)
    const url = res.url.startsWith('http') ? res.url : `${baseURL}${res.url}`
    const a = document.createElement('a')
    a.href = url
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch (err) {
    alert(errorMessageJa(err))
  } finally {
    dlLoading.value = null
  }
}

// ─── Delete ──────────────────────────────────────
const deleteTarget = ref<DownloadItem | null>(null)
const deleteLoading = ref(false)
const deleteError = ref<string | null>(null)

function openDelete(item: DownloadItem) {
  deleteTarget.value = item
  deleteError.value = null
}

async function executeDelete() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  deleteError.value = null
  try {
    await api.delete(`/api/v1/me/downloads/${deleteTarget.value.id}`)
    // Update copy_exists flag
    const idx = items.value.findIndex(i => i.id === deleteTarget.value!.id)
    if (idx !== -1) {
      const old = items.value[idx]!
      items.value[idx] = { ...old, copy_exists: false, file_size_bytes: 0 }
    }
    // Recalculate storage usage
    storageUsedBytes.value = items.value.reduce((sum, i) => sum + i.file_size_bytes, 0)
    deleteTarget.value = null
  } catch (err) {
    deleteError.value = errorMessageJa(err)
  } finally {
    deleteLoading.value = false
  }
}

// ─── Helpers ─────────────────────────────────────
function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- Header -->
    <div class="flex shrink-0 items-end justify-between gap-4 pb-3 pt-5">
      <div>
        <h1 class="text-[20px] font-normal tracking-[-0.0125em] text-ink">My Downloads</h1>
        <p class="mt-0.5 text-[12px] text-muted">購入済み音源の再ダウンロード / 管理</p>
      </div>

      <!-- Storage usage -->
      <div v-if="auth.isActivated && items.length > 0" class="shrink-0 text-right font-mono text-[11px] text-muted">
        <span>ストレージ使用量</span>
        <span class="ml-2 font-semibold text-ink">{{ formatBytes(storageUsedBytes) }}</span>
      </div>
    </div>

    <div class="h-px shrink-0 bg-hairline-soft" />

    <!-- Body -->
    <div class="flex-1 overflow-y-auto py-3">

      <!-- Not activated -->
      <div v-if="!auth.isActivated" class="card p-6 text-center text-[13px] text-body">
        アクティベートしていないため、ダウンロード履歴はありません。
      </div>

      <!-- Loading -->
      <div v-else-if="loading" class="space-y-2">
        <div v-for="i in 3" :key="i" class="card flex items-center gap-4 px-4 py-3">
          <div class="h-12 w-40 animate-pulse rounded bg-hairline-soft" />
          <div class="flex-1 space-y-2">
            <div class="h-4 w-1/2 animate-pulse rounded bg-hairline-soft" />
            <div class="h-3 w-1/3 animate-pulse rounded bg-hairline-soft" />
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="card mx-auto mt-6 max-w-[520px] p-6 text-center text-[13px]">
        <p class="font-medium text-accent">読み込みに失敗しました</p>
        <p class="mt-1 text-muted">{{ error }}</p>
        <button
          class="mt-4 rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary"
          @click="fetchDownloads"
        >再試行</button>
      </div>

      <!-- Empty -->
      <div v-else-if="items.length === 0" class="py-16 text-center text-[13px] text-muted">
        まだ購入した音源はありません。
      </div>

      <!-- List -->
      <div v-else class="space-y-2">
        <div
          v-for="item in items"
          :key="item.id"
          class="card flex items-center gap-4 px-4 py-3"
        >
          <!-- Left: meta -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate text-[14px] font-medium text-ink">{{ item.title }}</span>
              <span class="shrink-0 font-mono text-[11px] text-muted">{{ formatDuration(item.duration_sec) }}</span>
            </div>
            <div class="mt-0.5 flex items-center gap-2 text-[12px] text-body">
              <span>{{ item.creator.display_name }}</span>
              <span class="h-1 w-1 rounded-full bg-muted" />
              <span class="font-mono">{{ item.tokens_consumed }} tk 消費</span>
              <span class="h-1 w-1 rounded-full bg-muted" />
              <span class="font-mono">{{ formatDate(item.downloaded_at) }}</span>
            </div>
            <div v-if="item.tags.length" class="mt-1.5 flex flex-wrap gap-1">
              <span
                v-for="tag in item.tags"
                :key="tag"
                class="rounded-full border border-hairline-strong bg-surface-strong/80 px-2 py-0.5 font-mono text-[10px] text-body-strong"
              >{{ tag }}</span>
            </div>
          </div>

          <!-- Right: actions -->
          <div class="flex shrink-0 items-center gap-2">
            <!-- Storage info (copy exists) -->
            <span v-if="item.copy_exists" class="font-mono text-[10px] text-muted">
              {{ formatBytes(item.file_size_bytes) }}
            </span>
            <span v-else class="font-mono text-[10px] text-accent">コピーなし</span>

            <!-- Re-download -->
            <button
              class="flex items-center gap-1.5 rounded-md border border-hairline-strong bg-surface-strong/60 px-2.5 py-1 text-[12px] font-medium text-body-strong transition-colors hover:border-primary hover:text-primary-active disabled:opacity-40"
              :disabled="dlLoading === item.id"
              @click="redownload(item)"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
              </svg>
              {{ dlLoading === item.id ? '…' : '再DL' }}
            </button>

            <!-- Delete copy -->
            <button
              v-if="item.copy_exists"
              class="flex items-center justify-center rounded-md border border-hairline p-1.5 text-muted transition-colors hover:border-accent hover:text-accent"
              aria-label="コピーを削除"
              @click="openDelete(item)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirm modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="deleteTarget"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          @click.self="deleteTarget = null"
        >
          <div class="card w-full max-w-[420px] p-6">
            <h2 class="text-[15px] font-medium text-ink">コピーを削除</h2>
            <p class="mt-3 text-[13px] text-body">
              <span class="font-medium text-ink">{{ deleteTarget.title }}</span>
              のローカルコピーを削除します。
            </p>
            <p class="mt-1 text-[12px] text-accent">
              削除後は再ダウンロードができなくなります。元の音源は sold 状態のため Dashboard にも表示されません。
            </p>

            <p v-if="deleteError" class="mt-3 text-[12px] text-accent">{{ deleteError }}</p>

            <div class="mt-5 flex justify-end gap-2">
              <button
                class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] font-medium text-body-strong hover:border-primary hover:text-ink"
                @click="deleteTarget = null"
              >やめる</button>
              <button
                class="rounded-md bg-accent px-4 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50"
                :disabled="deleteLoading"
                @click="executeDelete"
              >{{ deleteLoading ? '削除中…' : '削除する' }}</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 200ms; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.overflow-y-auto::-webkit-scrollbar { display: none; }
.overflow-y-auto { scrollbar-width: none; }
</style>
