<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })

const auth = useAuthStore()
const api = useApi()
const route = useRoute()
const router = useRouter()

const orderId = computed(() => route.params.id as string)

// ─── Types ────────────────────────────────────────
interface Candidate {
  id: string
  creator_id: string
  creator_name: string
  response_status: string
  sent_at: string
}

interface Message {
  id: string
  sender_id: string | null
  sender_name: string | null
  content: string | null
  attachment_path: string | null
  kind: string
  created_at: string
}

interface OrderBrief {
  // Step 1
  sound_type?: string
  purpose?: string
  purpose_note?: string
  length_sec?: number
  // Step 2 BGM
  bgm_scenes?: string[]
  bgm_loop?: boolean
  bgm_note?: string
  // Step 2 SE
  se_trigger?: string
  se_functions?: string[]
  // Step 3 Emotional
  emotions_target?: string[]
  emotions_avoid?: string[]
  memory_impression?: string
  // Step 4 Texture
  tx_organic_electronic?: string
  tx_melody_rhythm?: string
  tx_warm_cold?: string
  tx_sparse_dense?: string
  tx_static_dynamic?: string
  // Step 5 Reference
  reference_urls?: string
  reference_elements?: string[]
  reference_avoid?: string
  // Step 6 Technical
  delivery_format?: string
  deadline?: string
  budget_range?: string
  note?: string
}

interface OrderDetail {
  id: string
  title: string
  serial: int
  description: string | null
  brief: OrderBrief | null
  token_cost: int
  desired_deadline: string
  status: string
  user_id: string
  user_name: string
  assigned_creator_id: string | null
  assigned_creator_name: string | null
  candidates: Candidate[]
  messages: Message[]
  file_path: string | null
  notified_at: string | null
  created_at: string
  updated_at: string
}

type int = number

useHead(computed(() => ({ title: `発注 — Pathfinder` })))

// ─── Fetch ────────────────────────────────────────
const order = ref<OrderDetail | null>(null)
const loading = ref(false)
const fetchError = ref<string | null>(null)

onMounted(async () => {
  auth.hydrate()
  await fetchOrder()
  // 改訂2: チケット閲覧を記録 (通知バッジの既読判定に使う)
  if (order.value) {
    try {
      await api.post(`/api/v1/orders/${orderId.value}/view`, { body: {} })
    } catch { /* silent: 通知精度を落とすだけ */ }
  }
})

async function fetchOrder() {
  loading.value = true
  fetchError.value = null
  try {
    order.value = await api.get<OrderDetail>(`/api/v1/orders/${orderId.value}`)
  } catch (err) {
    fetchError.value = errorMessageJa(err)
  } finally {
    loading.value = false
  }
}

// ─── Deadline edit (改訂2) ─────────────────────────
const editingDeadline = ref(false)
const deadlineDraft = ref('')
const deadlineLoading = ref(false)

function startEditDeadline() {
  if (!order.value) return
  deadlineDraft.value = order.value.desired_deadline
  editingDeadline.value = true
}

async function saveDeadline() {
  if (!deadlineDraft.value || !order.value) return
  deadlineLoading.value = true
  try {
    order.value = await api.patch<OrderDetail>(`/api/v1/orders/${orderId.value}/deadline`, {
      body: { desired_deadline: deadlineDraft.value },
    })
    editingDeadline.value = false
  } catch (err) {
    alert(errorMessageJa(err))
  } finally {
    deadlineLoading.value = false
  }
}

const canEditDeadline = computed(() => {
  if (!order.value) return false
  if (order.value.status === 'done' || order.value.status === 'cancelled') return false
  return isAdmin.value || isOwner.value
})

function formatDeadline(d: string | null | undefined): string {
  if (!d) return '-'
  return new Date(d).toLocaleDateString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

// ─── Role helpers ─────────────────────────────────
const isAdmin = computed(() => auth.role === 'admin')
const isCreator = computed(() => auth.role === 'creator' || auth.role === 'admin')
const isOwner = computed(() => order.value?.user_id === auth.user?.id)
const isAssignedCreator = computed(() => order.value?.assigned_creator_id === auth.user?.id)

// ─── Submit order (draft → open) ─────────────────
const submitLoading = ref(false)
async function submitOrder() {
  submitLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/submit`)
  } catch (err) { alert(errorMessageJa(err)) }
  finally { submitLoading.value = false }
}

// ─── Cancel ──────────────────────────────────────
const cancelLoading = ref(false)
async function cancelOrder() {
  if (!confirm('この発注をキャンセルしますか？')) return
  cancelLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/cancel`)
  } catch (err) { alert(errorMessageJa(err)) }
  finally { cancelLoading.value = false }
}

