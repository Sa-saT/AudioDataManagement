<script setup lang="ts">
import type { OrderBrief as WizardBrief } from '~/components/OrderBriefWizard.vue'
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
  // 改訂2.2: user が受け取った時刻。null なら未受け取り
  closed_at: string | null
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
  // NOTIFICATION_SPEC §9.1 9-A11: WaveformPlayer 用 peaks v2 ({n,max,min,rms})
  submission_peaks: { n: number; max: number[]; min: number[]; rms: number[] } | null
  notified_at: string | null
  created_at: string
  updated_at: string
}

type int = number

useHead(computed(() => ({ title: `Commission — Pathfinder` })))

// ─── Fetch ────────────────────────────────────────
const order = ref<OrderDetail | null>(null)
const loading = ref(false)
const fetchError = ref<string | null>(null)

onMounted(async () => {
  auth.hydrate()
  // 9-A4: auth.role 確定後に briefView の既定を適用
  applyBriefViewDefault()
  await fetchOrder()
  await fetchMemos()
  // 改訂2: チケット閲覧を記録 (通知バッジの既読判定に使う)
  if (order.value) {
    try {
      await api.post(`/api/v1/orders/${orderId.value}/view`, { body: {} })
    } catch { /* silent: 通知精度を落とすだけ */ }
    // 改訂2.1: 編集履歴を取得 (highlight + 履歴モーダル用)
    await fetchBriefEdits()
    // 改訂2.2: 音源プレビュー URL を取得 (reviewing / done のみ)
    if (hasSubmission.value) {
      await fetchSubmissions()
      await loadPreview()
    }
    // チャット最下部までスクロール (LINE 風)
    await scrollToBottom()
  }
})

