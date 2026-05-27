<script setup lang="ts">
import { useApi } from '~/composables/useApi'
import { useAudiosStore } from '~/stores/audios'
import { errorMessageJa } from '~/utils/errorMessageJa'
import { mapApiAudio, type AudioTrack, type ApiAudioListItem } from '~/types/audio'

const PRESET_TAGS = [
  'warm', 'ambient', 'nature', 'cinematic',
  'dark', 'bright', 'acoustic', 'electronic',
  'energetic', 'peaceful', 'dramatic', 'mysterious',
]

const props = defineProps<{
  open: boolean
  track: AudioTrack
}>()

const emit = defineEmits<{
  'update:open': [v: boolean]
  updated: [track: AudioTrack]
}>()

const api = useApi()
const audios = useAudiosStore()

const title = ref('')
const description = ref('')
const youtubeSafe = ref(true)
const isPublic = ref(false)
const selectedTags = ref<string[]>([])
const loading = ref(false)
const errorMsg = ref<string | null>(null)

watch(() => props.open, (v) => {
  if (v) {
    title.value = props.track.title
    description.value = props.track.description ?? ''
    youtubeSafe.value = props.track.youtubeSafe
    isPublic.value = props.track.isPublic ?? false
    selectedTags.value = [...(props.track.tags ?? [])]
    errorMsg.value = null
  }
})

function toggleTag(tag: string) {
  const idx = selectedTags.value.indexOf(tag)
  if (idx === -1) selectedTags.value.push(tag)
  else selectedTags.value.splice(idx, 1)
}

function close() {
  if (loading.value) return
  emit('update:open', false)
}

async function save() {
  if (!title.value.trim() || loading.value) return
  loading.value = true
  errorMsg.value = null
  try {
    const res = await api.put<ApiAudioListItem & { is_public: boolean; description: string | null }>(`/api/v1/audios/${props.track.id}`, {
      body: {
        title: title.value.trim(),
        description: description.value.trim() || null,
        youtube_safe: youtubeSafe.value,
        is_public: isPublic.value,
        tags: selectedTags.value,
      },
    })
    const updated = mapApiAudio(res)
    audios.updateAudio(updated)
    emit('updated', updated)
    emit('update:open', false)
  } catch (e) {
    errorMsg.value = errorMessageJa(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-start justify-center bg-black/25 pt-16 backdrop-blur-sm"
        @click.self="close"
      >
        <div class="card mx-4 w-full max-w-[520px] p-6">
          <!-- Header -->
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-[15px] font-semibold text-ink">音源を編集</h2>
            <button class="text-muted hover:text-ink disabled:opacity-30" :disabled="loading" @click="close">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <div class="space-y-4">
            <!-- Title -->
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">
                タイトル <span class="text-error">*</span>
              </label>
              <input
                v-model="title"
                type="text"
                maxlength="120"
                class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[13px] text-ink placeholder:text-muted outline-none transition-colors focus:border-primary focus:bg-white"
              />
            </div>

            <!-- Description -->
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">説明</label>
              <textarea
                v-model="description"
                rows="2"
                maxlength="500"
                class="w-full resize-none rounded-md border border-hairline bg-white/70 px-3 py-2 text-[13px] text-ink outline-none transition-colors focus:border-primary"
              />
            </div>

            <!-- Tags -->
            <div>
              <label class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">イメージタグ</label>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="tag in PRESET_TAGS"
                  :key="tag"
                  type="button"
                  class="rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors"
                  :class="selectedTags.includes(tag)
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-hairline-strong bg-surface-strong/70 text-body-strong hover:border-primary/60 hover:text-ink'"
                  @click="toggleTag(tag)"
                >{{ tag }}</button>
              </div>
            </div>

            <!-- Toggles -->
            <div class="flex gap-6 border-t border-hairline pt-3">
              <label class="flex cursor-pointer items-center gap-2">
                <div
                  class="relative h-4 w-8 shrink-0 rounded-full transition-colors"
                  :class="youtubeSafe ? 'bg-primary' : 'bg-hairline-strong'"
                  @click="youtubeSafe = !youtubeSafe"
                >
                  <div
                    class="absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform"
                    :class="youtubeSafe ? 'translate-x-[18px]' : 'translate-x-0.5'"
                  />
                </div>
                <span class="text-[12px] text-body">YouTube Safe</span>
              </label>

              <label class="flex cursor-pointer items-center gap-2">
                <div
                  class="relative h-4 w-8 shrink-0 rounded-full transition-colors"
                  :class="isPublic ? 'bg-primary' : 'bg-hairline-strong'"
                  @click="isPublic = !isPublic"
                >
                  <div
                    class="absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform"
                    :class="isPublic ? 'translate-x-[18px]' : 'translate-x-0.5'"
                  />
                </div>
                <span class="text-[12px] text-body">公開</span>
              </label>
            </div>

            <!-- Error -->
            <p
              v-if="errorMsg"
              class="rounded-md border border-error/30 bg-error/5 px-3 py-2 text-[12px] text-error"
            >{{ errorMsg }}</p>
          </div>

          <!-- Actions -->
          <div class="mt-5 flex justify-end gap-2">
            <button
              class="rounded-md border border-hairline bg-white/60 px-4 py-1.5 text-[12px] text-body hover:text-ink disabled:opacity-40"
              :disabled="loading"
              @click="close"
            >キャンセル</button>
            <button
              class="flex items-center gap-1.5 rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary disabled:opacity-50"
              :disabled="!title.trim() || loading"
              @click="save"
            >
              <svg v-if="loading" class="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              保存
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-enter-active, .confirm-leave-active { transition: opacity 180ms ease; }
.confirm-enter-active > div, .confirm-leave-active > div { transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 180ms ease; }
.confirm-enter-from, .confirm-leave-to { opacity: 0; }
.confirm-enter-from > div { transform: translateY(-12px) scale(0.96); opacity: 0; }
.confirm-leave-to > div { transform: translateY(-6px); opacity: 0; }
</style>