// ─── Message ─────────────────────────────────────
const msgContent = ref('')
const msgLoading = ref(false)
async function sendMessage() {
  if (!msgContent.value.trim()) return
  msgLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/message`, {
      body: { content: msgContent.value.trim() },
    })
    msgContent.value = ''
  } catch (err) { alert(errorMessageJa(err)) }
  finally { msgLoading.value = false }
}

// ─── Creator: respond ─────────────────────────────
const respondLoading = ref(false)
async function respond(response: 'accepted' | 'declined') {
  const label = response === 'accepted' ? '受諾' : '辞退'
  if (!confirm(`この発注を${label}しますか？`)) return
  respondLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/respond`, { body: { response } })
  } catch (err) { alert(errorMessageJa(err)) }
  finally { respondLoading.value = false }
}

// ─── Creator: submit file ─────────────────────────
const showSubmitFile = ref(false)
const submitFile = ref<File | null>(null)
const submitNote = ref('')
const submitFileLoading = ref(false)
const submitFileError = ref<string | null>(null)

async function executeSubmitFile() {
  if (!submitFile.value) { submitFileError.value = 'ファイルを選択してください。'; return }
  submitFileLoading.value = true
  submitFileError.value = null
  try {
    const fd = new FormData()
    fd.append('file', submitFile.value)
    fd.append('note', submitNote.value.trim() || '')
    const config = useRuntimeConfig()
    const data = await $fetch<OrderDetail>(`/api/v1/orders/${orderId.value}/submit-file`, {
      baseURL: config.public.apiBaseUrl as string,
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` },
      body: fd,
    })
    order.value = data
    showSubmitFile.value = false
    submitFile.value = null
    submitNote.value = ''
  } catch (err) {
    submitFileError.value = errorMessageJa(err)
  } finally {
    submitFileLoading.value = false
  }
}

// ─── User: download done file ─────────────────────
const dlLoading = ref(false)
async function downloadDoneFile() {
  dlLoading.value = true
  try {
    const baseURL = useRuntimeConfig().public.apiBaseUrl as string
    const res = await api.get<{ url: string }>(`/api/v1/orders/${orderId.value}/file-url`)
    const url = res.url.startsWith('http') ? res.url : `${baseURL}${res.url}`
    const a = document.createElement('a')
    a.href = url
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch (err) { alert(errorMessageJa(err)) }
  finally { dlLoading.value = false }
}

// ─── Admin: nominate ─────────────────────────────
const showNominate = ref(false)
const nominateIds = ref('')
const nominateLoading = ref(false)
const nominateError = ref<string | null>(null)

async function executeNominate() {
  const ids = nominateIds.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!ids.length) { nominateError.value = 'Creator ID を入力してください。'; return }
  nominateLoading.value = true
  nominateError.value = null
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/nominate`, { body: { creator_ids: ids } })
    showNominate.value = false
    nominateIds.value = ''
  } catch (err) { nominateError.value = errorMessageJa(err) }
  finally { nominateLoading.value = false }
}

// ─── Admin: assign ────────────────────────────────
const showAssign = ref(false)
const assignCreatorId = ref('')
const assignTokenCost = ref<number | null>(null)
const assignLoading = ref(false)
const assignError = ref<string | null>(null)

async function executeAssign() {
  if (!assignCreatorId.value.trim()) { assignError.value = 'Creator ID を入力してください。'; return }
  assignLoading.value = true
  assignError.value = null
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/assign`, {
      body: {
        creator_id: assignCreatorId.value.trim(),
        token_cost: assignTokenCost.value ?? null,
      },
    })
    showAssign.value = false
  } catch (err) { assignError.value = errorMessageJa(err) }
  finally { assignLoading.value = false }
}

// ─── Admin: reject ────────────────────────────────
const showReject = ref(false)
const rejectReason = ref('')
const rejectLoading = ref(false)
const rejectError = ref<string | null>(null)

async function executeReject() {
  if (!rejectReason.value.trim()) { rejectError.value = '理由を入力してください。'; return }
  rejectLoading.value = true
  rejectError.value = null
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/reject`, { body: { reason: rejectReason.value.trim() } })
    showReject.value = false
    rejectReason.value = ''
  } catch (err) { rejectError.value = errorMessageJa(err) }
  finally { rejectLoading.value = false }
}