// status 変化で preview を再ロード + 履歴も再取得 (新規 submission で版数増加)
watch(() => order.value?.status, async (s) => {
  if (s && ['reviewing', 'done'].includes(s)) {
    await fetchSubmissions()
    await loadPreview()
  } else {
    audioPreviewUrl.value = null
    submissions.value = []
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

// ─── Brief edit after submit (改訂2.1) ─────────────
interface BriefEditHistoryItem {
  id: string
  editor_id: string | null
  editor_name: string | null
  field_path: string
  field_label: string
  old_value: unknown
  new_value: unknown
  created_at: string
}

const briefEdits = ref<BriefEditHistoryItem[]>([])
const showBriefEditWizard = ref(false)
const showBriefHistory = ref(false)
const briefEditError = ref<string | null>(null)

async function fetchBriefEdits() {
  if (!order.value) return
  try {
    briefEdits.value = await api.get<BriefEditHistoryItem[]>(`/api/v1/orders/${orderId.value}/brief-edits`)
  } catch { /* silent: 履歴は補助情報 */ }
}

// ─── REDMINE 風タイトル分離 (改訂2.2) ─────────────
// 件名 = `title` から ` #N` 末尾を除去 (旧 order 互換)。新 order は最初から #N 無し
const subjectDisplay = computed(() => {
  const t = order.value?.title ?? '…'
  return t.replace(/\s*#\d+\s*$/, '')
})

// ─── 音源プレビュー (改訂2.2) + バージョン管理 (改訂2.5 / 9-A3) ───────────────
const audioPreviewUrl = ref<string | null>(null)
const audioPreviewLoading = ref(false)
const audioPreviewError = ref<string | null>(null)
const hasSubmission = computed(() =>
  order.value && ['reviewing', 'done'].includes(order.value.status),
)

interface SubmissionVersion {
  version: number
  message_id: string
  sender_id: string | null
  sender_name: string | null
  note: string | null
  file_available: boolean
  peaks: { n: number; max: number[]; min: number[]; rms: number[] } | null
  rejected: boolean
  rejection_reason: string | null
  created_at: string
}

const submissions = ref<SubmissionVersion[]>([])
const selectedVersion = ref<number>(0)  // 0 = latest

async function fetchSubmissions() {
  if (!order.value) return
  try {
    submissions.value = await api.get<SubmissionVersion[]>(
      `/api/v1/orders/${orderId.value}/submissions`,
    )
    // 初期選択: 最新 version (リストの末尾)
    if (submissions.value.length > 0) {
      selectedVersion.value = submissions.value[submissions.value.length - 1].version
    }
  } catch { /* silent: バージョン履歴は補助情報 */ }
}

async function loadPreview(version = 0) {
  if (!hasSubmission.value) return
  audioPreviewLoading.value = true
  audioPreviewError.value = null
  try {
    const { url } = await api.get<{ url: string }>(
      `/api/v1/orders/${orderId.value}/submission-stream-url`,
      { query: { start: 0, version } },
    )
    const config = useRuntimeConfig()
    const base = config.public.apiBaseUrl as string
    audioPreviewUrl.value = url.startsWith('http') ? url : `${base}${url}`
  } catch (err) {
    audioPreviewError.value = errorMessageJa(err)
  } finally {
    audioPreviewLoading.value = false
  }
}

function selectVersion(v: number) {
  selectedVersion.value = v
  // version=0 で最新が確実に取れるよう、末尾なら 0、それ以外は具体的な v を渡す
  const isLatest = submissions.value.length > 0 &&
    v === submissions.value[submissions.value.length - 1].version
  loadPreview(isLatest ? 0 : v)
}

function formatVersionTime(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─── 受け取る (close) (改訂2.2) ─────────────────
const closeLoading = ref(false)
const canReceive = computed(() => {
  if (!order.value) return false
  if (order.value.status !== 'done') return false
  if (order.value.closed_at) return false
  return isOwner.value
})

async function receiveAndClose() {
  if (!order.value) return
  const cost = order.value.token_cost
  if (!confirm(`この音源を受け取りますか?\n\n${cost} token が消費され、creator への支払いが確定します。\n受け取り後はアーカイブに移動します。`)) return
  closeLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/close`, { body: {} })
  } catch (err) { alert(errorMessageJa(err)) }
  finally { closeLoading.value = false }
}

// ─── チャット添付による音源提出 (改訂2.2) ────────
// 既存の showSubmitFile モーダルを撤去し、チャット欄で直接添付して提出する
const attachInputRef = ref<HTMLInputElement | null>(null)
const attachedFile = ref<File | null>(null)
const attachLoading = ref(false)

function pickAttach() {
  attachInputRef.value?.click()
}
function onAttachChange(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (!f.name.toLowerCase().endsWith('.wav')) {
    alert('音源は .wav (PCM) のみ受け付けます')
    return
  }
  attachedFile.value = f
}
function clearAttach() {
  attachedFile.value = null
  if (attachInputRef.value) attachInputRef.value.value = ''
}

const canAttachSubmit = computed(() =>
  order.value?.status === 'assigned' && isAssignedCreator.value,
)

async function sendChat() {
  // 添付あり → submit-file (creator が音源提出)、なし → 通常メッセージ送信
  if (attachedFile.value && canAttachSubmit.value) {
    attachLoading.value = true
    try {
      const fd = new FormData()
      fd.append('file', attachedFile.value)
      fd.append('note', msgContent.value.trim() || '音源を提出しました。')
      order.value = await api.post<OrderDetail>(
        `/api/v1/orders/${orderId.value}/submit-file`, { body: fd },
      )
      clearAttach()
      msgContent.value = ''
    } catch (err) { alert(errorMessageJa(err)) }
    finally { attachLoading.value = false }
    return
  }
  await sendMessage()
}

// 編集されたことのある field 一覧 (highlight 用)
const editedFieldSet = computed(() => new Set(briefEdits.value.map(e => e.field_path)))

// 各 field の最終編集時刻 (ホバー表示用)
const fieldLastEditedAt = computed(() => {
  const m = new Map<string, string>()
  for (const e of briefEdits.value) {
    if (!m.has(e.field_path)) m.set(e.field_path, e.created_at)
  }
  return m
})

// brief 編集可能かどうか (open/recruiting/assigned かつ owner or admin)
const canEditBrief = computed(() => {
  const o = order.value
  if (!o) return false
  if (!['open', 'recruiting', 'assigned'].includes(o.status)) return false
  return isOwner.value || isAdmin.value
})

function fieldHighlightClass(field: string): string {
  return editedFieldSet.value.has(field)
    ? 'rounded-md bg-accent/10 px-1.5 py-0.5 -mx-1.5'
    : ''
}

function openBriefEditWizard() {
  briefEditError.value = null
  showBriefEditWizard.value = true
}

async function submitBriefEdit(payload: { brief: WizardBrief; desired_deadline: string }) {
  briefEditError.value = null
  try {
    order.value = await api.patch<OrderDetail>(
      `/api/v1/orders/${orderId.value}/brief-after-submit`,
      { body: { brief: payload.brief } },
    )
    showBriefEditWizard.value = false
    await fetchBriefEdits()
    // 締切も変わっていれば反映 (別 API)
    if (order.value.desired_deadline !== payload.desired_deadline) {
      try {
        order.value = await api.patch<OrderDetail>(
          `/api/v1/orders/${orderId.value}/deadline`,
          { body: { desired_deadline: payload.desired_deadline } },
        )
      } catch { /* deadline 失敗は別 toast 化したいが今回はサイレント */ }
    }
  } catch (err) {
    briefEditError.value = errorMessageJa(err)
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

// ─── 9-A4: クリエイター視点 brief 表示 ────────────────
// role=creator は creator view、user は user view、admin は creator view を既定
// localStorage に保存して次回も復元
const BRIEF_VIEW_KEY = 'pathfinder.briefView'
type BriefView = 'user' | 'creator'
const briefView = ref<BriefView>('creator')  // 仮値、auth.hydrate 後に正値を再設定
function applyBriefViewDefault() {
  if (typeof window === 'undefined') return
  const saved = localStorage.getItem(BRIEF_VIEW_KEY) as BriefView | null
  briefView.value = saved ?? (auth.role === 'user' ? 'user' : 'creator')
}
function toggleBriefView() {
  briefView.value = briefView.value === 'creator' ? 'user' : 'creator'
  if (typeof window !== 'undefined') localStorage.setItem(BRIEF_VIEW_KEY, briefView.value)
}
// 締切までの残日数 (creator view 用)
const daysToDeadline = computed(() => {
  if (!order.value?.desired_deadline) return null
  const dl = new Date(order.value.desired_deadline)
  const diff = Math.ceil((dl.getTime() - Date.now()) / 86400000)
  return diff
})
// tx_* スライダー位置 (0〜100%)
function txPosition(value: string | undefined, left: string, mid: string, right: string): number {
  if (value === left) return 10
  if (value === mid) return 50
  if (value === right) return 90
  return 50
}

// ─── 改訂2.4: 共有メモ ─────────────────────────────
interface MemoOut {
  author_kind: 'admin' | 'creator'
  content: string
  author_name: string | null
  updated_at: string
}
interface MemosResponse {
  admin: MemoOut | null
  creator: MemoOut | null
  can_edit_admin: boolean
  can_edit_creator: boolean
}
const memosState = ref<MemosResponse>({
  admin: null, creator: null, can_edit_admin: false, can_edit_creator: false,
})
const canViewMemos = computed(() => isAdmin.value || isAssignedCreator.value)

async function fetchMemos() {
  if (!order.value || !canViewMemos.value) return
  try {
    memosState.value = await api.get<MemosResponse>(`/api/v1/orders/${orderId.value}/memos`)
  } catch { /* silent: メモは補助情報 */ }
}

const memoEditOpen = ref<'admin' | 'creator' | null>(null)
const memoEditContent = ref('')
const memoSaving = ref(false)

function openMemoEdit(kind: 'admin' | 'creator') {
  memoEditOpen.value = kind
  memoEditContent.value = (kind === 'admin' ? memosState.value.admin?.content : memosState.value.creator?.content) ?? ''
}
function closeMemoEdit() {
  memoEditOpen.value = null
  memoEditContent.value = ''
}
async function saveMemo() {
  if (!memoEditOpen.value) return
  memoSaving.value = true
  try {
    await api.put(`/api/v1/orders/${orderId.value}/memo`, {
      body: { content: memoEditContent.value },
    })
    await fetchMemos()
    closeMemoEdit()
  } catch (err) { alert(errorMessageJa(err)) }
  finally { memoSaving.value = false }
}

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
const messagesRef = ref<HTMLDivElement | null>(null)
// brief / memo / submission / messages を一本に貫通させるスクロール参照
const contentScrollRef = ref<HTMLDivElement | null>(null)

async function sendMessage() {
  if (!msgContent.value.trim()) return
  msgLoading.value = true
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/message`, {
      body: { content: msgContent.value.trim() },
    })
    msgContent.value = ''
    await scrollToBottom()
  } catch (err) { alert(errorMessageJa(err)) }
  finally { msgLoading.value = false }
}

// ─── LINE 風チャット表示ヘルパ (改訂2.3) ──────────
function isMyMessage(m: Message): boolean {
  return !!(m.sender_id && auth.user?.id && m.sender_id === auth.user.id)
}
function shouldShowAvatar(m: Message, i: number): boolean {
  // 連続発言は最初のみアバター/名前を表示
  if (i === 0) return true
  const prev = order.value?.messages[i - 1]
  if (!prev) return true
  if (prev.sender_id !== m.sender_id) return true
  if (prev.kind !== m.kind) return true
  // 5分以上空けば改めて表示
  const dt = new Date(m.created_at).getTime() - new Date(prev.created_at).getTime()
  return dt > 5 * 60 * 1000
}
function avatarLetter(m: Message): string {
  if (!m.sender_name) return 'S'
  return m.sender_name.charAt(0).toUpperCase()
}
function avatarClass(m: Message): string {
  if (!m.sender_id) return 'bg-hairline-soft text-muted'  // system
  if (isMyMessage(m)) return 'bg-primary text-white'
  // 発注者(user) / creator / admin を識別
  if (m.sender_id === order.value?.user_id) return 'bg-[#807d72] text-white'  // user
  if (m.sender_id === order.value?.assigned_creator_id) return 'bg-[#20b2aa] text-white'  // creator
  return 'bg-accent text-white'  // admin など
}
function senderLabel(m: Message): string {
  if (m.kind === 'brief_edit') return 'System (Brief Bot)'
  if (!m.sender_name) return 'System'
  if (m.sender_id === order.value?.user_id) return `${m.sender_name} (発注者)`
  if (m.sender_id === order.value?.assigned_creator_id) return `${m.sender_name} (creator)`
  return m.sender_name
}
function bubbleClass(m: Message): string {
  if (isMyMessage(m)) return 'bg-primary text-white shadow-sm'
  return 'bg-surface-strong/60 text-ink shadow-sm'
}
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
}
async function scrollToBottom() {
  await nextTick()
  // 親スクロール (brief 〜 messages を貫通) を下端へ
  const scroll = contentScrollRef.value
  if (scroll) scroll.scrollTop = scroll.scrollHeight
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

// ─── Admin: nominate (改訂2.2: creator 一覧 + ランクフィルタ + 複数選択) ────
interface AdminUserItem {
  id: string
  username: string
  role: string
  rank: string | null
  display_name: string | null
}
const allCreators = ref<AdminUserItem[]>([])
const showNominate = ref(false)
const nominateLoading = ref(false)
const nominateError = ref<string | null>(null)
const nominateSelected = ref<Set<string>>(new Set())
const nominateRankFilter = ref<Set<string>>(new Set(['bronze', 'silver', 'gold', 'platinum']))
const nominateSearch = ref('')

async function loadCreators() {
  if (allCreators.value.length > 0) return
  try {
    const all = await api.get<AdminUserItem[]>('/api/v1/admin/users')
    allCreators.value = all.filter(u => u.role === 'creator')
  } catch (err) { nominateError.value = errorMessageJa(err) }
}

async function openNominateModal() {
  nominateError.value = null
  nominateSelected.value = new Set()
  nominateSearch.value = ''
  showNominate.value = true
  await loadCreators()
}

const RANK_LABEL: Record<string, string> = {
  bronze: 'Bronze ¥100', silver: 'Silver ¥200', gold: 'Gold ¥400', platinum: 'Platinum ¥800',
}
const RANK_CHIP: Record<string, string> = {
  bronze: 'bg-[#cd7f3220] text-[#8b5a2b]',
  silver: 'bg-[#c0c0c022] text-[#6b6b6b]',
  gold:   'bg-[#ffd70022] text-[#a07900]',
  platinum: 'bg-[#e5e4e220] text-[#5b6770]',
}

const filteredCreators = computed(() => {
  const q = nominateSearch.value.trim().toLowerCase()
  return allCreators.value.filter(c => {
    const rank = c.rank ?? ''
    if (!nominateRankFilter.value.has(rank)) return false
    if (q && !(c.username.toLowerCase().includes(q) || (c.display_name ?? '').toLowerCase().includes(q))) return false
    return true
  })
})

function toggleRankFilter(rank: string) {
  if (nominateRankFilter.value.has(rank)) nominateRankFilter.value.delete(rank)
  else nominateRankFilter.value.add(rank)
}
function toggleNominate(id: string) {
  if (nominateSelected.value.has(id)) nominateSelected.value.delete(id)
  else nominateSelected.value.add(id)
}

async function executeNominate() {
  const ids = Array.from(nominateSelected.value)
  if (!ids.length) { nominateError.value = 'Creator を1人以上選択してください。'; return }
  nominateLoading.value = true
  nominateError.value = null
  try {
    order.value = await api.post<OrderDetail>(`/api/v1/orders/${orderId.value}/nominate`, { body: { creator_ids: ids } })
    showNominate.value = false
    nominateSelected.value = new Set()
  } catch (err) { nominateError.value = errorMessageJa(err) }
  finally { nominateLoading.value = false }
}

// ─── Admin: assign (改訂2.2: 候補一覧から選択) ───
const showAssign = ref(false)
const assignCreatorId = ref('')
const assignTokenCost = ref<number | null>(null)
const assignLoading = ref(false)
const assignError = ref<string | null>(null)

// accepted な候補を優先表示、pending は薄く
const candidatesForAssign = computed(() => {
  const cs = order.value?.candidates ?? []
  return [
    ...cs.filter(c => c.response_status === 'accepted'),
    ...cs.filter(c => c.response_status === 'pending'),
  ]
})

function openAssignModal() {
  assignError.value = null
  // accepted な候補が1人だけならデフォルト選択
  const accepted = order.value?.candidates.filter(c => c.response_status === 'accepted') ?? []
  assignCreatorId.value = accepted.length === 1 ? accepted[0]!.creator_id : ''
  assignTokenCost.value = null
  showAssign.value = true
}

async function executeAssign() {
  if (!assignCreatorId.value.trim()) { assignError.value = 'Creator を1人選択してください。'; return }
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
  brief_edit: 'border-l-2 border-accent/60 bg-accent/5 pl-3',
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
      <button
        class="flex shrink-0 items-center justify-center text-ink/70 transition-colors hover:text-ink"
        title="Commission 一覧に戻る"
        @click="router.push('/orders')"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <div class="min-w-0 flex-1">
        <!-- 改訂2.2: REDMINE 風 件名 / ID 分離表示 -->
        <div class="flex items-center gap-3">
          <span
            v-if="order"
            class="shrink-0 rounded-md bg-ink/5 px-2 py-0.5 font-mono text-[12px] font-semibold text-ink"
            title="チケットID"
          >#{{ order.serial }}</span>
          <h1 class="min-w-0 flex-1 truncate text-[16px] font-normal tracking-[-0.0125em] text-ink" title="件名">
            {{ subjectDisplay }}
          </h1>
          <span
            v-if="order"
            class="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
            :class="STATUS_CLASS[order.status] ?? 'bg-hairline-soft text-body'"
          >{{ STATUS_LABEL[order.status] ?? order.status }}</span>
          <span
            v-if="order?.closed_at"
            class="shrink-0 rounded-full bg-hairline-soft px-2 py-0.5 font-mono text-[10px] font-semibold text-muted"
            title="受け取り済 (アーカイブ)"
          >Archived</span>
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

        <!-- スクロール領域 (brief / memo / submission / messages を1本のスクロールで貫通) -->
        <div ref="contentScrollRef" class="flex flex-1 flex-col gap-3 overflow-y-auto pr-1">

        <!-- Description -->
        <div v-if="order.description" class="card px-4 py-3">
          <p class="whitespace-pre-wrap text-[13px] text-body">{{ order.description }}</p>
        </div>

        <!-- Brief (structured hearing) -->
        <div v-if="order.brief" class="card px-4 py-4 space-y-4 text-[12px]">
          <div class="flex items-center justify-between">
            <p class="text-[10px] font-semibold text-ink/40 tracking-widest uppercase">サウンドブリーフ</p>
            <div class="flex items-center gap-2">
              <!-- 9-A4: 視点切替トグル -->
              <button
                class="flex items-center gap-1 rounded-md border border-hairline-soft bg-white/60 px-2 py-0.5 text-[10px] text-muted transition-colors hover:border-primary hover:text-primary-active"
                :title="briefView === 'creator' ? 'ユーザ視点に切替' : 'クリエイター視点に切替'"
                @click="toggleBriefView"
              >{{ briefView === 'creator' ? '🎵 クリエイター視点' : '👤 ユーザ視点' }}</button>
              <!-- 履歴アイコン -->
              <button
                v-if="briefEdits.length > 0"
                class="flex items-center gap-1 rounded-md border border-hairline-soft bg-white/60 px-2 py-0.5 text-[10px] text-muted transition-colors hover:border-accent hover:text-accent"
                title="編集履歴を表示"
                @click="showBriefHistory = true"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                履歴 {{ briefEdits.length }}
              </button>
              <!-- 編集ボタン (open/recruiting/assigned のみ) -->
              <button
                v-if="canEditBrief"
                class="flex items-center gap-1 rounded-md border border-accent/40 bg-accent/5 px-2.5 py-0.5 text-[10px] font-medium text-accent transition-colors hover:bg-accent hover:text-white"
                @click="openBriefEditWizard"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                ブリーフを編集
              </button>
            </div>
          </div>

          <!-- 9-A4: クリエイター視点 (役割優先順序) ─────────────────────── -->
          <template v-if="briefView === 'creator'">
            <!-- 📦 つくるもの (最重要: タイプ + 長さ + 報酬 + 締切) -->
            <div class="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-primary-active">📦 つくるもの</p>
              <div class="flex flex-wrap items-baseline gap-x-4 gap-y-1.5 text-[14px] font-medium text-ink">
                <span v-if="order.brief.sound_type" class="rounded-full bg-ink px-2.5 py-0.5 text-[12px] text-canvas">{{ { bgm: 'BGM', se: 'SE', both: 'BGM + SE' }[order.brief.sound_type] }}</span>
                <span v-if="order.brief.length_sec"><span class="font-mono">{{ order.brief.length_sec }}</span> <span class="text-[11px] text-muted">秒</span></span>
                <span class="text-accent"><span class="font-mono">{{ order.token_cost }}</span> <span class="text-[11px]">tk</span></span>
                <span v-if="order.desired_deadline" class="text-[12px]">
                  締切 <span class="font-mono">{{ formatDeadline(order.desired_deadline) }}</span>
                  <span v-if="daysToDeadline !== null && daysToDeadline >= 0" class="text-muted">(あと {{ daysToDeadline }} 日)</span>
                  <span v-else-if="daysToDeadline !== null" class="text-accent">(期限超過)</span>
                </span>
              </div>
              <p v-if="order.brief.purpose" class="text-[12px] text-body">
                用途: <span class="text-ink">{{ { game: 'ゲーム', video: '映像', podcast: 'ポッドキャスト', other: 'その他' }[order.brief.purpose] ?? order.brief.purpose }}</span>
                <span v-if="order.brief.purpose_note" class="text-muted">— {{ order.brief.purpose_note }}</span>
              </p>
            </div>

            <!-- 🎵 雰囲気・感情 -->
            <div v-if="order.brief.emotions_target?.length || order.brief.bgm_scenes?.length || order.brief.memory_impression" class="space-y-1.5">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-ink/40">🎵 雰囲気・感情</p>
              <div v-if="order.brief.emotions_target?.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="e in order.brief.emotions_target"
                  :key="e"
                  class="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary-active"
                >{{ { excitement: '高揚感/興奮', tension: '緊張感', fear: '恐怖/不安', relief: '安らぎ/安心', loneliness: '孤独感', grandeur: '壮大さ', speed: '疾走感', sadness: '哀愁', mystery: '神秘/異世界感', achievement: '達成感', heaviness: '重厚感', comfort: '心地よさ', euphoria: '爽快感', dread: 'じわじわ恐怖', wonder: '驚き/発見' }[e] ?? e }}</span>
              </div>
              <div v-if="order.brief.bgm_scenes?.length" class="flex flex-wrap items-center gap-1.5">
                <span class="text-muted">シーン:</span>
                <span
                  v-for="s in order.brief.bgm_scenes"
                  :key="s"
                  class="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-body border border-white/10"
                >{{ { battle: 'バトル/戦闘', boss: 'ボス戦', explore: '探索/フィールド', menu: 'メニュー/UI', title: 'タイトル', event: 'イベント/ムービー', ending: 'エンディング', ambient: 'アンビエント', other: 'その他' }[s] ?? s }}</span>
              </div>
              <p v-if="order.brief.memory_impression" class="rounded-md border-l-2 border-primary/40 bg-primary/5 pl-2.5 py-1.5 text-[12px] italic text-body whitespace-pre-wrap">「{{ order.brief.memory_impression }}」</p>
            </div>

            <!-- 🔊 SE 設計 (SE のみ) -->
            <div v-if="order.brief.se_trigger || order.brief.se_functions?.length" class="space-y-1.5">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-ink/40">🔊 SE 設計</p>
              <p v-if="order.brief.se_trigger" class="text-[12px]"><span class="text-muted">トリガー:</span> <span class="text-ink">{{ order.brief.se_trigger }}</span></p>
              <div v-if="order.brief.se_functions?.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="f in order.brief.se_functions"
                  :key="f"
                  class="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-body border border-white/10"
                >{{ { success: '成功/達成', danger: '危険/警告', ui: 'UI操作', operation: '操作の手応え', immersion: '没入/演出', character: 'キャラ感情' }[f] ?? f }}</span>
              </div>
            </div>

            <!-- 🔗 参考音源 (大きく表示) -->
            <div v-if="order.brief.reference_urls || order.brief.reference_elements?.length || order.brief.reference_avoid" class="space-y-1.5 rounded-md border border-hairline-soft bg-white/30 p-2.5">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-ink/40">🔗 参考音源</p>
              <p v-if="order.brief.reference_urls" class="whitespace-pre-wrap break-all text-[12px] font-mono text-primary-active">{{ order.brief.reference_urls }}</p>
              <div v-if="order.brief.reference_elements?.length" class="flex flex-wrap items-center gap-1">
                <span class="text-[11px] text-muted">参考要素:</span>
                <span
                  v-for="r in order.brief.reference_elements"
                  :key="r"
                  class="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-body border border-white/10"
                >{{ { atmosphere: '空気感/雰囲気', bass: '低音/ベース感', progression: '展開/構成', tempo: 'テンポ/グルーヴ', timbre: '音色/サウンドデザイン', melody: 'メロディライン', rhythm: 'リズムパターン', density: '音の密度/空間感' }[r] ?? r }}</span>
              </div>
              <p v-if="order.brief.reference_avoid" class="text-[11px]"><span class="text-muted">避けたい:</span> <span class="text-accent">{{ order.brief.reference_avoid }}</span></p>
            </div>

            <!-- 🎛️ 方向性スライダー -->
            <div v-if="order.brief.tx_warm_cold || order.brief.tx_sparse_dense || order.brief.tx_static_dynamic" class="space-y-2">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-ink/40">🎛️ 方向性</p>
              <div v-if="order.brief.tx_warm_cold" class="grid grid-cols-[60px_1fr_60px] items-center gap-2 text-[11px]">
                <span class="text-right text-muted">温かい</span>
                <div class="relative h-1.5 rounded-full bg-hairline-soft">
                  <span class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary shadow-sm" :style="`left:${txPosition(order.brief.tx_warm_cold, 'warm', 'mid', 'cold')}%`" />
                </div>
                <span class="text-muted">冷たい</span>
              </div>
              <div v-if="order.brief.tx_sparse_dense" class="grid grid-cols-[60px_1fr_60px] items-center gap-2 text-[11px]">
                <span class="text-right text-muted">シンプル</span>
                <div class="relative h-1.5 rounded-full bg-hairline-soft">
                  <span class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary shadow-sm" :style="`left:${txPosition(order.brief.tx_sparse_dense, 'sparse', 'mid', 'dense')}%`" />
                </div>
                <span class="text-muted">重厚</span>
              </div>
              <div v-if="order.brief.tx_static_dynamic" class="grid grid-cols-[60px_1fr_60px] items-center gap-2 text-[11px]">
                <span class="text-right text-muted">静的</span>
                <div class="relative h-1.5 rounded-full bg-hairline-soft">
                  <span class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary shadow-sm" :style="`left:${txPosition(order.brief.tx_static_dynamic, 'static', 'mid', 'dynamic')}%`" />
                </div>
                <span class="text-muted">激しい</span>
              </div>
            </div>

            <!-- ⚙️ 技術仕様 (末尾、コンパクト) -->
            <div v-if="order.brief.delivery_format || order.brief.bgm_loop !== undefined || order.brief.budget_range || order.brief.note" class="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
              <span v-if="order.brief.delivery_format">📀 {{ { wav48k24b: '48kHz / 24bit', wav44k16b: '44.1kHz / 16bit', any: '形式: どちらでも' }[order.brief.delivery_format] }}</span>
              <span v-if="order.brief.bgm_loop !== undefined">🔁 {{ order.brief.bgm_loop ? 'ループ必要' : 'ループ不要' }}</span>
              <span v-if="order.brief.budget_range">💰 {{ { '5000': '〜¥5,000', '10000': '〜¥10,000', negotiable: '予算: 要相談' }[order.brief.budget_range] }}</span>
              <p v-if="order.brief.note" class="mt-1 w-full whitespace-pre-wrap text-body">{{ order.brief.note }}</p>
            </div>
          </template>

          <!-- 👤 ユーザ視点 (既存レイアウト、入力エコー) ───────────────────── -->
          <template v-else>
          <!-- 基本 -->
          <div class="space-y-1">
            <p class="text-[10px] font-semibold text-ink/30 tracking-widest uppercase">基本</p>
            <div class="grid grid-cols-[80px_1fr] gap-y-1.5">
              <template v-if="order.brief.sound_type">
                <span class="text-muted">タイプ</span>
                <span class="text-body font-medium" :class="fieldHighlightClass('sound_type')" :title="editedFieldSet.has('sound_type') ? `編集済 (${formatDate(fieldLastEditedAt.get('sound_type') ?? '')})` : ''">{{ { bgm: 'BGM', se: 'SE', both: 'BGM + SE' }[order.brief.sound_type] ?? order.brief.sound_type }}</span>
              </template>
              <template v-if="order.brief.purpose">
                <span class="text-muted">用途</span>
                <span class="text-body" :class="fieldHighlightClass('purpose')" :title="editedFieldSet.has('purpose') ? `編集済 (${formatDate(fieldLastEditedAt.get('purpose') ?? '')})` : ''">{{ { game: 'ゲーム', video: '映像', podcast: 'ポッドキャスト', other: 'その他' }[order.brief.purpose] ?? order.brief.purpose }}{{ order.brief.purpose_note ? ` — ${order.brief.purpose_note}` : '' }}</span>
              </template>
              <template v-if="order.brief.length_sec">
                <span class="text-muted">長さ</span>
                <span class="text-body" :class="fieldHighlightClass('length_sec')" :title="editedFieldSet.has('length_sec') ? `編集済 (${formatDate(fieldLastEditedAt.get('length_sec') ?? '')})` : ''">{{ order.brief.length_sec }}秒</span>
              </template>
            </div>
          </div>

          <!-- シーン (BGM) -->
          <div v-if="order.brief.bgm_scenes?.length" class="space-y-1" :class="fieldHighlightClass('bgm_scenes')">
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
            <div v-if="order.brief.emotions_target?.length" :class="fieldHighlightClass('emotions_target')">
              <p class="text-muted mb-1">狙う感情</p>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="e in order.brief.emotions_target"
                  :key="e"
                  class="rounded-full bg-accent/15 px-2.5 py-0.5 text-[11px] text-accent border border-accent/20"
                >{{ { excitement: '高揚感/興奮', tension: '緊張感', fear: '恐怖/不安', relief: '安らぎ/安心', loneliness: '孤独感', grandeur: '壮大さ/圧倒感', speed: '疾走感', sadness: '哀愁/切なさ', mystery: '神秘/異世界感', achievement: '達成感', heaviness: '重厚感/威圧感', comfort: '心地よさ', euphoria: '爽快感', dread: 'じわじわとした恐怖', wonder: '驚き/発見の喜び' }[e] ?? e }}</span>
              </div>
            </div>
            <div v-if="order.brief.emotions_avoid?.length" :class="fieldHighlightClass('emotions_avoid')">
              <p class="text-muted mb-1">避けたい感情</p>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="e in order.brief.emotions_avoid"
                  :key="e"
                  class="rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] text-muted border border-white/10 line-through"
                >{{ { excitement: '高揚感/興奮', tension: '緊張感', fear: '恐怖/不安', relief: '安らぎ/安心', loneliness: '孤独感', grandeur: '壮大さ/圧倒感', speed: '疾走感', sadness: '哀愁/切なさ', mystery: '神秘/異世界感', achievement: '達成感', heaviness: '重厚感/威圧感', comfort: '心地よさ', euphoria: '爽快感', dread: 'じわじわとした恐怖', wonder: '驚き/発見の喜び' }[e] ?? e }}</span>
              </div>
            </div>
            <p v-if="order.brief.memory_impression" class="mt-2 rounded-lg bg-surface-2/60 border border-white/10 px-3 py-2 text-[12px] text-body italic whitespace-pre-wrap" :class="fieldHighlightClass('memory_impression')">「{{ order.brief.memory_impression }}」</p>
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
          </template>
        </div>

        <!-- 改訂2.4: admin/creator 共有メモ (user 不可視) -->
        <div v-if="canViewMemos" class="card px-4 py-3">
          <p class="mb-2 text-[10px] font-semibold uppercase tracking-widest text-ink/40">共有メモ (user には非表示)</p>
          <div class="grid grid-cols-2 gap-3">
            <!-- Admin 枠 -->
            <div class="rounded-md border border-hairline-soft bg-white/40 p-2">
              <div class="mb-1 flex items-center justify-between">
                <span class="text-[10px] font-semibold uppercase tracking-widest text-accent">📝 Admin</span>
                <button
                  v-if="memosState.can_edit_admin"
                  class="rounded border border-hairline px-2 py-0.5 text-[10px] text-body transition-colors hover:border-accent hover:text-accent"
                  @click="openMemoEdit('admin')"
                >メモ</button>
              </div>
              <p v-if="memosState.admin?.content" class="whitespace-pre-wrap text-[12px] text-ink">{{ memosState.admin.content }}</p>
              <p v-else class="text-[11px] italic text-muted">(未記入)</p>
              <p v-if="memosState.admin?.author_name" class="mt-1 font-mono text-[9px] text-muted">
                — {{ memosState.admin.author_name }} / {{ formatDate(memosState.admin.updated_at) }}
              </p>
            </div>
            <!-- Creator 枠 -->
            <div class="rounded-md border border-hairline-soft bg-white/40 p-2">
              <div class="mb-1 flex items-center justify-between">
                <span class="text-[10px] font-semibold uppercase tracking-widest text-[#0e7a74]">📝 Creator</span>
                <button
                  v-if="memosState.can_edit_creator"
                  class="rounded border border-hairline px-2 py-0.5 text-[10px] text-body transition-colors hover:border-[#0e7a74] hover:text-[#0e7a74]"
                  @click="openMemoEdit('creator')"
                >メモ</button>
              </div>
              <p v-if="memosState.creator?.content" class="whitespace-pre-wrap text-[12px] text-ink">{{ memosState.creator.content }}</p>
              <p v-else class="text-[11px] italic text-muted">(未記入)</p>
              <p v-if="memosState.creator?.author_name" class="mt-1 font-mono text-[9px] text-muted">
                — {{ memosState.creator.author_name }} / {{ formatDate(memosState.creator.updated_at) }}
              </p>
            </div>
          </div>
        </div>

        <!-- 改訂2.2: 音源プレビュー (reviewing / done で全参加者視聴可) -->
        <!-- 改訂2.5 (9-A3): 複数 version の履歴を表示、選択切替 -->
        <div
          v-if="hasSubmission"
          class="card shrink-0 border-primary/30 bg-primary/5 px-4 py-3"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0 flex-1">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-primary-active">提出された音源</p>
              <p class="mt-0.5 text-[11px] text-muted">
                {{ order.status === 'reviewing' ? 'プレビュー可能 (admin の承認後に受け取れます)' : `承認済み — 受け取り時に ${order.token_cost} token 消費` }}
              </p>
            </div>
            <button
              v-if="canReceive"
              class="shrink-0 rounded-md bg-ink px-3 py-1.5 text-[12px] font-medium text-canvas transition-colors hover:bg-primary disabled:opacity-50"
              :disabled="closeLoading"
              @click="receiveAndClose"
            >{{ closeLoading ? '…' : '受け取る' }}</button>
          </div>

          <!-- バージョン履歴 (改訂2.5 / 9-A3) — 2件以上の時のみ表示 -->
          <div v-if="submissions.length > 1" class="mt-3 space-y-1">
            <p class="text-[10px] font-semibold uppercase tracking-widest text-muted">提出履歴</p>
            <div class="space-y-1">
              <button
                v-for="s in [...submissions].reverse()"
                :key="s.message_id"
                type="button"
                class="flex w-full items-center gap-2 rounded-md border px-2.5 py-1.5 text-left text-[11px] transition-colors"
                :class="selectedVersion === s.version
                  ? 'border-primary bg-primary/10'
                  : s.rejected
                    ? 'border-hairline-soft bg-white/30 opacity-60 hover:opacity-100'
                    : 'border-hairline-soft bg-white/50 hover:border-primary/40'"
                @click="selectVersion(s.version)"
              >
                <span class="shrink-0 rounded-full bg-ink/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-ink">v{{ s.version }}</span>
                <span v-if="s.rejected" class="shrink-0 rounded bg-accent/20 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-accent">REJECTED</span>
                <span class="flex-1 truncate" :class="s.rejected ? 'text-muted' : 'text-ink'">{{ s.note ?? '(メモなし)' }}</span>
                <span class="shrink-0 font-mono text-[10px] text-muted">{{ formatVersionTime(s.created_at) }}</span>
              </button>
            </div>
            <p v-if="submissions.find(s => s.version === selectedVersion)?.rejected" class="px-1 text-[10px] text-accent">
              ⊘ {{ submissions.find(s => s.version === selectedVersion)?.rejection_reason ?? '差し戻されました' }}
            </p>
          </div>

          <div v-if="audioPreviewLoading" class="mt-2 text-[12px] text-muted">読み込み中…</div>
          <div v-else-if="audioPreviewError" class="mt-2 text-[12px] text-accent">{{ audioPreviewError }}</div>
          <audio
            v-else-if="audioPreviewUrl"
            :src="audioPreviewUrl"
            controls
            class="mt-2 h-9 w-full"
            preload="metadata"
          />
        </div>

        <!-- Messages (改訂2.3: LINE 風チャット吹き出し)。スクロールは親 contentScrollRef に統合 -->
        <div ref="messagesRef" class="px-2 py-2">
          <div v-if="order.messages.length === 0" class="py-12 text-center text-[12px] text-muted">
            メッセージはまだありません。
          </div>
          <div
            v-for="(msg, i) in order.messages"
            :key="msg.id"
            class="mb-1.5 flex gap-2"
            :class="isMyMessage(msg) ? 'flex-row-reverse' : 'flex-row'"
          >
            <!-- アバター (初文字) — 連続発言時は省略 -->
            <div
              v-if="shouldShowAvatar(msg, i)"
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-bold"
              :class="avatarClass(msg)"
            >{{ avatarLetter(msg) }}</div>
            <div v-else class="w-7 shrink-0" />

            <!-- 吹き出し -->
            <div :class="isMyMessage(msg) ? 'flex max-w-[78%] flex-col items-end' : 'flex max-w-[78%] flex-col items-start'">
              <!-- 名前 + 時刻 + 私信バッジ -->
              <div
                v-if="shouldShowAvatar(msg, i)"
                class="mb-0.5 flex items-center gap-1.5 px-1 text-[10px]"
                :class="isMyMessage(msg) ? 'flex-row-reverse' : 'flex-row'"
              >
                <span class="font-medium text-body-strong">{{ senderLabel(msg) }}</span>
                <span class="text-muted">{{ formatTime(msg.created_at) }}</span>
              </div>

              <!-- 吹き出し本体 -->
              <div
                v-if="msg.kind === 'comment' || msg.kind === 'submission'"
                class="rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed whitespace-pre-wrap break-words"
                :class="bubbleClass(msg)"
              >
                <p v-if="msg.content">{{ msg.content }}</p>
                <p v-if="msg.attachment_path" class="mt-1 font-mono text-[10px] opacity-70">
                  📎 添付ファイル
                </p>
              </div>
              <!-- システム / status / brief_edit はインラインの細い表示 -->
              <div
                v-else
                class="rounded-md border-l-2 px-2.5 py-1 text-[11px] italic"
                :class="msg.kind === 'brief_edit'
                  ? 'border-accent bg-accent/5 text-accent'
                  : msg.kind === 'rejection'
                    ? 'border-accent/50 bg-accent/5 text-body'
                    : msg.kind === 'done'
                      ? 'border-[#2ecc71]/60 bg-[#2ecc71]/5 text-body'
                      : 'border-hairline-strong bg-hairline-soft/60 text-muted'"
              >
                <p v-if="msg.content" class="whitespace-pre-wrap">{{ msg.content }}</p>
              </div>
            </div>
          </div>
        </div>

        </div><!-- /contentScrollRef: チャット入力は下に固定するためスクロール領域から外す -->

        <!-- 改訂2.2: チャット入力 (テキスト + 音源添付 + 送信) -->
        <div
          v-if="order.status !== 'cancelled' && order.status !== 'draft' && !order.closed_at"
          class="card shrink-0 px-3 py-2"
        >
          <textarea
            v-model="msgContent"
            rows="2"
            :placeholder="attachedFile ? '音源と一緒に送るメモ (任意)…' : 'メッセージを入力…'"
            class="w-full resize-none bg-transparent text-[13px] text-ink outline-none placeholder:text-muted"
            @keydown.ctrl.enter.prevent="sendChat"
          />
          <!-- 添付済みファイル表示 -->
          <div
            v-if="attachedFile"
            class="mt-1 flex items-center gap-2 rounded-md border border-primary/30 bg-primary/5 px-2 py-1 text-[11px]"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary-active">
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
            </svg>
            <span class="flex-1 truncate font-mono text-body">{{ attachedFile.name }}</span>
            <button class="text-muted hover:text-accent" @click="clearAttach">×</button>
          </div>
          <div class="mt-1.5 flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <!-- Attach (creator only, status=assigned) -->
              <button
                v-if="canAttachSubmit"
                class="flex items-center gap-1 rounded-md border border-hairline-strong px-2 py-1 text-[11px] text-body transition-colors hover:border-primary hover:text-primary-active"
                :title="'音源を添付して提出 (assigned creator のみ)'"
                @click="pickAttach"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                </svg>
                音源添付
              </button>
              <input
                ref="attachInputRef"
                type="file"
                accept=".wav,audio/wav,audio/x-wav"
                class="hidden"
                @change="onAttachChange"
              />
            </div>
            <button
              class="rounded-md bg-ink px-3 py-1 text-[11px] font-medium text-canvas transition-colors hover:bg-primary disabled:opacity-50"
              :disabled="msgLoading || attachLoading || (!msgContent.trim() && !attachedFile)"
              @click="sendChat"
            >{{ attachLoading ? '提出中…' : (attachedFile ? '提出' : (msgLoading ? '…' : '送信')) }}</button>
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
            @click="openNominateModal"
          >クリエイター指名</button>

          <button
            v-if="['open','recruiting'].includes(order.status)"
            class="w-full rounded-md border border-[#20b2aa55] px-3 py-1.5 text-[12px] font-medium text-[#0e7a74] hover:bg-[#20b2aa15] disabled:opacity-40"
            :disabled="candidatesForAssign.length === 0"
            :title="candidatesForAssign.length === 0 ? '候補がいません。先に指名してください' : ''"
            @click="openAssignModal"
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

      <!-- Nominate (改訂2.2: creator 一覧 + ランクフィルタ + 検索 + 複数選択) -->
      <Transition name="modal">
        <div v-if="showNominate" class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-12 pb-6 backdrop-blur-sm overflow-y-auto" @click.self="showNominate = false">
          <div class="card mx-4 w-full max-w-[560px] p-6">
            <h2 class="mb-3 text-[15px] font-semibold text-ink">クリエイター指名</h2>

            <!-- ランクフィルタ -->
            <div class="mb-3 flex flex-wrap items-center gap-1.5">
              <span class="mr-1 text-[10px] uppercase tracking-widest text-muted">ランク</span>
              <button
                v-for="r in (['bronze','silver','gold','platinum'] as const)"
                :key="r"
                class="rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors"
                :class="nominateRankFilter.has(r) ? RANK_CHIP[r] + ' ring-1 ring-current/40' : 'bg-hairline-soft text-muted'"
                @click="toggleRankFilter(r)"
              >{{ RANK_LABEL[r] }}</button>
            </div>

            <!-- 検索 -->
            <input
              v-model="nominateSearch"
              type="search"
              placeholder="ユーザ名 / 表示名で検索…"
              class="mb-3 w-full rounded-md border border-hairline-strong bg-white/70 px-3 py-1.5 text-[12px] text-ink outline-none focus:border-primary"
            />

            <!-- 候補一覧 -->
            <div class="max-h-[40vh] space-y-1 overflow-y-auto rounded-md border border-hairline">
              <p v-if="filteredCreators.length === 0" class="p-4 text-center text-[12px] text-muted">該当する creator がいません</p>
              <label
                v-for="c in filteredCreators"
                :key="c.id"
                class="flex cursor-pointer items-center gap-3 border-b border-hairline-soft px-3 py-2 text-[12px] transition-colors last:border-b-0 hover:bg-primary/5"
              >
                <input
                  type="checkbox"
                  :checked="nominateSelected.has(c.id)"
                  class="h-4 w-4 accent-primary"
                  @change="toggleNominate(c.id)"
                />
                <span class="flex-1 truncate font-medium text-ink">{{ c.display_name ?? c.username }}</span>
                <span class="font-mono text-[10px] text-muted">@{{ c.username }}</span>
                <span
                  v-if="c.rank"
                  class="rounded-full px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase"
                  :class="RANK_CHIP[c.rank] ?? ''"
                >{{ c.rank }}</span>
              </label>
            </div>

            <p class="mt-2 text-[11px] text-muted">{{ nominateSelected.size }} 名選択中</p>
            <p v-if="nominateError" class="mt-2 text-[12px] text-accent">{{ nominateError }}</p>
            <div class="mt-4 flex justify-end gap-2">
              <button class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] text-body-strong hover:text-ink" @click="showNominate = false">やめる</button>
              <button
                class="rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas transition-colors hover:bg-primary disabled:opacity-50"
                :disabled="nominateLoading || nominateSelected.size === 0"
                @click="executeNominate"
              >{{ nominateLoading ? '…' : `指名する (${nominateSelected.size})` }}</button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Assign (改訂2.2: 候補から選択) -->
      <Transition name="modal">
        <div v-if="showAssign" class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24 backdrop-blur-sm" @click.self="showAssign = false">
          <div class="card mx-4 w-full max-w-[480px] p-6">
            <h2 class="mb-3 text-[15px] font-semibold text-ink">アサイン確定</h2>
            <p v-if="candidatesForAssign.length === 0" class="mb-3 text-[12px] text-muted">候補がいません。先に指名してください。</p>

            <div v-else class="mb-3 space-y-1 rounded-md border border-hairline">
              <label
                v-for="c in candidatesForAssign"
                :key="c.id"
                class="flex cursor-pointer items-center gap-3 border-b border-hairline-soft px-3 py-2 text-[12px] transition-colors last:border-b-0 hover:bg-primary/5"
                :class="c.response_status === 'pending' ? 'opacity-60' : ''"
              >
                <input
                  type="radio"
                  :value="c.creator_id"
                  v-model="assignCreatorId"
                  name="assign_creator"
                  class="accent-primary"
                />
                <span class="flex-1 truncate font-medium text-ink">{{ c.creator_name }}</span>
                <span
                  class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  :class="c.response_status === 'accepted' ? 'bg-[#20b2aa22] text-[#0e7a74]' : 'bg-hairline-soft text-muted'"
                >{{ RESPONSE_LABEL[c.response_status] }}</span>
              </label>
            </div>

            <div>
              <label class="mb-1 block text-[11px] font-medium text-muted">token 数 (変更する場合)</label>
              <input
                v-model.number="assignTokenCost"
                type="number"
                min="1"
                :placeholder="`現在: ${order?.token_cost ?? '-'}`"
                class="w-40 rounded-md border border-hairline-strong bg-white/60 px-3 py-1.5 font-mono text-[12px] text-ink outline-none focus:border-primary"
              />
            </div>

            <p v-if="assignError" class="mt-2 text-[12px] text-accent">{{ assignError }}</p>
            <div class="mt-4 flex justify-end gap-2">
              <button class="rounded-md border border-hairline-strong px-4 py-1.5 text-[12px] text-body-strong hover:text-ink" @click="showAssign = false">やめる</button>
              <button
                class="rounded-md bg-[#20b2aa] px-4 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:opacity-50"
                :disabled="assignLoading || !assignCreatorId"
                @click="executeAssign"
              >{{ assignLoading ? '…' : 'アサイン確定' }}</button>
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

    <!-- 改訂2.1: ブリーフ編集 wizard モーダル -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showBriefEditWizard && order?.brief"
          class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-12 pb-6 backdrop-blur-sm overflow-y-auto"
          @click.self="showBriefEditWizard = false"
        >
          <div class="card mx-4 w-full max-w-[540px] p-6">
            <div class="mb-3 flex items-center justify-between">
              <div>
                <h2 class="text-[15px] font-semibold text-ink">ブリーフを編集</h2>
                <p class="mt-0.5 text-[11px] text-muted">変更内容はチャットに自動通知されます</p>
              </div>
              <button class="text-muted hover:text-ink" @click="showBriefEditWizard = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>
            <OrderBriefWizard
              :initial-brief="order.brief as Partial<WizardBrief>"
              :initial-deadline="order.desired_deadline"
              @submit="submitBriefEdit"
              @cancel="showBriefEditWizard = false"
            />
            <p v-if="briefEditError" class="mt-3 text-[12px] text-accent">{{ briefEditError }}</p>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 改訂2.1: ブリーフ編集履歴モーダル -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showBriefHistory"
          class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-16 pb-6 backdrop-blur-sm overflow-y-auto"
          @click.self="showBriefHistory = false"
        >
          <div class="card mx-4 w-full max-w-[520px] p-6">
            <div class="mb-4 flex items-center justify-between">
              <h2 class="text-[15px] font-semibold text-ink">ブリーフ編集履歴 ({{ briefEdits.length }})</h2>
              <button class="text-muted hover:text-ink" @click="showBriefHistory = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>
            <div v-if="briefEdits.length === 0" class="py-8 text-center text-[12px] text-muted">編集はまだありません。</div>
            <div v-else class="space-y-3 max-h-[60vh] overflow-y-auto">
              <div
                v-for="e in briefEdits"
                :key="e.id"
                class="rounded-lg border border-hairline bg-white/60 px-3 py-2.5"
              >
                <div class="flex items-baseline justify-between gap-2 text-[11px] text-muted">
                  <span class="font-mono">{{ formatDate(e.created_at) }}</span>
                  <span>{{ e.editor_name ?? 'system' }}</span>
                </div>
                <p class="mt-1 text-[12px] font-semibold text-accent">{{ e.field_label }}</p>
                <div class="mt-1 grid grid-cols-[40px_1fr] gap-x-2 gap-y-0.5 text-[11px]">
                  <span class="text-muted">変更前</span>
                  <span class="text-body whitespace-pre-wrap break-words">{{ JSON.stringify(e.old_value) }}</span>
                  <span class="text-muted">変更後</span>
                  <span class="text-ink whitespace-pre-wrap break-words">{{ JSON.stringify(e.new_value) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 改訂2.4: メモ編集モーダル -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="memoEditOpen"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          @click.self="closeMemoEdit"
        >
          <div class="w-full max-w-[480px] rounded-lg bg-canvas px-5 py-4 shadow-xl">
            <div class="mb-3 flex items-center justify-between">
              <h3 class="text-[14px] font-semibold text-ink">
                {{ memoEditOpen === 'admin' ? '📝 Admin メモ' : '📝 Creator メモ' }}
              </h3>
              <button class="text-muted hover:text-ink" @click="closeMemoEdit">×</button>
            </div>
            <textarea
              v-model="memoEditContent"
              rows="6"
              maxlength="2000"
              placeholder="この Order についてのメモ (user には表示されません)…"
              class="w-full resize-none rounded-md border border-hairline bg-white px-3 py-2 text-[13px] text-ink outline-none focus:border-primary"
            />
            <div class="mt-1 flex items-center justify-between">
              <span class="font-mono text-[10px] text-muted">{{ memoEditContent.length }} / 2000</span>
            </div>
            <div class="mt-3 flex justify-end gap-2">
              <button
                class="rounded-md border border-hairline px-3 py-1.5 text-[12px] text-body hover:border-ink hover:text-ink"
                @click="closeMemoEdit"
              >キャンセル</button>
              <button
                class="rounded-md bg-ink px-3 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary disabled:opacity-50"
                :disabled="memoSaving"
                @click="saveMemo"
              >{{ memoSaving ? '…' : '保存' }}</button>
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
