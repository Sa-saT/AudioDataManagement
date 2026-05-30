<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useSystemStore } from '~/stores/system'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })
useHead({ title: 'DM ToAdmin — Pathfinder' })

const auth = useAuthStore()
const system = useSystemStore()
const api = useApi()
const router = useRouter()

interface DMItem {
  id: string
  sender_id: string | null
  sender_name: string | null
  sender_kind: 'admin' | 'creator'
  content: string
  attachment_path: string | null
  created_at: string
}

const messages = ref<DMItem[]>([])
const loading = ref(false)
const fetchError = ref<string | null>(null)
const draft = ref('')
const sending = ref(false)
const listRef = ref<HTMLDivElement | null>(null)

onMounted(async () => {
  auth.hydrate()
  if (auth.role !== 'creator') {
    router.replace('/dashboard')
    return
  }
  await fetchMessages()
  // 既読化 + 通知バッジ再計算
  try {
    await api.post('/api/v1/me/dm/admin/view', { body: {} })
    await system.fetchCommissionUnread()
  } catch { /* silent */ }
})

async function fetchMessages() {
  loading.value = true
  fetchError.value = null
  try {
    messages.value = await api.get<DMItem[]>('/api/v1/me/dm/admin')
    await scrollToBottom()
  } catch (err) {
    fetchError.value = errorMessageJa(err)
  } finally {
    loading.value = false
  }
}

async function send() {
  const content = draft.value.trim()
  if (!content) return
  sending.value = true
  try {
    const msg = await api.post<DMItem>('/api/v1/me/dm/admin', { body: { content } })
    messages.value.push(msg)
    draft.value = ''
    await scrollToBottom()
  } catch (err) {
    alert(errorMessageJa(err))
  } finally {
    sending.value = false
  }
}

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function isMine(m: DMItem): boolean {
  return m.sender_kind === 'creator'
}
function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="mx-auto flex h-full max-w-[860px] flex-col px-6">
    <div class="flex shrink-0 items-end justify-between gap-4 pb-3 pt-5">
      <div>
        <h1 class="text-[20px] font-normal tracking-[-0.0125em] text-ink">DM ToAdmin</h1>
        <p class="mt-0.5 text-[12px] text-muted">admin チームへの直接メッセージ (Order に紐づかない継続的やりとり)</p>
      </div>
    </div>
    <div class="h-px shrink-0 bg-hairline-soft" />

    <!-- Messages -->
    <div ref="listRef" class="flex-1 overflow-y-auto py-4">
      <div v-if="loading" class="space-y-2">
        <div v-for="i in 4" :key="i" class="card h-12 animate-pulse bg-hairline-soft/40" />
      </div>
      <div v-else-if="fetchError" class="card mx-auto mt-6 max-w-[420px] p-6 text-center text-[13px]">
        <p class="font-medium text-accent">読み込みに失敗しました</p>
        <p class="mt-1 text-muted">{{ fetchError }}</p>
        <button class="mt-4 rounded-md bg-ink px-4 py-1.5 text-[12px] text-canvas hover:bg-primary" @click="fetchMessages">再試行</button>
      </div>
      <div v-else-if="messages.length === 0" class="py-16 text-center text-[13px] text-muted">
        メッセージはまだありません。
      </div>
      <div v-else class="space-y-1.5">
        <div
          v-for="m in messages"
          :key="m.id"
          class="flex gap-2"
          :class="isMine(m) ? 'flex-row-reverse' : 'flex-row'"
        >
          <div
            class="grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-[11px] font-bold"
            :class="isMine(m) ? 'bg-primary text-white' : 'bg-accent text-white'"
          >{{ isMine(m) ? 'C' : 'A' }}</div>
          <div class="max-w-[70%]" :class="isMine(m) ? 'items-end text-right' : 'items-start text-left'">
            <p class="mb-0.5 flex items-center gap-1.5 px-1 text-[10px]" :class="isMine(m) ? 'justify-end' : 'justify-start'">
              <span class="font-medium text-body-strong">{{ isMine(m) ? 'あなた' : (m.sender_name ?? 'Admin') + ' (Admin)' }}</span>
              <span class="text-muted">{{ formatTime(m.created_at) }}</span>
            </p>
            <div
              class="inline-block rounded-2xl px-3.5 py-2 text-left text-[13px] leading-relaxed whitespace-pre-wrap break-words shadow-sm"
              :class="isMine(m) ? 'bg-primary text-white' : 'bg-surface-strong/60 text-ink'"
            >{{ m.content }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Composer -->
    <div class="card shrink-0 px-3 py-2">
      <textarea
        v-model="draft"
        rows="2"
        placeholder="admin にメッセージを送る…"
        maxlength="4000"
        class="w-full resize-none bg-transparent text-[13px] text-ink outline-none placeholder:text-muted"
        @keydown.ctrl.enter.prevent="send"
      />
      <div class="mt-1.5 flex items-center justify-between">
        <span class="font-mono text-[10px] text-muted">{{ draft.length }} / 4000</span>
        <button
          class="rounded-md bg-ink px-3 py-1 text-[11px] font-medium text-canvas hover:bg-primary disabled:opacity-50"
          :disabled="sending || !draft.trim()"
          @click="send"
        >{{ sending ? '…' : '送信' }}</button>
      </div>
    </div>
  </div>
</template>