// ─── Admin: done ──────────────────────────────────
const doneLoading = ref(false)
async function markDone() {
  if (!confirm('発注を完了にしますか？ token が消費されます。')) return
  doneLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/done`)
  } catch (err) { alert(errorMessageJa(err)) }
  finally { doneLoading.value = false }
}

// ─── Helpers ─────────────────────────────────────
const STATUS_LABEL: Record<string, string> = {
  draft: 'Draft', open: 'Open', recruiting: '募集中',
  assigned: 'アサイン済', reviewing: 'レビュー中', done: '完了', cancelled: 'キャンセル',
}
const STATUS_CLASS: Record<string, string> = {
  draft: 'bg-hairline-soft text-body',
  open: 'bg-primary/15 text-primary-active',
  recruiting: 'bg-primary/20 text-primary-active',
  assigned: 'bg-[#20b2aa22] text-[#0e7a74]',
  reviewing: 'bg-[#f0a84022] text-[#b07000]',
  done: 'bg-[#2ecc7122] text-[#1a9950]',
  cancelled: 'bg-accent/15 text-accent',
}
const KIND_CLASS: Record<string, string> = {
  comment: '',
  status_change: 'opacity-60 italic',
  submission: 'border-l-2 border-primary/40 pl-3',
  rejection: 'border-l-2 border-accent/40 pl-3',
  done: 'border-l-2 border-[#2ecc71]/50 pl-3',
}
function formatDate(iso: string) {
  return new Date(iso).toLocaleString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// candidate response label
const RESPONSE_LABEL: Record<string, string> = { pending: '未回答', accepted: '受諾', declined: '辞退' }
const RESPONSE_CLASS: Record<string, string> = {
  pending: 'text-muted',
  accepted: 'text-[#0e7a74]',
  declined: 'text-accent',
}

// My candidate row (for creator respond action)
const myCandidate = computed(() =>
  order.value?.candidates.find(c => c.creator_id === auth.user?.id) ?? null
)
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- Header -->
    <div class="flex shrink-0 items-center gap-3 pb-3 pt-5">
      <button class="text-muted hover:text-ink" @click="router.push('/orders')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h1 class="truncate text-[18px] font-normal tracking-[-0.0125em] text-ink">
            {{ order?.title ?? '…' }}
          </h1>
          <span
            v-if="order"
            class="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
            :class="STATUS_CLASS[order.status] ?? 'bg-hairline-soft text-body'"
          >{{ STATUS_LABEL[order.status] ?? order.status }}</span>
        </div>
        <p v-if="order" class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
          <span>{{ order.user_name }}</span>
          <template v-if="order.assigned_creator_name">
            <span>→</span>
            <span>{{ order.assigned_creator_name }}</span>
          </template>
          <span class="font-mono">{{ order.token_cost }} tk</span>
          <span>·</span>
          <span>作成 {{ formatDate(order.created_at) }}</span>
          <span>·</span>

          <!-- 希望締切 (改訂2: 編集可) -->
          <template v-if="editingDeadline">
            <input
              v-model="deadlineDraft"
              type="date"
              class="rounded border border-hairline-strong bg-white px-1.5 py-0.5 font-mono text-[10px] text-ink focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              class="rounded bg-primary px-1.5 py-0.5 text-[10px] text-white hover:bg-primary/80 disabled:opacity-50"
              :disabled="deadlineLoading"
              @click="saveDeadline"
            >保存</button>
            <button
              class="rounded px-1.5 py-0.5 text-[10px] text-muted hover:text-ink"
              @click="editingDeadline = false"
            >×</button>
          </template>
          <template v-else>
            <span>締切 <span class="font-mono">{{ formatDeadline(order.desired_deadline) }}</span></span>
            <button
              v-if="canEditDeadline"
              class="text-[10px] text-primary-active hover:underline"
              @click="startEditDeadline"
              title="希望締切日を変更"
            >編集</button>
          </template>
        </p>
      </div>
    </div>
    <div class="h-px shrink-0 bg-hairline-soft" />

    <!-- Loading -->
    <div v-if="loading" class="flex flex-1 items-center justify-center text-[13px] text-muted">読み込み中…</div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex flex-1 flex-col items-center justify-center gap-3">
      <p class="text-[13px] text-accent">{{ fetchError }}</p>
      <button class="rounded-md bg-ink px-4 py-1.5 text-[12px] text-canvas hover:bg-primary" @click="fetchOrder">再試行</button>
    </div>

    <!-- Content -->
    <div v-else-if="order" class="flex flex-1 gap-5 overflow-hidden py-4">

      <!-- Left: messages + reply -->
      <div class="flex flex-1 flex-col gap-3 overflow-hidden">

        <!-- Description -->
        <div v-if="order.description" class="card px-4 py-3">
          <p class="whitespace-pre-wrap text-[13px] text-body">{{ order.description }}</p>
        </div>

        <!-- Brief (structured hearing) -->
        <div v-if="order.brief" class="card px-4 py-4 space-y-4 text-[12px]">
          <p class="text-[10px] font-semibold text-ink/40 tracking-widest uppercase">サウンドブリーフ</p>

          <!-- 基本 -->
          <div class="space-y-1">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">基本</p>
            <div class="grid grid-cols-[80px_1fr] gap-y-1.5">
              <template v-if="order.brief.sound_type">
                <span class="text-muted">タイプ</span>
                <span class="text-body font-medium">{{ { bgm: 'BGM', se: 'SE', both: 'BGM + SE' }[order.brief.sound_type] ?? order.brief.sound_type }}</span>
              </template>
              <template v-if="order.brief.purpose">
                <span class="text-muted">用途</span>
                <span class="text-body">{{ { game: 'ゲーム', video: '映像', podcast: 'ポッドキャスト', other: 'その他' }[order.brief.purpose] ?? order.brief.purpose }}{{ order.brief.purpose_note ? ` — ${order.brief.purpose_note}` : '' }}</span>
              </template>
              <template v-if="order.brief.length_sec">
                <span class="text-muted">長さ</span>
                <span class="text-body">{{ order.brief.length_sec }}秒</span>
              </template>
            </div>
          </div>

          <!-- シーン (BGM) -->
          <div v-if="order.brief.bgm_scenes?.length" class="space-y-1">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">BGM シーン</p>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="s in order.brief.bgm_scenes"
                :key="s"
                class="rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] text-body border border-white/10"
              >{{ { battle: 'バトル/戦闘', boss: 'ボス戦', explore: '探索/フィールド', menu: 'メニュー/UI', title: 'タイトル', event: 'イベント/ムービー', ending: 'エンディング', ambient: 'アンビエント', other: 'その他' }[s] ?? s }}</span>
            </div>
            <p v-if="order.brief.bgm_loop !== undefined" class="text-muted mt-1">ループ: <span class="text-body">{{ order.brief.bgm_loop ? '必要' : '不要' }}</span></p>
            <p v-if="order.brief.bgm_note" class="text-body mt-1 whitespace-pre-wrap">{{ order.brief.bgm_note }}</p>
          </div>

          <!-- SE -->
          <div v-if="order.brief.se_trigger" class="space-y-1">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">SE 設計</p>
            <p><span class="text-muted">トリガー</span><span class="ml-2 text-body">{{ order.brief.se_trigger }}</span></p>
            <div v-if="order.brief.se_functions?.length" class="flex flex-wrap gap-1 mt-1">
              <span
                v-for="f in order.brief.se_functions"
                :key="f"
                class="rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] text-body border border-white/10"
              >{{ { success: '成功/達成', danger: '危険/警告', ui: 'UI操作', operation: '操作の手応え', immersion: '没入/演出', character: 'キャラクター感情' }[f] ?? f }}</span>
            </div>
          </div>

          <!-- 感情設計 -->
          <div v-if="order.brief.emotions_target?.length || order.brief.memory_impression" class="space-y-2">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">感情設計</p>
            <div v-if="order.brief.emotions_target?.length">
              <p class="text-muted mb-1">狙う感情</p>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="e in order.brief.emotions_target"
                  :key="e"
                  class="rounded-full bg-accent/15 px-2.5 py-0.5 text-[11px] text-accent border border-accent/20"
                >{{ { excitement: '高揚感/興奮', tension: '緊張感', fear: '恐怖/不安', relief: '安らぎ/安心', loneliness: '孤独感', grandeur: '壮大さ/圧倒感', speed: '疾走感', sadness: '哀愁/切なさ', mystery: '神秘/異世界感', achievement: '達成感', heaviness: '重厚感/威圧感', comfort: '心地よさ', euphoria: '爽快感', dread: 'じわじわとした恐怖', wonder: '驚き/発見の喜び' }[e] ?? e }}</span>
              </div>
            </div>
            <div v-if="order.brief.emotions_avoid?.length">
              <p class="text-muted mb-1">避けたい感情</p>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="e in order.brief.emotions_avoid"
                  :key="e"
                  class="rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] text-muted border border-white/10 line-through"
                >{{ { excitement: '高揚感/興奮', tension: '緊張感', fear: '恐怖/不安', relief: '安らぎ/安心', loneliness: '孤独感', grandeur: '壮大さ/圧倒感', speed: '疾走感', sadness: '哀愁/切なさ', mystery: '神秘/異世界感', achievement: '達成感', heaviness: '重厚感/威圧感', comfort: '心地よさ', euphoria: '爽快感', dread: 'じわじわとした恐怖', wonder: '驚き/発見の喜び' }[e] ?? e }}</span>
              </div>
            </div>
            <p v-if="order.brief.memory_impression" class="mt-2 rounded-lg bg-surface-2/60 border border-white/10 px-3 py-2 text-[12px] text-body italic whitespace-pre-wrap">「{{ order.brief.memory_impression }}」</p>
          </div>

          <!-- テクスチャ -->
          <div v-if="[order.brief.tx_organic_electronic, order.brief.tx_melody_rhythm, order.brief.tx_warm_cold, order.brief.tx_sparse_dense, order.brief.tx_static_dynamic].some(v => v && v !== '')" class="space-y-1">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">テクスチャ方向</p>
            <div class="grid grid-cols-[120px_1fr] gap-y-1 text-[11px]">
              <template v-if="order.brief.tx_organic_electronic">
                <span class="text-muted">有機的 ↔ 電子的</span>
                <span class="text-body">{{ { organic: '← 有機的 / 生楽器', mid: 'どちらでも', electronic: '電子的 / シンセ →' }[order.brief.tx_organic_electronic] }}</span>
              </template>
              <template v-if="order.brief.tx_melody_rhythm">
                <span class="text-muted">メロディ ↔ リズム</span>
                <span class="text-body">{{ { melody: '← メロディ重視', mid: 'どちらでも', rhythm: 'リズム重視 →' }[order.brief.tx_melody_rhythm] }}</span>
              </template>
              <template v-if="order.brief.tx_warm_cold">
                <span class="text-muted">温かい ↔ 冷たい</span>
                <span class="text-body">{{ { warm: '← 温かい / 柔らかい', mid: 'どちらでも', cold: '冷たい / 無機質 →' }[order.brief.tx_warm_cold] }}</span>
              </template>
              <template v-if="order.brief.tx_sparse_dense">
                <span class="text-muted">シンプル ↔ 重厚</span>
                <span class="text-body">{{ { sparse: '← シンプル / 余白', mid: 'どちらでも', dense: '重厚 / 音多い →' }[order.brief.tx_sparse_dense] }}</span>
              </template>
              <template v-if="order.brief.tx_static_dynamic">
                <span class="text-muted">静的 ↔ 激しい</span>
                <span class="text-body">{{ { static: '← 静的 / 落ち着いた', mid: 'どちらでも', dynamic: '激しい / 展開多い →' }[order.brief.tx_static_dynamic] }}</span>
              </template>
            </div>
          </div>

          <!-- 参考音源 -->
          <div v-if="order.brief.reference_urls || order.brief.reference_elements?.length || order.brief.reference_avoid" class="space-y-1.5">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">参考音源</p>
            <p v-if="order.brief.reference_urls" class="text-body whitespace-pre-wrap text-[11px] break-all">{{ order.brief.reference_urls }}</p>
            <div v-if="order.brief.reference_elements?.length" class="flex flex-wrap gap-1">
              <span class="text-muted mr-1">参考要素:</span>
              <span
                v-for="r in order.brief.reference_elements"
                :key="r"
                class="rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] text-body border border-white/10"
              >{{ { atmosphere: '空気感/雰囲気', bass: '低音/ベース感', progression: '展開/構成', tempo: 'テンポ/グルーヴ', timbre: '音色/サウンドデザイン', melody: 'メロディライン', rhythm: 'リズムパターン', density: '音の密度/空間感' }[r] ?? r }}</span>
            </div>
            <p v-if="order.brief.reference_avoid" class="text-muted">避けたい要素: <span class="text-body">{{ order.brief.reference_avoid }}</span></p>
          </div>

          <!-- 技術仕様 -->
          <div v-if="order.brief.delivery_format || order.brief.deadline || order.brief.budget_range || order.brief.note" class="space-y-1">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">技術仕様</p>
            <div class="grid grid-cols-[80px_1fr] gap-y-1">
              <template v-if="order.brief.delivery_format">
                <span class="text-muted">納品形式</span>
                <span class="text-body">{{ { wav48k24b: '48kHz / 24bit', wav44k16b: '44.1kHz / 16bit', any: 'どちらでも可' }[order.brief.delivery_format] ?? order.brief.delivery_format }}</span>
              </template>
              <template v-if="order.brief.deadline">
                <span class="text-muted">締切</span>
                <span class="text-body">{{ order.brief.deadline }}</span>
              </template>
              <template v-if="order.brief.budget_range">
                <span class="text-muted">予算感</span>
                <span class="text-body">{{ { '5000': '〜¥5,000', '10000': '〜¥10,000', negotiable: '要相談' }[order.brief.budget_range] ?? order.brief.budget_range }}</span>
              </template>
            </div>
            <p v-if="order.brief.note" class="mt-1 text-body whitespace-pre-wrap">{{ order.brief.note }}</p>
          </div>
        </div>

        <!-- Messages -->
        <div class="flex-1 overflow-y-auto space-y-2">
          <div
            v-for="msg in order.messages"
            :key="msg.id"
            class="card px-4 py-2.5"
            :class="KIND_CLASS[msg.kind] ?? ''"
          >
            <div class="flex items-center gap-2 text-[11px] text-muted">
              <span class="font-medium text-body-strong">{{ msg.sender_name ?? 'System' }}</span>
              <span>{{ formatDate(msg.created_at) }}</span>
            </div>
            <p v-if="msg.content" class="mt-1 whitespace-pre-wrap text-[13px] text-ink">{{ msg.content }}</p>
          </div>
          <div v-if="order.messages.length === 0" class="py-6 text-center text-[12px] text-muted">メッセージはまだありません。</div>
        </div>

        <!-- Reply box (active orders only) -->
        <div
          v-if="order.status !== 'done' && order.status !== 'cancelled' && order.status !== 'draft'"
          class="card shrink-0 px-3 py-2"
        >
          <textarea
            v-model="msgContent"
            rows="2"
            placeholder="メッセージを入力…"
            class="w-full resize-none bg-transparent text-[13px] text-ink outline-none placeholder:text-muted"
            @keydown.ctrl.enter.prevent="sendMessage"
          />
          <div class="mt-1.5 flex justify-end">
            <button
              class="rounded-md bg-ink px-3 py-1 text-[11px] font-medium text-canvas hover:bg-primary disabled:opacity-50"
              :disabled="msgLoading || !msgContent.trim()"
              @click="sendMessage"
            >{{ msgLoading ? '…' : '送信' }}</button>
          </div>
        </div>
      </div>

      <!-- Right: action panel -->
      <div class="w-52 shrink-0 space-y-3">

        <!-- Order owner actions -->
        <div v-if="isOwner" class="card px-4 py-3 space-y-2">
          <p class="text-[11px] font-semibold uppercase tracking-widest text-muted">あなたの操作</p>

          <!-- Submit (draft → open) -->
          <button
            v-if="order.status === 'draft'"
            class="w-full rounded-md bg-ink px-3 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary disabled:opacity-50"
            :disabled="submitLoading"
            @click="submitOrder"
          >{{ submitLoading ? '…' : '発注する' }}</button>

          <!-- Download done file -->
          <button
            v-if="order.status === 'done'"
            class="w-full rounded-md bg-[#2ecc71] px-3 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50"
            :disabled="dlLoading"
            @click="downloadDoneFile"
          >{{ dlLoading ? '…' : '音源をDL' }}</button>

          <!-- Cancel -->
          <button
            v-if="!['done','cancelled'].includes(order.status)"
            class="w-full rounded-md border border-hairline-strong px-3 py-1.5 text-[12px] text-muted hover:border-accent hover:text-accent disabled:opacity-50"
            :disabled="cancelLoading"
            @click="cancelOrder"
          >{{ cancelLoading ? '…' : 'キャンセル' }}</button>
        </div>

        <!-- Creator actions -->
        <div v-if="isCreator && !isAdmin && myCandidate && order.status === 'recruiting'" class="card px-4 py-3 space-y-2">
          <p class="text-[11px] font-semibold uppercase tracking-widest text-muted">クリエイター</p>
          <p class="text-[11px] text-muted">
            返答:
            <span :class="RESPONSE_CLASS[myCandidate.response_status]">
              {{ RESPONSE_LABEL[myCandidate.response_status] }}
            </span>
          </p>
          <template v-if="myCandidate.response_status === 'pending'">
            <button
              class="w-full rounded-md bg-[#20b2aa] px-3 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50"
              :disabled="respondLoading"
              @click="respond('accepted')"
            >受諾</button>
            <button
              class="w-full rounded-md border border-hairline-strong px-3 py-1.5 text-[12px] text-muted hover:border-accent hover:text-accent disabled:opacity-50"
              :disabled="respondLoading"
              @click="respond('declined')"
            >辞退</button>
          </template>
        </div>

        <!-- Creator: submit file -->
        <div v-if="(isCreator && !isAdmin && isAssignedCreator && order.status === 'assigned') || (isAdmin && order.status === 'assigned')" class="card px-4 py-3 space-y-2">
          <p class="text-[11px] font-semibold uppercase tracking-widest text-muted">音源提出</p>
          <button
            class="w-full rounded-md bg-primary px-3 py-1.5 text-[12px] font-medium text-white hover:opacity-90"
            @click="showSubmitFile = true"
          >ファイルを提出</button>
        </div>

        <!-- Admin actions -->
        <div v-if="isAdmin" class="card px-4 py-3 space-y-2">
          <p class="text-[11px] font-semibold uppercase tracking-widest text-muted">Admin</p>

          <button
            v-if="['open','recruiting'].includes(order.status)"
            class="w-full rounded-md bg-ink px-3 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary"
            @click="showNominate = true"
          >クリエイター指名</button>

          <button
            v-if="['open','recruiting'].includes(order.status)"
            class="w-full rounded-md border border-[#20b2aa55] px-3 py-1.5 text-[12px] font-medium text-[#0e7a74] hover:bg-[#20b2aa15]"
            @click="showAssign = true"
          >アサイン確定</button>

          <button
            v-if="order.status === 'reviewing'"
            class="w-full rounded-md bg-[#2ecc71] px-3 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50"
            :disabled="doneLoading"
            @click="markDone"
          >{{ doneLoading ? '…' : '完了にする' }}</button>

          <button
            v-if="order.status === 'reviewing'"
            class="w-full rounded-md border border-accent/40 px-3 py-1.5 text-[12px] text-accent hover:bg-accent/10"
            @click="showReject = true"
          >差し戻し</button>

          <button
            v-if="!['done','cancelled'].includes(order.status)"
            class="w-full rounded-md border border-hairline-strong px-3 py-1.5 text-[12px] text-muted hover:border-accent hover:text-accent disabled:opacity-50"
            :disabled="cancelLoading"
            @click="cancelOrder"
          >キャンセル</button>
        </div>

        <!-- Candidates (admin/creator view) -->
        <div v-if="(isAdmin || isCreator) && order.candidates.length" class="card px-4 py-3">
          <p class="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted">候補クリエイター</p>
          <div class="space-y-1.5">
            <div v-for="c in order.candidates" :key="c.id" class="flex items-center justify-between">
              <span class="text-[12px] text-ink">{{ c.creator_name }}</span>
              <span class="font-mono text-[10px]" :class="RESPONSE_CLASS[c.response_status]">
                {{ RESPONSE_LABEL[c.response_status] }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Modals ───────────────────────────────────── -->
    <Teleport to="body">

      <!-- Submit file -->
      <Transition name="modal">
        <div v-if="showSubmitFile" class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24 backdrop-blur-sm" @click.self="showSubmitFile = false">
          <div class="card mx-4 w-full max-w-[480px] p-6">
            <h2 class="mb-4 text-[15px] font-semibold text-ink">音源を提出</h2>
            <label class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-hairline-strong bg-white/40 px-6 py-6 text-center transition-colors hover:border-primary">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="text-muted">
                <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
              </svg>
              <span class="text-[13px] text-ink">{{ submitFile?.name ?? '.wav ファイルを選択' }}</span>
              <input type="file" accept=".wav,audio/wav" class="hidden" @change="(e) => { submitFile = (e.target as HTMLInputElement).files?.[0] ?? null }" />
            </label>
            <textarea v-model="submitNote" rows="2" placeholder="コメント（任意）" class="mt-3 w-full resize-none rounded-md border border-hairline-strong bg-white/60 px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-primary" />
            <p v-if="submitFileError" class="mt-2 text-[12px] text-accent">{{ submitFileError }}</p>
            <div class="mt-4 flex justify-end gap-2">
              <button class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] text-body-strong hover:text-ink" @click="showSubmitFile = false">やめる</button>
              <button class="rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary disabled:opacity-50" :disabled="submitFileLoading" @click="executeSubmitFile">
                {{ submitFileLoading ? '提出中…' : '提出する' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Nominate -->
      <Transition name="modal">
        <div v-if="showNominate" class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24 backdrop-blur-sm" @click.self="showNominate = false">
          <div class="card mx-4 w-full max-w-[480px] p-6">
            <h2 class="mb-4 text-[15px] font-semibold text-ink">クリエイター指名</h2>
            <p class="mb-2 text-[12px] text-muted">Creator ID を1行につき1件入力してください。</p>
            <textarea v-model="nominateIds" rows="4" placeholder="uuid&#10;uuid&#10;..." class="w-full resize-none rounded-md border border-hairline-strong bg-white/60 px-3 py-2 font-mono text-[12px] text-ink outline-none placeholder:text-muted focus:border-primary" />
            <p v-if="nominateError" class="mt-2 text-[12px] text-accent">{{ nominateError }}</p>
            <div class="mt-4 flex justify-end gap-2">
              <button class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] text-body-strong hover:text-ink" @click="showNominate = false">やめる</button>
              <button class="rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary disabled:opacity-50" :disabled="nominateLoading" @click="executeNominate">
                {{ nominateLoading ? '…' : '指名する' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Assign -->
      <Transition name="modal">
        <div v-if="showAssign" class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24 backdrop-blur-sm" @click.self="showAssign = false">
          <div class="card mx-4 w-full max-w-[480px] p-6">
            <h2 class="mb-4 text-[15px] font-semibold text-ink">アサイン確定</h2>
            <div class="space-y-3">
              <div>
                <label class="mb-1 block text-[12px] font-medium text-body-strong">Creator ID</label>
                <input v-model="assignCreatorId" type="text" class="w-full rounded-md border border-hairline-strong bg-white/60 px-3 py-2 font-mono text-[12px] text-ink outline-none focus:border-primary" />
              </div>
              <div>
                <label class="mb-1 block text-[12px] font-medium text-body-strong">token 数（変更する場合）</label>
                <input v-model.number="assignTokenCost" type="number" min="1" placeholder="空欄=変更なし" class="w-32 rounded-md border border-hairline-strong bg-white/60 px-3 py-2 font-mono text-[12px] text-ink outline-none focus:border-primary" />
              </div>
            </div>
            <p v-if="assignError" class="mt-2 text-[12px] text-accent">{{ assignError }}</p>
            <div class="mt-4 flex justify-end gap-2">
              <button class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] text-body-strong hover:text-ink" @click="showAssign = false">やめる</button>
              <button class="rounded-md bg-[#20b2aa] px-4 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50" :disabled="assignLoading" @click="executeAssign">
                {{ assignLoading ? '…' : 'アサイン確定' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Reject -->
      <Transition name="modal">
        <div v-if="showReject" class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24 backdrop-blur-sm" @click.self="showReject = false">
          <div class="card mx-4 w-full max-w-[480px] p-6">
            <h2 class="mb-4 text-[15px] font-semibold text-ink">差し戻し</h2>
            <textarea v-model="rejectReason" rows="3" placeholder="差し戻しの理由" class="w-full resize-none rounded-md border border-hairline-strong bg-white/60 px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-primary" />
            <p v-if="rejectError" class="mt-2 text-[12px] text-accent">{{ rejectError }}</p>
            <div class="mt-4 flex justify-end gap-2">
              <button class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] text-body-strong hover:text-ink" @click="showReject = false">やめる</button>
              <button class="rounded-md bg-accent px-4 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50" :disabled="rejectLoading" @click="executeReject">
                {{ rejectLoading ? '…' : '差し戻す' }}
              </button>
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
