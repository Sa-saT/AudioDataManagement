<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useApi } from '~/composables/useApi'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })
useHead({ title: 'Upload — Pathfinder' })

const auth = useAuthStore()
const api = useApi()
const router = useRouter()

onMounted(() => {
  auth.hydrate()
  if (auth.role !== 'creator' && auth.role !== 'admin') {
    router.replace('/dashboard')
  }
})

const canAccess = computed(() => auth.role === 'creator' || auth.role === 'admin')

// ─── File drop ───────────────────────────────────────
const isDragging = ref(false)
const file = ref<File | null>(null)
const fileError = ref<string | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}
function onDragLeave() {
  isDragging.value = false
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  setFile(e.dataTransfer?.files[0] ?? null)
}
function onFileInput(e: Event) {
  setFile((e.target as HTMLInputElement).files?.[0] ?? null)
}
function setFile(f: File | null) {
  fileError.value = null
  if (!f) return
  if (!f.name.toLowerCase().endsWith('.wav')) {
    fileError.value = '.wav ファイルのみ対応しています'
    file.value = null
    return
  }
  file.value = f
}
function clearFile() {
  file.value = null
  fileError.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

// ─── Form ─────────────────────────────────────────────
const PRESET_TAGS = [
  'warm', 'ambient', 'nature', 'cinematic',
  'dark', 'bright', 'acoustic', 'electronic',
  'energetic', 'peaceful', 'dramatic', 'mysterious',
]

const title = ref('')
const description = ref('')
const youtubeSafe = ref(true)
const isPublic = ref(false)
const selectedTags = ref<string[]>([])

function toggleTag(tag: string) {
  const idx = selectedTags.value.indexOf(tag)
  if (idx === -1) selectedTags.value.push(tag)
  else selectedTags.value.splice(idx, 1)
}

const canSubmit = computed(() => !!file.value && title.value.trim().length > 0 && !loading.value)

// ─── Submit ───────────────────────────────────────────
const loading = ref(false)
const errorMsg = ref<string | null>(null)
const succeeded = ref(false)

async function submit() {
  if (!canSubmit.value || !file.value) return
  loading.value = true
  errorMsg.value = null

  const form = new FormData()
  form.append('file', file.value)
  form.append('title', title.value.trim())
  if (description.value.trim()) form.append('description', description.value.trim())
  form.append('youtube_safe', String(youtubeSafe.value))
  form.append('is_public', String(isPublic.value))
  form.append('tags_json', JSON.stringify(selectedTags.value))

  try {
    await api.post('/api/v1/audios', { body: form })
    succeeded.value = true
  } catch (e) {
    errorMsg.value = errorMessageJa(e)
  } finally {
    loading.value = false
  }
}

function uploadAnother() {
  file.value = null
  title.value = ''
  description.value = ''
  youtubeSafe.value = true
  isPublic.value = false
  selectedTags.value = []
  errorMsg.value = null
  succeeded.value = false
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <div v-if="canAccess" class="mx-auto max-w-2xl px-4 py-10">

    <!-- ─── Success ─────────────────────────────────── -->
    <div v-if="succeeded" class="card p-10 text-center">
      <div class="mb-4 flex justify-center">
        <div class="flex h-14 w-14 items-center justify-center rounded-full bg-primary/15">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#40e0d0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6 9 17l-5-5"/>
          </svg>
        </div>
      </div>
      <h2 class="mb-1 text-[18px] font-semibold text-ink">アップロード完了</h2>
      <p class="mb-8 text-[13px] text-body">音源を受け付けました。処理完了後 Dashboard に反映されます。</p>
      <div class="flex justify-center gap-3">
        <button class="btn-secondary" @click="uploadAnother">続けてアップロード</button>
        <button class="btn-ink" @click="router.push('/dashboard')">Dashboard へ</button>
      </div>
    </div>

    <!-- ─── Upload form ─────────────────────────────── -->
    <template v-else>
      <h1 class="mb-6 text-[22px] font-semibold tracking-[-0.02em] text-ink">Upload Sound</h1>

      <!-- Dropzone -->
      <div
        class="mb-5 rounded-xl border-2 border-dashed transition-colors"
        :class="isDragging
          ? 'border-primary bg-primary/5'
          : file
            ? 'border-hairline-strong bg-surface-card/60'
            : 'border-hairline-strong bg-white/30 hover:border-primary/50'"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
      >
        <!-- File selected -->
        <div v-if="file" class="flex items-center gap-3 px-5 py-4">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#40e0d0" stroke-width="1.8" stroke-linecap="round">
            <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
          </svg>
          <div class="flex-1 min-w-0">
            <p class="truncate text-[13px] font-medium text-ink">{{ file.name }}</p>
            <p class="text-[11px] text-body">{{ formatBytes(file.size) }}</p>
          </div>
          <button
            class="ml-2 rounded p-1 text-muted hover:text-ink"
            title="クリア"
            @click="clearFile"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <!-- Empty drop zone -->
        <div
          v-else
          class="flex cursor-pointer flex-col items-center gap-2 py-10 text-center"
          @click="fileInputRef?.click()"
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#807d72" stroke-width="1.5" stroke-linecap="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <p class="text-[13px] text-body">
            <span class="font-medium text-ink">クリックして選択</span>、またはここにドロップ
          </p>
          <p class="text-[11px] text-body">PCM .wav / 最大 48kHz · 24bit · ステレオ</p>
        </div>
      </div>

      <p v-if="fileError" class="mb-4 text-[12px] text-error">{{ fileError }}</p>

      <input
        ref="fileInputRef"
        type="file"
        accept=".wav,audio/wav"
        class="hidden"
        @change="onFileInput"
      />

      <!-- Form fields -->
      <div class="card space-y-5 p-6">

        <!-- Title -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.07em] text-body-strong">
            タイトル <span class="text-error">*</span>
          </label>
          <input
            v-model="title"
            type="text"
            placeholder="例: Morning Bloom"
            maxlength="120"
            class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2.5 text-[13px] text-ink placeholder:text-muted outline-none transition-colors focus:border-primary focus:bg-white"
          />
        </div>

        <!-- Description -->
        <div>
          <label class="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.07em] text-body-strong">
            説明 <span class="text-[10px] normal-case tracking-normal text-muted-soft">(任意)</span>
          </label>
          <textarea
            v-model="description"
            rows="3"
            placeholder="音源のイメージや使用楽器など"
            maxlength="500"
            class="w-full resize-none rounded-md border border-hairline-strong bg-white/85 px-3 py-2.5 text-[13px] text-ink placeholder:text-muted outline-none transition-colors focus:border-primary focus:bg-white"
          />
        </div>

        <!-- Tags -->
        <div>
          <label class="mb-2 block text-[12px] font-semibold uppercase tracking-[0.07em] text-body-strong">
            イメージタグ <span class="text-[10px] normal-case tracking-normal text-muted-soft">(任意・複数可)</span>
          </label>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="tag in PRESET_TAGS"
              :key="tag"
              type="button"
              class="rounded-full border px-3 py-1 text-[11px] font-medium tracking-wide transition-colors"
              :class="selectedTags.includes(tag)
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-hairline-strong bg-surface-strong/70 text-body-strong hover:border-primary/60 hover:text-ink'"
              @click="toggleTag(tag)"
            >{{ tag }}</button>
          </div>
        </div>

        <!-- Toggles -->
        <div class="flex flex-col gap-3 border-t border-hairline pt-4">
          <label class="flex cursor-pointer items-center justify-between">
            <div>
              <p class="text-[13px] font-medium text-ink">YouTube Safe</p>
              <p class="text-[11px] text-body">Content ID に抵触しない素材として公開する</p>
            </div>
            <div
              class="relative h-5 w-9 shrink-0 rounded-full transition-colors"
              :class="youtubeSafe ? 'bg-primary' : 'bg-hairline-strong'"
              @click="youtubeSafe = !youtubeSafe"
            >
              <div
                class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform"
                :class="youtubeSafe ? 'translate-x-4' : 'translate-x-0.5'"
              />
            </div>
          </label>

          <label class="flex cursor-pointer items-center justify-between">
            <div>
              <p class="text-[13px] font-medium text-ink">Dashboard に公開</p>
              <p class="text-[11px] text-body">すぐに全ユーザへ表示する (OFF = 下書き)</p>
            </div>
            <div
              class="relative h-5 w-9 shrink-0 rounded-full transition-colors"
              :class="isPublic ? 'bg-primary' : 'bg-hairline-strong'"
              @click="isPublic = !isPublic"
            >
              <div
                class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform"
                :class="isPublic ? 'translate-x-4' : 'translate-x-0.5'"
              />
            </div>
          </label>
        </div>

        <!-- Error -->
        <p
          v-if="errorMsg"
          class="rounded-md border border-error/30 bg-error/5 px-3 py-2.5 text-[12px] text-error"
        >{{ errorMsg }}</p>

        <!-- Actions -->
        <div class="flex items-center justify-between pt-1">
          <button
            class="text-[12px] text-muted transition-colors hover:text-ink"
            @click="router.push('/dashboard')"
          >キャンセル</button>
          <button
            class="btn-ink flex items-center gap-2 disabled:opacity-50"
            :disabled="!canSubmit"
            @click="submit"
          >
            <svg
              v-if="loading"
              class="animate-spin"
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            ><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
            <svg
              v-else
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
            ><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            {{ loading ? 'アップロード中...' : 'アップロード' }}
          </button>
        </div>
      </div>
    </template>

  </div>
</template>
