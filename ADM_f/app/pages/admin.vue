<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useSystemStore } from '~/stores/system'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })
useHead({ title: 'Admin — Pathfinder' })

const auth = useAuthStore()
const system = useSystemStore()
const api = useApi()
const router = useRouter()

onMounted(() => {
  auth.hydrate()
  if (auth.role !== 'admin') router.replace('/dashboard')
  // NOTIFICATION_SPEC §5: Level 3 タブドット用に通知サマリを取得
  system.fetchCommissionUnread()
})

// NOTIFICATION_SPEC §3.2: タブ単位の通知ドット (Level 3)
// 未実装領域 (token_grants / lic_requests) は 0 なのでドットが立たない
function tabArea(tabKey: Tab): { action: number; info: boolean } {
  // タブ名 → area 名のマッピング (Users タブは creator_dm を担う = DM ボタンの導線)
  const map: Record<Tab, string | null> = {
    users: 'creator_dm',
    payouts: 'payouts',
    tokens: 'token_grants',
    licenses: 'lic_requests',
    orders: 'commission',
    archive: null,
    logs: null,
    settings: null,
  }
  const areaName = map[tabKey]
  if (!areaName) return { action: 0, info: false }
  const a = system.areaFor(areaName)
  return { action: a.action_count, info: a.has_info }
}

// ─── Tab ─────────────────────────────────────────────────────────────────────
type Tab = 'users' | 'payouts' | 'tokens' | 'licenses' | 'orders' | 'archive' | 'logs' | 'settings'
const TAB_STORAGE_KEY = 'pathfinder.adminTab'
const VALID_TABS: readonly Tab[] = ['users', 'payouts', 'tokens', 'licenses', 'orders', 'archive', 'logs', 'settings']
function loadInitialTab(): Tab {
  if (typeof window === 'undefined') return 'users'
  const saved = window.localStorage.getItem(TAB_STORAGE_KEY) as Tab | null
  return saved && VALID_TABS.includes(saved) ? saved : 'users'
}
const tab = ref<Tab>(loadInitialTab())
watch(tab, (t) => {
  if (typeof window !== 'undefined') window.localStorage.setItem(TAB_STORAGE_KEY, t)
})

// ─── DM modal (改訂2.4) ──────────────────────────────────────────────────────
interface DMItem {
  id: string
  sender_id: string | null
  sender_name: string | null
  sender_kind: 'admin' | 'creator'
  content: string
  attachment_path: string | null
  created_at: string
}
const dmOpen = ref<{ id: string; name: string } | null>(null)
const dmMessages = ref<DMItem[]>([])
const dmLoading = ref(false)
const dmDraft = ref('')
const dmSending = ref(false)
const dmListRef = ref<HTMLDivElement | null>(null)

async function openDmModal(creatorId: string, name: string) {
  dmOpen.value = { id: creatorId, name }
  dmMessages.value = []
  dmDraft.value = ''
  dmLoading.value = true
  try {
    dmMessages.value = await api.get<DMItem[]>(`/api/v1/admin/dm/creators/${creatorId}`)
    await api.post(`/api/v1/admin/dm/creators/${creatorId}/view`, { body: {} })
    await system.fetchCommissionUnread()
    await nextTick()
    if (dmListRef.value) dmListRef.value.scrollTop = dmListRef.value.scrollHeight
  } catch (err) {
    alert(errorMessageJa(err))
  } finally {
    dmLoading.value = false
  }
}
function closeDm() {
  dmOpen.value = null
  dmMessages.value = []
  dmDraft.value = ''
}
async function sendDm() {
  if (!dmOpen.value) return
  const content = dmDraft.value.trim()
  if (!content) return
  dmSending.value = true
  try {
    const msg = await api.post<DMItem>(`/api/v1/admin/dm/creators/${dmOpen.value.id}`, {
      body: { content },
    })
    dmMessages.value.push(msg)
    dmDraft.value = ''
    await nextTick()
    if (dmListRef.value) dmListRef.value.scrollTop = dmListRef.value.scrollHeight
  } catch (err) {
    alert(errorMessageJa(err))
  } finally {
    dmSending.value = false
  }
}
function dmIsMine(m: DMItem): boolean {
  return m.sender_kind === 'admin'
}
function dmFormatTime(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─── Types ───────────────────────────────────────────────────────────────────
interface UserItem {
  id: string
  username: string
  role: string
  license_code: string | null
  monthly_quota_tokens: number | null
  group_name: string | null
  rank: string | null
  display_name: string | null
  created_at: string
}
interface PayoutItem {
  id: string
  audio_title: string | null
  creator_name: string | null
  creator_id: string
  rank_at_payout: string
  amount_yen: number
  status: string
  created_at: string
  paid_at: string | null
}
interface CreatorGroup {
  creator_id: string
  creator_name: string | null
  rank: string
  payouts: PayoutItem[]
  pending_total: number
  pending_count: number
  paid_total: number
}
interface MonthStat { yyyymm: number; uploads: number; dls: number }
interface CreatorStats {
  user_id: string
  total_uploads: number
  total_sold: number
  total_unsold: number
  payout_total_yen: number
  payout_pending_yen: number
  monthly: MonthStat[]
}

// ─── Users tab ───────────────────────────────────────────────────────────────
const users = ref<UserItem[]>([])
const usersLoading = ref(false)
const usersError = ref<string | null>(null)

async function fetchUsers() {
  usersLoading.value = true
  usersError.value = null
  try {
    users.value = await api.get<UserItem[]>('/api/v1/admin/users')
  } catch (e) {
    usersError.value = errorMessageJa(e)
  } finally {
    usersLoading.value = false
  }
}

// ─── User list role filter ───────────────────────────────────────────────────
type RoleFilter = 'creator' | 'licensee'
const roleFilter = ref<RoleFilter>('creator')

// ロール識別色 (DESIGN.md「ロール識別色」)。Tailwind は動的クラス名を出せないため静的マップで保持。
// Users タブの role フィルタ (選択時=塗り pill)
const ROLE_FILTER_CLASS: Record<RoleFilter, { on: string; off: string }> = {
  creator:  { on: 'bg-seagreen text-white',  off: 'border border-hairline-strong text-seagreen-deep hover:border-seagreen' },
  licensee: { on: 'bg-licensee text-ink',    off: 'border border-hairline-strong text-licensee-deep hover:border-licensee' },
}
// lic 発行の role セレクタ (選択時=淡色 tint)
const LIC_ROLE_CLASS: Record<'licensee' | 'creator' | 'admin', { on: string; off: string }> = {
  admin:    { on: 'border-admin bg-admin/15 text-admin-deep',          off: 'border-hairline text-admin-deep/70 hover:text-admin-deep' },
  creator:  { on: 'border-seagreen bg-seagreen/15 text-seagreen-deep', off: 'border-hairline text-seagreen-deep/70 hover:text-seagreen-deep' },
  licensee: { on: 'border-licensee bg-licensee/25 text-licensee-deep', off: 'border-hairline text-licensee-deep/70 hover:text-licensee-deep' },
}
// ロール名 → 識別テキスト色 (バッジ/ログ行の role 表記用)
function roleTextClass(role: string): string {
  return role === 'admin' ? 'text-admin-deep'
    : role === 'creator' ? 'text-seagreen-deep'
    : 'text-licensee-deep'
}
const groupFilter = ref<string>('all')

const creatorList = computed(() => users.value.filter(u => u.role === 'creator' || u.role === 'admin'))
const userList = computed(() => users.value.filter(u => u.role === 'licensee'))

const availableGroups = computed(() => {
  const s = new Set<string>()
  for (const u of userList.value) if (u.group_name) s.add(u.group_name)
  return Array.from(s).sort()
})

const filteredUsers = computed(() => {
  if (groupFilter.value === 'all') return userList.value
  if (groupFilter.value === '__none__') return userList.value.filter(u => !u.group_name)
  return userList.value.filter(u => u.group_name === groupFilter.value)
})

watch(roleFilter, () => { groupFilter.value = 'all' })

// ─── Creator rank ────────────────────────────────────────────────────────────
const RANKS = ['bronze', 'silver', 'gold', 'platinum']
const rankLoading = ref<Record<string, boolean>>({})
const rankError = ref<Record<string, string | null>>({})

async function changeRank(userId: string, rank: string) {
  rankLoading.value[userId] = true
  rankError.value[userId] = null
  try {
    await api.patch(`/api/v1/admin/creators/${userId}/rank`, { body: { rank } })
    const u = users.value.find(u => u.id === userId)
    if (u) u.rank = rank
  } catch (e) {
    rankError.value[userId] = errorMessageJa(e)
  } finally {
    rankLoading.value[userId] = false
  }
}

// ─── Creator stats (lazy load per row) ───────────────────────────────────────
const expandedStats = ref(new Set<string>())
const creatorStats = ref<Record<string, CreatorStats>>({})
const statsLoading = ref<Record<string, boolean>>({})

async function toggleStats(userId: string) {
  const s = new Set(expandedStats.value)
  if (s.has(userId)) {
    s.delete(userId)
    expandedStats.value = s
    return
  }
  s.add(userId)
  expandedStats.value = s
  if (creatorStats.value[userId]) return  // already loaded
  statsLoading.value[userId] = true
  try {
    creatorStats.value[userId] = await api.get<CreatorStats>(
      `/api/v1/admin/creators/${userId}/stats?months=6`
    )
  } catch {
    // silently fail — stats panel shows dash
  } finally {
    statsLoading.value[userId] = false
  }
}

function fmtMonth(yyyymm: number): string {
  const y = Math.floor(yyyymm / 100)
  const m = yyyymm % 100
  return `${y}-${String(m).padStart(2, '0')}`
}

// ─── Group editing (inline) ───────────────────────────────────────────────────
const editingGroupId = ref<string | null>(null)
const editGroupValue = ref('')
const groupSaving = ref(false)
const groupError = ref<string | null>(null)

function startEditGroup(u: UserItem) {
  editingGroupId.value = u.id
  editGroupValue.value = u.group_name ?? ''
  groupError.value = null
}

function cancelEditGroup() {
  editingGroupId.value = null
  editGroupValue.value = ''
  groupError.value = null
}

async function saveGroup(u: UserItem) {
  groupSaving.value = true
  groupError.value = null
  try {
    await api.patch(`/api/v1/admin/users/${u.id}/group`, {
      body: { group_name: editGroupValue.value.trim() || null },
    })
    u.group_name = editGroupValue.value.trim() || null
    cancelEditGroup()
  } catch (e) {
    groupError.value = errorMessageJa(e)
  } finally {
    groupSaving.value = false
  }
}

// ─── Payouts tab ─────────────────────────────────────────────────────────────
const payouts = ref<PayoutItem[]>([])
const payoutsLoading = ref(false)
const payoutsError = ref<string | null>(null)
const payoutFilter = ref<'pending' | 'all'>('pending')
const expandedCreators = ref(new Set<string>())

function toggleCreator(id: string) {
  const s = new Set(expandedCreators.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedCreators.value = s
}

async function fetchPayouts() {
  payoutsLoading.value = true
  payoutsError.value = null
  expandedCreators.value = new Set()
  try {
    const q = payoutFilter.value === 'pending' ? { status_filter: 'pending' } : {}
    payouts.value = await api.get<PayoutItem[]>('/api/v1/admin/payouts', { query: q })
  } catch (e) {
    payoutsError.value = errorMessageJa(e)
  } finally {
    payoutsLoading.value = false
  }
}

const creatorGroups = computed((): CreatorGroup[] => {
  const map = new Map<string, CreatorGroup>()
  for (const p of payouts.value) {
    if (!map.has(p.creator_id)) {
      map.set(p.creator_id, {
        creator_id: p.creator_id, creator_name: p.creator_name,
        rank: p.rank_at_payout, payouts: [],
        pending_total: 0, pending_count: 0, paid_total: 0,
      })
    }
    const g = map.get(p.creator_id)!
    g.payouts.push(p)
    if (p.status === 'pending') { g.pending_total += p.amount_yen; g.pending_count++ }
    else if (p.status === 'paid') { g.paid_total += p.amount_yen }
  }
  return Array.from(map.values()).sort((a, b) => b.pending_total - a.pending_total)
})

const paidLoading = ref<Record<string, boolean>>({})

async function markPaid(payoutId: string) {
  paidLoading.value[payoutId] = true
  try {
    await api.patch(`/api/v1/admin/payouts/${payoutId}/paid`, {})
    const p = payouts.value.find(p => p.id === payoutId)
    if (p) p.status = 'paid'
  } catch (e) {
    payoutsError.value = errorMessageJa(e)
  } finally {
    paidLoading.value[payoutId] = false
  }
}

// ─── Token grant tab ──────────────────────────────────────────────────────────
const grantUserId = ref('')
const grantTokens = ref(3600)
const grantReason = ref('')
const grantLoading = ref(false)
const grantError = ref<string | null>(null)
const grantSuccess = ref<string | null>(null)
const userOnlyList = computed(() => users.value.filter(u => u.role === 'licensee'))

function resetGrant() {
  grantUserId.value = ''
  grantTokens.value = 3600
  grantReason.value = ''
  grantError.value = null
  grantSuccess.value = null
}

async function submitGrant() {
  if (!grantUserId.value || grantTokens.value <= 0) return
  grantLoading.value = true
  grantError.value = null
  grantSuccess.value = null
  try {
    const res = await api.post<{ id: string; tokens: number; period_yyyymm: number }>(
      '/api/v1/admin/token-grants',
      { body: { user_id: grantUserId.value, tokens: grantTokens.value, reason: grantReason.value || null } },
    )
    grantSuccess.value = `${res.tokens.toLocaleString()} tk を付与しました (${res.period_yyyymm})`
    grantUserId.value = ''
    grantTokens.value = 3600
    grantReason.value = ''
  } catch (e) {
    grantError.value = errorMessageJa(e)
  } finally {
    grantLoading.value = false
  }
}

// ─── Lic issuance tab ────────────────────────────────────────────────────────
const licUsername = ref('')
const licRole = ref<'licensee' | 'creator' | 'admin'>('licensee')
const licQuota = ref(18000)
const licGroup = ref('')
const licExpires = ref('')
const licLoading = ref(false)
const licError = ref<string | null>(null)

function resetLic() {
  licUsername.value = ''
  licRole.value = 'licensee'
  licQuota.value = 18000
  licGroup.value = ''
  licExpires.value = ''
  licError.value = null
}

async function issueLic() {
  if (!licUsername.value.trim()) return
  licLoading.value = true
  licError.value = null
  try {
    const body: Record<string, unknown> = {
      username: licUsername.value.trim(),
      role: licRole.value,
      ...(licRole.value === 'licensee' ? { monthly_quota_tokens: licQuota.value } : {}),
      ...(licGroup.value.trim() ? { group: licGroup.value.trim() } : {}),
    }
    if (licExpires.value) body.expires_at = new Date(licExpires.value).toISOString()

    const res = await $fetch<Blob>(`${useRuntimeConfig().public.apiBaseUrl}/api/v1/admin/licenses`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${auth.token}`,
      },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res)
    const a = document.createElement('a')
    a.href = url
    a.download = `${licUsername.value.trim()}.lic`
    a.click()
    URL.revokeObjectURL(url)
    resetLic()
  } catch (e) {
    licError.value = errorMessageJa(e)
  } finally {
    licLoading.value = false
  }
}

// ─── Orders tab ──────────────────────────────────────────────────────────────
interface AdminOrderItem {
  id: string
  title: string
  serial: number
  token_cost: number
  status: string
  user_name: string
  assigned_creator_name: string | null
  notified_at: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
}

const adminOrders = ref<AdminOrderItem[]>([])
const adminOrdersLoading = ref(false)
const adminOrdersError = ref<string | null>(null)

async function fetchAdminOrders() {
  adminOrdersLoading.value = true
  adminOrdersError.value = null
  try {
    adminOrders.value = await api.get<AdminOrderItem[]>('/api/v1/orders')
  } catch (e) {
    adminOrdersError.value = errorMessageJa(e)
  } finally {
    adminOrdersLoading.value = false
  }
}

// ─── Archive tab (改訂2.2) ────────────────────────────────────────────────────
const archiveOrders = ref<AdminOrderItem[]>([])
const archiveLoading = ref(false)
const archiveError = ref<string | null>(null)
const expandedGroups = ref<Set<string>>(new Set())

async function fetchArchiveOrders() {
  archiveLoading.value = true
  archiveError.value = null
  try {
    archiveOrders.value = await api.get<AdminOrderItem[]>('/api/v1/orders?archived=true')
    // 初期: 全グループ展開
    expandedGroups.value = new Set(archiveOrders.value.map(o => yyyymmGroup(o.closed_at ?? o.updated_at)))
  } catch (e) {
    archiveError.value = errorMessageJa(e)
  } finally {
    archiveLoading.value = false
  }
}

// 年月でグループ化 (REDMINE 風)
function yyyymmGroup(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
function toggleGroup(g: string) {
  if (expandedGroups.value.has(g)) expandedGroups.value.delete(g)
  else expandedGroups.value.add(g)
}
function stripSerialFromTitle(t: string): string { return t.replace(/\s*#\d+\s*$/, '') }

const archiveGroups = computed(() => {
  const map = new Map<string, AdminOrderItem[]>()
  for (const o of archiveOrders.value) {
    const g = yyyymmGroup(o.closed_at ?? o.updated_at)
    if (!map.has(g)) map.set(g, [])
    map.get(g)!.push(o)
  }
  // 新しい順
  return Array.from(map.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([g, items]) => ({ group: g, items }))
})

const ORDER_STATUS_LABEL: Record<string, string> = {
  draft: 'Draft', open: 'Open', recruiting: '募集中',
  assigned: 'アサイン済', reviewing: 'レビュー中', done: '完了', cancelled: 'キャンセル',
}
const ORDER_STATUS_CLASS: Record<string, string> = {
  draft: 'bg-hairline-soft text-body',
  open: 'bg-primary/15 text-primary-active',
  recruiting: 'bg-primary/20 text-primary-active',
  assigned: 'bg-seagreen/15 text-seagreen-deep',
  reviewing: 'bg-[#f0a84022] text-[#b07000]',
  done: 'bg-[#2ecc7122] text-[#1a9950]',
  cancelled: 'bg-accent/15 text-accent',
}

// ─── Settings tab ─────────────────────────────────────────────────────────────
interface SystemSettingItem { key: string; value: string; description: string | null }

const settings = ref<SystemSettingItem[]>([])
const settingsLoading = ref(false)
const settingsError = ref<string | null>(null)
const settingSaving = ref<Record<string, boolean>>({})

async function fetchSettings() {
  settingsLoading.value = true
  settingsError.value = null
  try {
    settings.value = await api.get<SystemSettingItem[]>('/api/v1/admin/settings')
  } catch (e) {
    settingsError.value = errorMessageJa(e)
  } finally {
    settingsLoading.value = false
  }
}

async function toggleSetting(key: string, current: string) {
  const newVal = current === 'true' ? 'false' : 'true'
  settingSaving.value[key] = true
  try {
    await api.patch(`/api/v1/admin/settings/${key}`, { body: { value: newVal } })
    const s = settings.value.find(s => s.key === key)
    if (s) s.value = newVal
  } catch (e) {
    settingsError.value = errorMessageJa(e)
  } finally {
    settingSaving.value[key] = false
  }
}

// ── image_tag_presets / commission_item_visibility (JSON 値) ──
function parsedJsonSetting<T>(key: string, fallback: T): T {
  const s = settings.value.find(s => s.key === key)
  if (!s) return fallback
  try { return JSON.parse(s.value) as T } catch { return fallback }
}
const imageTagDraft = ref('')
const addedFlash = ref(false)
function addImageTag() {
  const tag = imageTagDraft.value.trim().toLowerCase()
  if (!tag) return
  const current = parsedJsonSetting<string[]>('image_tag_presets', [])
  if (current.includes(tag)) { imageTagDraft.value = ''; return }
  void saveJsonSetting('image_tag_presets', [...current, tag])
  imageTagDraft.value = ''
  addedFlash.value = true
  window.setTimeout(() => { addedFlash.value = false }, 400)
}
const tagPendingDelete = ref<string | null>(null)
function askRemoveImageTag(tag: string) {
  tagPendingDelete.value = tag
}
async function confirmRemoveImageTag() {
  const tag = tagPendingDelete.value
  if (!tag) return
  const current = parsedJsonSetting<string[]>('image_tag_presets', [])
  await saveJsonSetting('image_tag_presets', current.filter(t => t !== tag))
  tagPendingDelete.value = null
}

// 設定タブのアコーディオン状態 (1 つだけ展開)
const expandedSettingKey = ref<string | null>(null)
function toggleSettingPanel(key: string) {
  expandedSettingKey.value = expandedSettingKey.value === key ? null : key
}
// commission 項目一覧の step 単位ゼブラ用ヘルパー
function stepNum(step: string): number {
  return Number(step.replace(/\D/g, '')) || 0
}
function isStepHead(idx: number): boolean {
  return COMMISSION_ITEM_LABELS[idx]?.step !== COMMISSION_ITEM_LABELS[idx - 1]?.step
}
// image_tag チップ: タグ名から決定的に淡色を割当てて識別性を上げる (tag パレット = 例外色)
const TAG_CHIP_PALETTE = [
  'bg-seagreen/15 text-seagreen-deep border-seagreen/35',
  'bg-admin/15 text-admin-deep border-admin/35',
  'bg-licensee/30 text-licensee-deep border-licensee/50',
  'bg-primary/15 text-primary-active border-primary/35',
  'bg-accent/12 text-accent border-accent/30',
]
function tagChipClass(tag: string): string {
  let h = 0
  for (let i = 0; i < tag.length; i++) h = (h * 31 + tag.charCodeAt(i)) >>> 0
  return TAG_CHIP_PALETTE[h % TAG_CHIP_PALETTE.length]!
}
// Commission 項目で OFF (非表示) になっている数
const commissionHiddenCount = computed(() => {
  const m = parsedJsonSetting<Record<string, boolean>>('commission_item_visibility', {})
  return COMMISSION_ITEM_LABELS.filter(it => m[it.key] === false).length
})
async function saveJsonSetting(key: string, value: unknown) {
  settingSaving.value[key] = true
  try {
    const str = JSON.stringify(value)
    await api.patch(`/api/v1/admin/settings/${key}`, { body: { value: str } })
    const s = settings.value.find(s => s.key === key)
    if (s) s.value = str
    // ストアキャッシュを破棄して次回 fetch 時に更新を取り込む
    system.invalidateAdminConfig()
  } catch (e) {
    settingsError.value = errorMessageJa(e)
  } finally {
    settingSaving.value[key] = false
  }
}
async function toggleCommissionItem(item: string) {
  const current = parsedJsonSetting<Record<string, boolean>>('commission_item_visibility', {})
  const next = { ...current, [item]: !(current[item] ?? true) }
  await saveJsonSetting('commission_item_visibility', next)
}

const COMMISSION_ITEM_LABELS: Array<{ key: string; label: string; step: string }> = [
  { key: 'sound_type',            label: 'サウンドタイプ',         step: 'Step 1' },
  { key: 'purpose',               label: '用途',                   step: 'Step 1' },
  { key: 'length_sec',            label: '曲の長さ',               step: 'Step 1' },
  { key: 'desired_deadline',      label: '希望締切日',             step: 'Step 1' },
  { key: 'bgm_scenes',            label: 'BGM: 使用シーン',        step: 'Step 2' },
  { key: 'bgm_loop',              label: 'BGM: ループ',            step: 'Step 2' },
  { key: 'bgm_note',              label: 'BGM: シーン補足',        step: 'Step 2' },
  { key: 'se_trigger',            label: 'SE: トリガー',           step: 'Step 2' },
  { key: 'se_functions',          label: 'SE: 役割',               step: 'Step 2' },
  { key: 'se_slots',              label: 'SE: バリエーション数',   step: 'Step 2' },
  { key: 'emotions_target',       label: '狙う感情',               step: 'Step 3' },
  { key: 'emotions_avoid',        label: '避けたい感情',           step: 'Step 3' },
  { key: 'memory_impression',     label: '記憶に残したいイメージ', step: 'Step 3' },
  { key: 'tx_organic_electronic', label: 'テクスチャ: 有機/電子',  step: 'Step 4' },
  { key: 'tx_melody_rhythm',      label: 'テクスチャ: メロ/リズム',step: 'Step 4' },
  { key: 'tx_warm_cold',          label: 'テクスチャ: 温/冷',      step: 'Step 4' },
  { key: 'tx_sparse_dense',       label: 'テクスチャ: シンプル/重',step: 'Step 4' },
  { key: 'tx_static_dynamic',     label: 'テクスチャ: 静/動',      step: 'Step 4' },
  { key: 'reference_urls',        label: '参考音源 URL',           step: 'Step 5' },
  { key: 'reference_elements',    label: '参考にしたい要素',       step: 'Step 5' },
  { key: 'reference_avoid',       label: '避けたい要素',           step: 'Step 5' },
  { key: 'delivery_format',       label: '納品形式',               step: 'Step 6' },
  { key: 'note',                  label: 'その他補足',             step: 'Step 6' },
]

// ─── Logs tab (Admin activity log) ────────────────────────────────────────────

type LogSub = 'creators' | 'users'
type Signal = 'green' | 'yellow' | 'red'
type LogDays = 7 | 30 | 90

interface LogMetricsBase {
  session_count: number
  active_days: number
}
interface UserMetricsRow extends LogMetricsBase {
  download_count: number
  tokens_used: number
  monthly_quota: number
  favorite_added: number
  commission_count: number
}
interface CreatorMetricsRow extends LogMetricsBase {
  upload_count: number
  sold_count: number
  sell_rate: number
  earnings_pending: number
  earnings_paid: number
  commission_done_count: number
  message_count: number
}
interface UserLogRow {
  user_id: string
  username: string
  role: string
  score: number
  signal: Signal
  metrics: UserMetricsRow
  last_active_at: string | null
}
interface CreatorLogRow {
  creator_id: string
  username: string
  display_name: string
  rank: string
  score: number
  signal: Signal
  metrics: CreatorMetricsRow
  last_active_at: string | null
}
interface Bucket { date: string; value: number }
interface HeatCell { weekday: number; hour: number; count: number }
interface EventRow { ts: string; kind: string; detail: string }
interface UserDetail {
  user_id: string; username: string; score: number; signal: Signal
  metrics: UserMetricsRow
  heatmap: HeatCell[]
  sparkline: { sessions: Bucket[]; downloads: Bucket[]; tokens: Bucket[] }
  events: EventRow[]
}
interface CreatorDetail {
  creator_id: string; username: string; display_name: string; rank: string
  score: number; signal: Signal
  metrics: CreatorMetricsRow
  rank_median: Record<string, number>
  heatmap: HeatCell[]
  sparkline: {
    sessions: Bucket[]; uploads: Bucket[]; sold: Bucket[]; earnings: Bucket[]
  }
  events: EventRow[]
}

const logSub = ref<LogSub>('creators')
// ログ サブタブ (Creator / Licensee) を Users の role フィルタと同じロール色に
const LOG_SUB_CLASS: Record<LogSub, { on: string; off: string }> = {
  creators: { on: 'bg-seagreen text-white', off: 'border border-hairline-strong text-seagreen-deep hover:border-seagreen' },
  users:    { on: 'bg-licensee text-ink',   off: 'border border-hairline-strong text-licensee-deep hover:border-licensee' },
}
const logDays = ref<LogDays>(30)
const userLogs = ref<UserLogRow[]>([])
const creatorLogs = ref<CreatorLogRow[]>([])
const logsLoading = ref(false)
const logsError = ref<string | null>(null)

// 行クリックで詳細展開 (複数同時展開可)
const expandedDetails = ref<Map<string, UserDetail | CreatorDetail>>(new Map())
const detailLoading = ref<Set<string>>(new Set())

async function fetchLogs() {
  logsLoading.value = true
  logsError.value = null
  try {
    if (logSub.value === 'creators') {
      creatorLogs.value = await api.get<CreatorLogRow[]>(
        `/api/v1/admin/logs/creators?days=${logDays.value}`,
      )
    } else {
      userLogs.value = await api.get<UserLogRow[]>(
        `/api/v1/admin/logs/users?days=${logDays.value}`,
      )
    }
    expandedDetails.value.clear()
  } catch (err: unknown) {
    logsError.value = (err as { data?: { detail?: { message?: string } } })?.data?.detail?.message
      ?? '読み込みに失敗しました'
  } finally {
    logsLoading.value = false
  }
}

async function toggleDetail(id: string) {
  if (expandedDetails.value.has(id)) {
    expandedDetails.value.delete(id)
    return
  }
  detailLoading.value.add(id)
  try {
    const path = logSub.value === 'creators'
      ? `/api/v1/admin/logs/creators/${id}/detail?days=${logDays.value}`
      : `/api/v1/admin/logs/users/${id}/detail?days=${logDays.value}`
    const data = await api.get<UserDetail | CreatorDetail>(path)
    expandedDetails.value.set(id, data)
  } catch (err: unknown) {
    alert((err as { data?: { detail?: { message?: string } } })?.data?.detail?.message ?? '詳細の取得に失敗しました')
  } finally {
    detailLoading.value.delete(id)
  }
}

// 期間 / サブタブ変更で再フェッチ
watch([logSub, logDays], () => {
  if (tab.value === 'logs') fetchLogs()
})

const SIGNAL_DOT_COLOR: Record<Signal, string> = {
  green: '#2ecc71',
  yellow: '#f0a840',
  red: '#e74c3c',
}

// KPI 計算 (一覧から)
const kpi = computed(() => {
  if (logSub.value === 'creators') {
    const rows = creatorLogs.value
    return {
      total: rows.length,
      active: rows.filter(r => r.signal === 'green').length,
      avgScore: rows.length === 0 ? 0
        : Math.round(rows.reduce((s, r) => s + r.score, 0) / rows.length),
      alert: rows.filter(r => r.signal === 'red').length,
    }
  }
  const rows = userLogs.value
  return {
    total: rows.length,
    active: rows.filter(r => r.signal === 'green').length,
    avgScore: rows.length === 0 ? 0
      : Math.round(rows.reduce((s, r) => s + r.score, 0) / rows.length),
    alert: rows.filter(r => r.signal === 'red').length,
  }
})

function formatRelTime(iso: string | null): string {
  if (!iso) return 'なし'
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  const day = Math.floor(diff / 86_400_000)
  if (day === 0) return '今日'
  if (day === 1) return '昨日'
  if (day < 30) return `${day}日前`
  return d.toLocaleDateString('ja-JP')
}

// Creator のレーダーチャート軸定義
const CREATOR_RADAR_AXES = [
  { key: 'active_days',           label: 'アクセス',    max: 30 },
  { key: 'upload_count',          label: 'UL',          max: 10 },
  { key: 'sell_rate',             label: '販売率',      max: 1 },
  { key: 'commission_done_count', label: 'Commission', max: 5 },
  { key: 'message_count',         label: 'メッセージ',  max: 30 },
]

// ─── Load on tab change ───────────────────────────────────────────────────────
watch(tab, (t) => {
  if ((t === 'users' || t === 'tokens') && users.value.length === 0) fetchUsers()
  if (t === 'payouts') fetchPayouts()
  if (t === 'orders') fetchAdminOrders()
  if (t === 'archive') fetchArchiveOrders()
  if (t === 'logs') fetchLogs()
  if (t === 'settings') fetchSettings()
}, { immediate: true })
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- Header -->
    <div class="flex shrink-0 items-center gap-3 py-5">
      <h1 class="font-mono text-[13px] font-bold uppercase tracking-widest text-admin-deep">Admin</h1>
    </div>

    <!-- Tabs -->
    <div class="flex shrink-0 flex-wrap gap-4 border-b border-hairline-soft pb-0">
      <button
        v-for="t in ([['users','Users'],['payouts','Payout'],['tokens','Token付与'],['licenses','lic発行'],['orders','Commission'],['archive','アーカイブ'],['logs','ログ'],['settings','設定']] as [Tab, string][])"
        :key="t[0]"
        class="relative pb-2 text-[14px] font-semibold transition-all"
        :class="[
          tab === t[0] ? 'filter-active' : 'opacity-40 hover:opacity-70',
          tabArea(t[0]).action > 0 || tabArea(t[0]).info ? 'text-notify' : 'text-ink',
        ]"
        @click="t[0] === 'orders' ? router.push('/orders') : (tab = t[0])"
      >
        <!-- NOTIFICATION_SPEC §3 Level 3: 要対応なら件数、情報のみなら小ドット -->
        <span
          v-if="tabArea(t[0]).action > 0"
          class="mr-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 align-middle font-mono text-[10px] font-bold text-white"
          style="background:#ffa500;"
        >{{ tabArea(t[0]).action }}</span>
        <span
          v-else-if="tabArea(t[0]).info"
          class="mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle"
          style="background:#ffa500;"
          title="確認が必要な情報があります"
        />
        {{ t[1] }}
        <span v-if="tab === t[0]" class="absolute inset-x-0 -bottom-px h-0.5 rounded-sm bg-primary" />
      </button>
    </div>

    <div class="flex-1 overflow-y-auto py-4">

      <!-- ① Users 管理 -->
      <div v-if="tab === 'users'">

        <!-- role フィルタ + 更新 -->
        <div class="mb-3 flex items-center gap-4">
          <div class="flex gap-2">
            <button
              v-for="r in (['creator','licensee'] as RoleFilter[])"
              :key="r"
              class="rounded-full px-3 py-1 text-[11px] font-semibold transition-colors"
              :class="ROLE_FILTER_CLASS[r][roleFilter === r ? 'on' : 'off']"
              @click="roleFilter = r"
            >{{ r === 'creator' ? 'Creator' : 'Licensee' }}</button>
          </div>
          <button class="ml-auto text-[11px] text-muted hover:text-ink" @click="fetchUsers">↻ 更新</button>
        </div>

        <!-- User: group filter -->
        <div v-if="roleFilter === 'licensee' && availableGroups.length > 0" class="mb-3 flex flex-wrap gap-2">
          <button
            v-for="g in ['all', ...availableGroups, '__none__']"
            :key="g"
            class="rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold transition-all"
            :class="groupFilter === g
              ? 'border-primary bg-primary/10 text-primary-active'
              : 'border-hairline text-muted hover:text-ink'"
            @click="groupFilter = g"
          >{{ g === 'all' ? '全員' : g === '__none__' ? '未所属' : g }}</button>
        </div>

        <div v-if="usersLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>
        <div v-else-if="usersError" class="py-4 text-center text-[12px] text-accent">{{ usersError }}</div>

        <!-- Creator 一覧 -->
        <div v-else-if="roleFilter === 'creator'" class="space-y-1.5">
          <div v-for="u in creatorList" :key="u.id">
            <!-- Creator 行 -->
            <button
              class="card w-full cursor-pointer px-4 py-3 text-left transition-colors hover:border-primary"
              :class="expandedStats.has(u.id) ? 'border-primary' : ''"
              @click="toggleStats(u.id)"
            >
              <div class="flex items-center gap-3">
                <!-- expand icon -->
                <svg
                  width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                  class="shrink-0 text-muted transition-transform"
                  :class="expandedStats.has(u.id) ? 'rotate-90' : ''"
                ><path d="m9 18 6-6-6-6"/></svg>

                <!-- role + rank badge -->
                <span
                  class="shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase"
                  :class="u.role === 'admin'
                    ? 'bg-admin/15 text-admin-deep border-admin/35'
                    : u.role === 'creator'
                      ? 'bg-seagreen/15 text-seagreen-deep border-seagreen/35'
                      : 'bg-licensee/25 text-licensee-deep border-licensee/40'"
                >{{ u.role }}</span>
                <span v-if="u.rank" class="shrink-0 rounded border border-hairline-strong bg-surface-strong/80 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-body-strong">{{ u.rank }}</span>

                <!-- name -->
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[13px] font-medium text-ink">
                    {{ u.display_name || u.username }}
                    <span v-if="u.display_name" class="ml-1 font-mono text-[11px] text-muted">@{{ u.username }}</span>
                  </p>
                  <p class="font-mono text-[10px] text-muted">{{ u.license_code ?? '—' }}</p>
                </div>

                <!-- quick stats summary (loaded state) -->
                <div v-if="creatorStats[u.id]" class="shrink-0 text-right">
                  <p class="font-mono text-[11px] text-ink">
                    {{ creatorStats[u.id]!.total_uploads }}UP
                    <span class="mx-1 text-muted">·</span>
                    {{ creatorStats[u.id]!.total_sold }}DL
                  </p>
                  <p class="font-mono text-[10px]" :class="creatorStats[u.id]!.payout_pending_yen > 0 ? 'text-accent' : 'text-muted'">
                    {{ creatorStats[u.id]!.payout_pending_yen > 0
                      ? `未払 ¥${creatorStats[u.id]!.payout_pending_yen.toLocaleString()}`
                      : `累計 ¥${creatorStats[u.id]!.payout_total_yen.toLocaleString()}` }}
                  </p>
                </div>

                <!-- rank selector + DM button -->
                <div class="shrink-0 flex items-center gap-1.5" @click.stop>
                  <button
                    class="rounded border border-hairline-strong bg-white/80 px-2 py-1 font-mono text-[11px] text-body transition-colors hover:border-accent hover:text-accent"
                    title="creator に DM を送る"
                    @click="openDmModal(u.id, u.display_name || u.username)"
                  >DM</button>
                  <select
                    class="rounded border border-hairline-strong bg-white/80 px-2 py-1 font-mono text-[11px] text-ink outline-none"
                    :value="u.rank ?? 'bronze'"
                    :disabled="!!rankLoading[u.id]"
                    @change="changeRank(u.id, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="r in RANKS" :key="r" :value="r">{{ r }}</option>
                  </select>
                  <span v-if="rankError[u.id]" class="text-[10px] text-accent">{{ rankError[u.id] }}</span>
                </div>
              </div>
            </button>

            <!-- Stats パネル (展開時) -->
            <div v-if="expandedStats.has(u.id)" class="ml-6 mt-1 rounded-xl border border-hairline-soft bg-white/50 px-5 py-4">
              <div v-if="statsLoading[u.id]" class="py-2 text-center text-[12px] text-muted">読み込み中…</div>
              <template v-else-if="creatorStats[u.id]">
                <div :key="u.id" class="space-y-4">
                  <!-- 累計サマリ -->
                  <div class="grid grid-cols-3 gap-3">
                    <div class="rounded-lg border border-hairline-soft bg-surface-strong/40 px-3 py-2.5 text-center">
                      <p class="font-mono text-[18px] font-semibold text-ink">{{ creatorStats[u.id]!.total_uploads }}</p>
                      <p class="mt-0.5 font-mono text-[10px] text-muted uppercase tracking-wider">Total UP</p>
                    </div>
                    <div class="rounded-lg border border-hairline-soft bg-surface-strong/40 px-3 py-2.5 text-center">
                      <p class="font-mono text-[18px] font-semibold text-ink">{{ creatorStats[u.id]!.total_sold }}</p>
                      <p class="mt-0.5 font-mono text-[10px] text-muted uppercase tracking-wider">Total DL</p>
                    </div>
                    <div class="rounded-lg border border-hairline-soft bg-surface-strong/40 px-3 py-2.5 text-center">
                      <p class="font-mono text-[18px] font-semibold text-ink">{{ creatorStats[u.id]!.total_unsold }}</p>
                      <p class="mt-0.5 font-mono text-[10px] text-muted uppercase tracking-wider">残</p>
                    </div>
                  </div>

                  <!-- 支払サマリ -->
                  <div class="flex items-center gap-4 rounded-lg border border-hairline-soft bg-surface-strong/40 px-4 py-2.5">
                    <div>
                      <p class="font-mono text-[10px] uppercase tracking-wider text-muted">支払累計</p>
                      <p class="font-mono text-[14px] font-semibold text-ink">¥{{ creatorStats[u.id]!.payout_total_yen.toLocaleString() }}</p>
                    </div>
                    <div class="h-6 w-px bg-hairline-soft" />
                    <div>
                      <p class="font-mono text-[10px] uppercase tracking-wider text-muted">未払い</p>
                      <p class="font-mono text-[14px] font-semibold" :class="creatorStats[u.id]!.payout_pending_yen > 0 ? 'text-accent' : 'text-muted'">
                        ¥{{ creatorStats[u.id]!.payout_pending_yen.toLocaleString() }}
                      </p>
                    </div>
                    <button
                      v-if="creatorStats[u.id]!.payout_pending_yen > 0"
                      class="ml-auto rounded border border-primary/40 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary-active hover:bg-primary/20"
                      @click="tab = 'payouts'"
                    >Payout 確認 →</button>
                  </div>

                  <!-- 月次テーブル -->
                  <div v-if="creatorStats[u.id]!.monthly.length > 0">
                    <p class="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">月次 (直近 {{ creatorStats[u.id]!.monthly.length }} ヶ月)</p>
                    <table class="w-full border-collapse font-mono text-[11px]">
                      <thead>
                        <tr class="border-b border-hairline-soft text-left text-muted">
                          <th class="pb-1.5 pr-4 font-semibold">月</th>
                          <th class="pb-1.5 pr-4 text-right font-semibold">UP</th>
                          <th class="pb-1.5 text-right font-semibold">DL</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="m in [...creatorStats[u.id]!.monthly].reverse()"
                          :key="m.yyyymm"
                          class="border-b border-hairline-soft/50 last:border-0"
                        >
                          <td class="py-1.5 pr-4 text-body">{{ fmtMonth(m.yyyymm) }}</td>
                          <td class="py-1.5 pr-4 text-right text-ink">{{ m.uploads }}</td>
                          <td class="py-1.5 text-right" :class="m.dls > 0 ? 'text-primary-active font-semibold' : 'text-muted'">{{ m.dls }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p v-else class="text-center text-[12px] text-muted">まだ活動記録がありません。</p>
                </div>
              </template>
              <p v-else class="text-center text-[12px] text-muted">統計を取得できませんでした。</p>
            </div>
          </div>
        </div>

        <!-- User 一覧 -->
        <div v-else class="space-y-1.5">
          <div
            v-for="u in filteredUsers"
            :key="u.id"
            class="card flex items-center gap-3 px-4 py-3"
          >
            <!-- role badge -->
            <span class="shrink-0 rounded border border-licensee/40 bg-licensee/25 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase text-licensee-deep">licensee</span>

            <!-- name / license / token -->
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13px] font-medium text-ink">{{ u.username }}</p>
              <p class="font-mono text-[10px] text-muted">
                {{ u.license_code ?? '—' }}
                <span v-if="u.monthly_quota_tokens !== null"> · {{ u.monthly_quota_tokens.toLocaleString() }} tk/月</span>
              </p>
            </div>

            <!-- group 表示 / インライン編集 -->
            <div class="flex shrink-0 items-center gap-1.5">
              <template v-if="editingGroupId === u.id">
                <input
                  v-model="editGroupValue"
                  type="text"
                  maxlength="64"
                  placeholder="グループ名"
                  class="w-32 rounded border border-primary/60 bg-white/90 px-2 py-1 font-mono text-[11px] text-ink outline-none"
                  @keydown.enter="saveGroup(u)"
                  @keydown.esc="cancelEditGroup"
                />
                <button
                  class="rounded border border-primary/40 bg-primary/10 px-2 py-1 text-[10px] font-medium text-primary-active hover:bg-primary/20 disabled:opacity-40"
                  :disabled="groupSaving"
                  @click="saveGroup(u)"
                >保存</button>
                <button class="text-[10px] text-muted hover:text-ink" @click="cancelEditGroup">×</button>
                <p v-if="groupError" class="text-[10px] text-accent">{{ groupError }}</p>
              </template>
              <template v-else>
                <span
                  class="max-w-[96px] truncate rounded-full border border-hairline px-2 py-0.5 font-mono text-[10px] text-body"
                  :class="u.group_name ? '' : 'text-muted italic'"
                >{{ u.group_name || '未所属' }}</span>
                <button class="text-[10px] text-muted hover:text-ink" :aria-label="'グループ編集'" @click="startEditGroup(u)">✎</button>
              </template>
            </div>

            <!-- token shortcut -->
            <button
              class="shrink-0 rounded border border-hairline px-2 py-1 text-[11px] text-body hover:border-primary hover:text-primary-active"
              @click="tab = 'tokens'; grantUserId = u.id"
            >+ Token</button>
          </div>

          <p v-if="filteredUsers.length === 0 && !usersLoading" class="py-6 text-center text-[12px] text-muted">
            {{ groupFilter === 'all' ? 'ユーザがいません。' : 'このグループにユーザがいません。' }}
          </p>
        </div>
      </div>

      <!-- ② Payout -->
      <div v-if="tab === 'payouts'">
        <div class="mb-3 flex items-center gap-4">
          <span class="text-[11px] font-semibold uppercase tracking-widest text-body-strong">Creator 支払い</span>
          <div class="flex gap-2">
            <button
              v-for="f in (['pending','all'] as const)"
              :key="f"
              class="rounded-full px-3 py-1 text-[11px] font-semibold transition-colors"
              :class="payoutFilter === f
                ? 'bg-ink text-canvas'
                : 'border border-hairline-strong text-body hover:border-primary hover:text-ink'"
              @click="payoutFilter = f; fetchPayouts()"
            >{{ f === 'pending' ? '未払い' : '全件' }}</button>
          </div>
          <button class="ml-auto text-[11px] text-muted hover:text-ink" @click="fetchPayouts">↻ 更新</button>
        </div>

        <div v-if="payoutsLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>
        <div v-else-if="payoutsError" class="py-4 text-center text-[12px] text-accent">{{ payoutsError }}</div>
        <div v-else-if="creatorGroups.length === 0" class="py-8 text-center text-[12px] text-muted">
          {{ payoutFilter === 'pending' ? '未払いの支払いはありません。' : '支払い記録がありません。' }}
        </div>

        <div v-else class="space-y-1.5">
          <div v-for="g in creatorGroups" :key="g.creator_id">
            <button
              class="card relative w-full cursor-pointer px-4 py-3 text-left transition-colors hover:border-primary"
              :class="expandedCreators.has(g.creator_id) ? 'border-primary' : ''"
              @click="toggleCreator(g.creator_id)"
            >
              <!-- NOTIFICATION_SPEC §3 Level 4: 未払いがあれば金ドット -->
              <span
                v-if="g.pending_count > 0"
                class="absolute -left-0.5 -top-0.5 h-2 w-2 rounded-full"
                style="background:#ffd700;box-shadow:0 0 4px #ffd700cc;"
                aria-label="未払いあり"
              />
              <div class="flex items-center gap-4">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                  class="shrink-0 text-muted transition-transform"
                  :class="expandedCreators.has(g.creator_id) ? 'rotate-90' : ''"
                ><path d="m9 18 6-6-6-6"/></svg>
                <span class="shrink-0 rounded border border-hairline-strong bg-surface-strong/80 px-2 py-0.5 font-mono text-[10px] font-semibold text-body-strong">{{ g.rank }}</span>
                <span class="flex-1 text-[13px] font-medium text-ink">{{ g.creator_name ?? '(不明)' }}</span>
                <span v-if="g.pending_count > 0" class="shrink-0 font-mono text-[12px] font-semibold text-accent">
                  ¥{{ g.pending_total.toLocaleString() }}
                  <span class="ml-1 text-[10px] font-normal text-muted">未払い {{ g.pending_count }}件</span>
                </span>
                <span v-else class="shrink-0 font-mono text-[11px] text-muted">支払済 ¥{{ g.paid_total.toLocaleString() }}</span>
              </div>
            </button>
            <div v-if="expandedCreators.has(g.creator_id)" class="ml-4 mt-1 space-y-1">
              <div
                v-for="p in g.payouts" :key="p.id"
                class="relative flex items-center gap-3 rounded-lg border border-hairline-soft bg-white/50 px-4 py-2.5"
              >
                <!-- NOTIFICATION_SPEC §3 Level 4: 未払い行に金ドット -->
                <span
                  v-if="p.status === 'pending'"
                  class="absolute -left-0.5 -top-0.5 h-2 w-2 rounded-full"
                  style="background:#ffd700;box-shadow:0 0 4px #ffd700cc;"
                  aria-label="未払い"
                />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[12px] font-medium text-ink">{{ p.audio_title ?? '(不明)' }}</p>
                  <p class="font-mono text-[10px] text-muted">{{ new Date(p.created_at).toLocaleDateString('ja-JP') }}</p>
                </div>
                <span class="shrink-0 font-mono text-[12px] font-semibold text-ink">¥{{ p.amount_yen.toLocaleString() }}</span>
                <span
                  class="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
                  :class="p.status === 'paid' ? 'bg-primary/15 text-primary-active' : p.status === 'cancelled' ? 'bg-hairline-soft text-muted' : 'bg-accent/15 text-accent'"
                >{{ p.status }}</span>
                <button
                  v-if="p.status === 'pending'"
                  class="shrink-0 rounded border border-primary/40 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary-active transition-colors hover:bg-primary/20 disabled:opacity-40"
                  :disabled="!!paidLoading[p.id]"
                  @click.stop="markPaid(p.id)"
                >支払済にする</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ③ Token 付与 -->
      <div v-if="tab === 'tokens'" class="max-w-[480px]">
        <p class="mb-4 text-[11px] font-semibold uppercase tracking-widest text-body-strong">Token 追加付与</p>
        <div class="card space-y-4 p-5">
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">
              対象利用者 <span class="text-accent">*</span>
              <span class="ml-1 font-normal normal-case tracking-normal text-muted">(role=licensee のみ)</span>
            </label>
            <div v-if="usersLoading" class="py-2 text-[12px] text-muted">読み込み中…</div>
            <div v-else-if="userOnlyList.length === 0" class="rounded-md border border-hairline-soft bg-surface-strong/40 px-3 py-2 text-[12px] text-muted">
              role=licensee のアカウントがまだありません。
            </div>
            <select
              v-else
              v-model="grantUserId"
              class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[12px] text-ink outline-none transition-colors focus:border-primary"
            >
              <option value="" disabled>利用者を選択…</option>
              <option v-for="u in userOnlyList" :key="u.id" :value="u.id">
                {{ u.username }}<template v-if="u.group_name"> ({{ u.group_name }})</template>
                <template v-if="u.monthly_quota_tokens !== null">（月{{ u.monthly_quota_tokens.toLocaleString() }}tk）</template>
              </option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">付与 token 量</label>
            <div class="flex items-center gap-2">
              <input v-model.number="grantTokens" type="number" min="1"
                class="w-32 rounded-md border border-hairline-strong bg-white/85 px-3 py-2 font-mono text-[12px] text-ink outline-none transition-colors focus:border-primary" />
              <span class="text-[11px] text-muted">tk ({{ Math.floor(grantTokens / 3600) }}h {{ Math.floor((grantTokens % 3600) / 60) }}m)</span>
            </div>
          </div>
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">理由 (任意)</label>
            <input v-model="grantReason" type="text" placeholder="例: キャンペーン付与"
              class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[12px] text-ink placeholder:text-muted outline-none transition-colors focus:border-primary" />
          </div>
          <p v-if="grantError" class="rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-[12px] text-accent">{{ grantError }}</p>
          <p v-if="grantSuccess" class="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-[12px] text-primary-active">{{ grantSuccess }}</p>
          <div class="flex gap-2">
            <button class="rounded-md border border-hairline bg-white/60 px-4 py-2 text-[12px] text-body hover:text-ink disabled:opacity-40" :disabled="grantLoading" @click="resetGrant">キャンセル</button>
            <button
              class="btn-primary"
              :disabled="!grantUserId || grantTokens <= 0 || grantLoading"
              @click="submitGrant"
            >
              <svg v-if="grantLoading" class="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              付与する
            </button>
          </div>
        </div>
      </div>

      <!-- ④ lic 発行 -->
      <div v-if="tab === 'licenses'" class="max-w-[480px]">
        <p class="mb-4 text-[11px] font-semibold uppercase tracking-widest text-body-strong">lic ファイル発行</p>
        <div class="card space-y-4 p-5">
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">ユーザ名 <span class="text-accent">*</span></label>
            <input v-model="licUsername" type="text" maxlength="32" placeholder="半角英数字・記号 (-_.) 1〜32文字"
              class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[12px] text-ink placeholder:text-muted outline-none transition-colors focus:border-primary" />
          </div>
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">ロール</label>
            <div class="flex gap-2">
              <button
                v-for="r in ['licensee','creator','admin'] as const" :key="r" type="button"
                class="rounded-full border px-3 py-1 text-[11px] font-medium transition-colors"
                :class="LIC_ROLE_CLASS[r][licRole === r ? 'on' : 'off']"
                @click="licRole = r"
              >{{ r }}</button>
            </div>
          </div>
          <!-- token: user のみ表示 -->
          <div v-if="licRole === 'licensee'">
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">月間 token</label>
            <div class="flex items-center gap-2">
              <input v-model.number="licQuota" type="number" min="0"
                class="w-32 rounded-md border border-hairline-strong bg-white/85 px-3 py-2 font-mono text-[12px] text-ink outline-none transition-colors focus:border-primary" />
              <span class="text-[11px] text-muted">tk / 月</span>
            </div>
          </div>
          <!-- group: 任意 -->
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">
              グループ / 会社名
              <span class="ml-1 font-normal normal-case tracking-normal text-muted">(任意)</span>
            </label>
            <input v-model="licGroup" type="text" maxlength="64" placeholder="例: SoundFactory"
              class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[12px] text-ink placeholder:text-muted outline-none transition-colors focus:border-primary" />
          </div>
          <div>
            <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-body-strong">有効期限 (省略=無期限)</label>
            <input v-model="licExpires" type="date"
              class="rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[12px] text-ink outline-none transition-colors focus:border-primary" />
          </div>
          <p v-if="licError" class="rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-[12px] text-accent">{{ licError }}</p>
          <div class="flex gap-2">
            <button class="rounded-md border border-hairline bg-white/60 px-4 py-2 text-[12px] text-body hover:text-ink disabled:opacity-40" :disabled="licLoading" @click="resetLic">キャンセル</button>
            <button
              class="btn-primary"
              :disabled="!licUsername.trim() || licLoading"
              @click="issueLic"
            >
              <svg v-if="licLoading" class="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
              </svg>
              .lic を発行してダウンロード
            </button>
          </div>
        </div>
      </div>

      <!-- ⑤ 発注管理 -->
      <div v-if="tab === 'orders'">
        <div class="mb-3 flex items-center gap-4">
          <span class="text-[11px] font-semibold uppercase tracking-widest text-body-strong">発注チケット一覧</span>
          <button class="ml-auto text-[11px] text-muted hover:text-ink" @click="fetchAdminOrders">↻ 更新</button>
        </div>

        <div v-if="adminOrdersLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>
        <div v-else-if="adminOrdersError" class="py-4 text-center text-[12px] text-accent">{{ adminOrdersError }}</div>
        <div v-else-if="adminOrders.length === 0" class="py-8 text-center text-[12px] text-muted">発注チケットはまだありません。</div>

        <div v-else class="space-y-1.5">
          <NuxtLink
            v-for="order in adminOrders"
            :key="order.id"
            :to="`/orders/${order.id}`"
            class="card group flex cursor-pointer items-center gap-3 px-4 py-3 transition-all hover:-translate-y-px hover:border-primary hover:shadow-md"
          >
            <!-- #serial を ID として独立表示 (REDMINE 風) -->
            <span class="shrink-0 rounded-md bg-ink/5 px-2 py-0.5 font-mono text-[11px] font-semibold text-ink">#{{ order.serial }}</span>
            <span
              class="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
              :class="ORDER_STATUS_CLASS[order.status] ?? 'bg-hairline-soft text-body'"
            >{{ ORDER_STATUS_LABEL[order.status] ?? order.status }}</span>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-[13px] font-medium text-ink">{{ stripSerialFromTitle(order.title) }}</span>
              </div>
              <div class="mt-0.5 flex items-center gap-2 text-[10px] text-muted font-mono">
                <span>{{ order.user_name }}</span>
                <template v-if="order.assigned_creator_name">
                  <span>→</span><span>{{ order.assigned_creator_name }}</span>
                </template>
                <span class="h-1 w-1 rounded-full bg-muted" />
                <span>{{ order.token_cost }} tk</span>
                <span class="h-1 w-1 rounded-full bg-muted" />
                <span>{{ new Date(order.updated_at).toLocaleDateString('ja-JP') }}</span>
              </div>
            </div>

            <!-- 詳細を開くボタン (明示的にクリック可能) -->
            <span class="shrink-0 rounded-md bg-ink px-3 py-1 text-[11px] font-mono font-medium text-canvas transition-colors group-hover:bg-primary">
              Open
            </span>
          </NuxtLink>
        </div>
      </div>

      <!-- 改訂2.2: アーカイブ チケット (REDMINE 風) -->
      <div v-if="tab === 'archive'">
        <div class="mb-3 flex items-center gap-4">
          <span class="text-[11px] font-semibold uppercase tracking-widest text-body-strong">アーカイブ チケット</span>
          <span class="font-mono text-[10px] text-muted">{{ archiveOrders.length }} 件</span>
          <button class="ml-auto text-[11px] text-muted hover:text-ink" @click="fetchArchiveOrders">↻ 更新</button>
        </div>

        <div v-if="archiveLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>
        <div v-else-if="archiveError" class="py-4 text-[12px] text-accent">{{ archiveError }}</div>
        <div v-else-if="archiveOrders.length === 0" class="py-8 text-center text-[12px] text-muted">
          アーカイブされたチケットはありません。
        </div>

        <!-- REDMINE 風テーブル -->
        <div v-else class="overflow-hidden rounded-lg border border-hairline">
          <!-- ヘッダ -->
          <div class="grid grid-cols-[40px_60px_100px_1fr_140px_140px_100px] gap-3 bg-hairline-soft px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-body">
            <span></span>
            <span>#</span>
            <span>ステータス</span>
            <span>件名</span>
            <span>発注者</span>
            <span>担当 (creator)</span>
            <span>受取日</span>
          </div>

          <!-- 年月グループ -->
          <div v-for="g in archiveGroups" :key="g.group">
            <!-- グループヘッダ -->
            <button
              class="flex w-full items-center gap-2 border-t border-hairline bg-white/80 px-3 py-1.5 text-left text-[11px] font-semibold text-body transition-colors hover:bg-white"
              @click="toggleGroup(g.group)"
            >
              <svg
                width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                :class="expandedGroups.has(g.group) ? 'rotate-90' : ''"
                class="transition-transform"
              >
                <polyline points="9 18 15 12 9 6"/>
              </svg>
              <span>{{ g.group }}</span>
              <span class="rounded bg-primary/15 px-1.5 font-mono text-[10px] text-primary-active">{{ g.items.length }}</span>
            </button>
            <!-- 行 -->
            <div v-if="expandedGroups.has(g.group)">
              <NuxtLink
                v-for="row in g.items"
                :key="row.id"
                :to="`/orders/${row.id}`"
                class="grid grid-cols-[40px_60px_100px_1fr_140px_140px_100px] items-center gap-3 border-t border-hairline-soft bg-white/60 px-3 py-2 text-[12px] text-body transition-colors hover:bg-primary/5"
              >
                <span></span>
                <span class="font-mono text-ink">#{{ row.serial }}</span>
                <span class="font-mono text-[10px] text-muted">{{ ORDER_STATUS_LABEL[row.status] ?? row.status }}</span>
                <span class="truncate text-ink hover:underline">{{ stripSerialFromTitle(row.title) }}</span>
                <span class="truncate">{{ row.user_name }}</span>
                <span class="truncate text-muted">{{ row.assigned_creator_name ?? '-' }}</span>
                <span class="font-mono text-[11px] text-muted">{{ row.closed_at ? new Date(row.closed_at).toLocaleDateString('ja-JP') : '-' }}</span>
              </NuxtLink>
            </div>
          </div>
        </div>
      </div>

      <!-- ⑥ ログ (Admin activity log) -->
      <div v-if="tab === 'logs'">
        <!-- サブタブ + 期間 -->
        <div class="mb-4 flex flex-wrap items-center gap-3">
          <div class="flex gap-2">
            <button
              v-for="opt in ([['creators','Creator'],['users','Licensee']] as [LogSub, string][])"
              :key="opt[0]"
              class="rounded-full px-3 py-1 text-[11px] font-semibold transition-colors"
              :class="LOG_SUB_CLASS[opt[0]][logSub === opt[0] ? 'on' : 'off']"
              @click="logSub = opt[0]"
            >{{ opt[1] }}</button>
          </div>
          <div class="ml-auto flex items-center gap-1">
            <span class="mr-2 text-[10px] uppercase tracking-widest text-muted">期間</span>
            <button
              v-for="d in ([7, 30, 90] as LogDays[])"
              :key="d"
              class="rounded-md px-2 py-0.5 text-[11px] font-mono transition-colors"
              :class="logDays === d
                ? 'bg-primary/15 text-primary-active'
                : 'text-muted hover:text-ink'"
              @click="logDays = d"
            >{{ d }}日</button>
          </div>
        </div>

        <!-- KPI cards -->
        <div class="mb-4 grid grid-cols-4 gap-2">
          <div class="card px-3 py-2">
            <p class="text-[9px] uppercase tracking-widest text-muted">対象</p>
            <p class="font-mono text-[18px] font-bold text-ink">{{ kpi.total }}</p>
          </div>
          <div class="card px-3 py-2">
            <p class="text-[9px] uppercase tracking-widest text-muted">活発 (緑)</p>
            <p class="font-mono text-[18px] font-bold" style="color:#2ecc71">{{ kpi.active }}</p>
          </div>
          <div class="card px-3 py-2">
            <p class="text-[9px] uppercase tracking-widest text-muted">平均スコア</p>
            <p class="font-mono text-[18px] font-bold text-ink">{{ kpi.avgScore }}</p>
          </div>
          <div class="card px-3 py-2">
            <p class="text-[9px] uppercase tracking-widest text-muted">要注意 (赤)</p>
            <p class="font-mono text-[18px] font-bold" style="color:#e74c3c">{{ kpi.alert }}</p>
          </div>
        </div>

        <!-- Loading / Error -->
        <div v-if="logsLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>
        <div v-else-if="logsError" class="py-4 text-[12px] text-accent">{{ logsError }}</div>

        <!-- Creator list -->
        <div v-else-if="logSub === 'creators'" class="space-y-2">
          <div v-if="creatorLogs.length === 0" class="py-8 text-center text-[12px] text-muted">
            この期間のクリエイター活動はありません
          </div>
          <div v-for="row in creatorLogs" :key="row.creator_id" class="overflow-hidden">
            <button
              class="flex w-full items-center gap-3 rounded-lg border border-hairline-soft bg-white/50 px-4 py-2.5 text-left transition-colors hover:border-primary/30 hover:bg-white"
              @click="toggleDetail(row.creator_id)"
            >
              <ChartsSignalDot :signal="row.signal" />
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-2">
                  <span class="text-[13px] font-semibold text-ink">{{ row.display_name }}</span>
                  <span class="font-mono text-[10px] uppercase tracking-widest text-muted">{{ row.rank }} · @{{ row.username }}</span>
                </div>
                <div class="mt-0.5 flex items-center gap-3 font-mono text-[10px] text-muted">
                  <span>UL <span class="text-ink">{{ row.metrics.upload_count }}</span></span>
                  <span>販売 <span class="text-ink">{{ row.metrics.sold_count }}</span></span>
                  <span>収益 <span class="text-ink">¥{{ row.metrics.earnings_pending + row.metrics.earnings_paid }}</span></span>
                  <span>access <span class="text-ink">{{ row.metrics.active_days }}/{{ logDays }}d</span></span>
                  <span class="text-[9px]">last {{ formatRelTime(row.last_active_at) }}</span>
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <span class="font-mono text-[13px] font-bold text-ink">{{ row.score }}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted transition-transform" :class="expandedDetails.has(row.creator_id) ? 'rotate-90' : ''">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </div>
            </button>

            <!-- 詳細展開 -->
            <div v-if="expandedDetails.has(row.creator_id)" class="mt-1 rounded-lg border border-hairline bg-white/70 p-4">
              <div v-if="detailLoading.has(row.creator_id)" class="text-center text-[12px] text-muted">読み込み中…</div>
              <template v-else>
                <div class="grid grid-cols-2 gap-4">
                  <!-- Radar + 中央値 -->
                  <div>
                    <p class="mb-2 text-[10px] uppercase tracking-widest text-muted">ランク内比較 ({{ row.rank }} 中央値 = 点線)</p>
                    <ChartsRadarChart
                      :axes="CREATOR_RADAR_AXES"
                      :values="(expandedDetails.get(row.creator_id) as CreatorDetail).metrics as unknown as Record<string, number>"
                      :medians="(expandedDetails.get(row.creator_id) as CreatorDetail).rank_median"
                    />
                  </div>
                  <!-- Heatmap -->
                  <div>
                    <p class="mb-2 text-[10px] uppercase tracking-widest text-muted">アクセス時刻 (曜日 × 時間)</p>
                    <ChartsHeatmap :data="(expandedDetails.get(row.creator_id) as CreatorDetail).heatmap" />
                  </div>
                </div>

                <!-- Sparklines -->
                <div class="mt-4 grid grid-cols-3 gap-3">
                  <div>
                    <p class="text-[10px] text-muted">UL</p>
                    <ChartsBarChart :data="(expandedDetails.get(row.creator_id) as CreatorDetail).sparkline.uploads" color="#20b2aa" :height="60" />
                  </div>
                  <div>
                    <p class="text-[10px] text-muted">販売</p>
                    <ChartsBarChart :data="(expandedDetails.get(row.creator_id) as CreatorDetail).sparkline.sold" color="#2ecc71" :height="60" />
                  </div>
                  <div>
                    <p class="text-[10px] text-muted">収益</p>
                    <ChartsBarChart :data="(expandedDetails.get(row.creator_id) as CreatorDetail).sparkline.earnings" color="#f0a840" :height="60" />
                  </div>
                </div>

                <!-- Events -->
                <div class="mt-4">
                  <p class="mb-1 text-[10px] uppercase tracking-widest text-muted">直近イベント</p>
                  <div class="max-h-[160px] space-y-1 overflow-y-auto font-mono text-[11px]">
                    <p v-for="(ev, i) in (expandedDetails.get(row.creator_id) as CreatorDetail).events" :key="i" class="flex gap-2 text-body">
                      <span class="text-muted">{{ new Date(ev.ts).toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
                      <span class="text-primary-active">{{ ev.kind }}</span>
                      <span class="text-ink">{{ ev.detail }}</span>
                    </p>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- User list -->
        <div v-else class="space-y-2">
          <div v-if="userLogs.length === 0" class="py-8 text-center text-[12px] text-muted">
            この期間のユーザ活動はありません
          </div>
          <div v-for="row in userLogs" :key="row.user_id" class="overflow-hidden">
            <button
              class="flex w-full items-center gap-3 rounded-lg border border-hairline-soft bg-white/50 px-4 py-2.5 text-left transition-colors hover:border-primary/30 hover:bg-white"
              @click="toggleDetail(row.user_id)"
            >
              <ChartsSignalDot :signal="row.signal" />
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-2">
                  <span class="text-[13px] font-semibold text-ink">@{{ row.username }}</span>
                  <span class="font-mono text-[10px] uppercase tracking-widest" :class="roleTextClass(row.role)">{{ row.role }}</span>
                </div>
                <div class="mt-0.5 flex items-center gap-3 font-mono text-[10px] text-muted">
                  <span>DL <span class="text-ink">{{ row.metrics.download_count }}</span></span>
                  <span>token <span class="text-ink">{{ row.metrics.tokens_used }}/{{ row.metrics.monthly_quota }}</span></span>
                  <span>♥ <span class="text-ink">{{ row.metrics.favorite_added }}</span></span>
                  <span>Cm <span class="text-ink">{{ row.metrics.commission_count }}</span></span>
                  <span>access <span class="text-ink">{{ row.metrics.active_days }}/{{ logDays }}d</span></span>
                  <span class="text-[9px]">last {{ formatRelTime(row.last_active_at) }}</span>
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <span class="font-mono text-[13px] font-bold text-ink">{{ row.score }}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted transition-transform" :class="expandedDetails.has(row.user_id) ? 'rotate-90' : ''">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </div>
            </button>

            <div v-if="expandedDetails.has(row.user_id)" class="mt-1 rounded-lg border border-hairline bg-white/70 p-4">
              <div v-if="detailLoading.has(row.user_id)" class="text-center text-[12px] text-muted">読み込み中…</div>
              <template v-else>
                <!-- Heatmap -->
                <div>
                  <p class="mb-2 text-[10px] uppercase tracking-widest text-muted">アクセス時刻 (曜日 × 時間)</p>
                  <ChartsHeatmap :data="(expandedDetails.get(row.user_id) as UserDetail).heatmap" />
                </div>

                <!-- Sparklines -->
                <div class="mt-4 grid grid-cols-3 gap-3">
                  <div>
                    <p class="text-[10px] text-muted">起動</p>
                    <ChartsBarChart :data="(expandedDetails.get(row.user_id) as UserDetail).sparkline.sessions" color="#20b2aa" :height="60" />
                  </div>
                  <div>
                    <p class="text-[10px] text-muted">DL</p>
                    <ChartsBarChart :data="(expandedDetails.get(row.user_id) as UserDetail).sparkline.downloads" color="#2ecc71" :height="60" />
                  </div>
                  <div>
                    <p class="text-[10px] text-muted">Token 消費</p>
                    <ChartsBarChart :data="(expandedDetails.get(row.user_id) as UserDetail).sparkline.tokens" color="#f0a840" :height="60" />
                  </div>
                </div>

                <!-- Token quota gauge -->
                <div class="mt-4">
                  <p class="mb-1 text-[10px] uppercase tracking-widest text-muted">Token 月間残量</p>
                  <div class="h-2 overflow-hidden rounded-full bg-hairline-soft">
                    <div
                      class="h-full rounded-full bg-seagreen"
                      :style="{
                        width: ((expandedDetails.get(row.user_id) as UserDetail).metrics.monthly_quota === 0 ? 0 : Math.min(100, ((expandedDetails.get(row.user_id) as UserDetail).metrics.tokens_used / (expandedDetails.get(row.user_id) as UserDetail).metrics.monthly_quota) * 100)) + '%',
                      }"
                    />
                  </div>
                </div>

                <!-- Events -->
                <div class="mt-4">
                  <p class="mb-1 text-[10px] uppercase tracking-widest text-muted">直近イベント</p>
                  <div class="max-h-[160px] space-y-1 overflow-y-auto font-mono text-[11px]">
                    <p v-for="(ev, i) in (expandedDetails.get(row.user_id) as UserDetail).events" :key="i" class="flex gap-2 text-body">
                      <span class="text-muted">{{ new Date(ev.ts).toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
                      <span class="text-primary-active">{{ ev.kind }}</span>
                      <span class="text-ink">{{ ev.detail }}</span>
                    </p>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- ⑦ 設定 -->
      <div v-if="tab === 'settings'" class="max-w-[640px]">
        <p class="mb-4 text-[11px] font-semibold uppercase tracking-widest text-body-strong">システム設定</p>

        <div v-if="settingsLoading" class="py-4 text-[12px] text-muted">読み込み中…</div>
        <div v-else-if="settingsError" class="text-[12px] text-accent">{{ settingsError }}</div>

        <div v-else class="card space-y-0 overflow-hidden p-0">

          <!-- 既存 Boolean 設定 (commission_enabled 等) -->
          <template v-for="(s, idx) in settings.filter(s => s.key !== 'image_tag_presets' && s.key !== 'commission_item_visibility')" :key="s.key">
            <div
              class="flex items-center gap-4 px-4 py-3"
              :class="idx > 0 ? 'border-t border-hairline-soft' : ''"
            >
              <div class="min-w-0 flex-1">
                <p class="font-mono text-[12px] font-semibold text-ink">{{ s.key }}</p>
                <p v-if="s.description" class="mt-0.5 text-[11px] text-muted">{{ s.description }}</p>
              </div>

              <template v-if="s.value === 'true' || s.value === 'false'">
                <span class="shrink-0 font-mono text-[11px]" :class="s.value === 'true' ? 'text-[#1a9950]' : 'text-muted'">
                  {{ s.value === 'true' ? '有効' : '無効' }}
                </span>
                <button
                  class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center overflow-hidden rounded-full transition-colors"
                  :class="[s.value === 'true' ? 'bg-[#2ecc71]' : 'bg-hairline-strong', settingSaving[s.key] ? 'opacity-50' : '']"
                  :disabled="settingSaving[s.key]"
                  @click="toggleSetting(s.key, s.value)"
                >
                  <span
                    class="absolute left-0 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
                    :class="s.value === 'true' ? 'translate-x-[18px]' : 'translate-x-0.5'"
                  />
                </button>
              </template>

              <span v-else class="font-mono text-[11px] text-body">{{ s.value }}</span>
            </div>
          </template>

          <!-- イメージタグ (アコーディオン) -->
          <div class="border-t border-hairline-soft">
            <button
              class="w-full flex items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-canvas-soft"
              @click="toggleSettingPanel('image_tag_presets')"
            >
              <div class="min-w-0 flex-1">
                <p class="font-mono text-[12px] font-semibold text-ink">image_tag_presets</p>
                <p class="mt-0.5 text-[11px] text-muted">アップロード画面で creator が選択できるタグ</p>
              </div>
              <span class="shrink-0 font-mono text-[11px] text-body">
                {{ parsedJsonSetting<string[]>('image_tag_presets', []).length }} 件
              </span>
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                class="shrink-0 text-muted transition-transform"
                :class="expandedSettingKey === 'image_tag_presets' ? 'rotate-90' : ''"
              ><path d="m9 18 6-6-6-6"/></svg>
            </button>

            <div v-if="expandedSettingKey === 'image_tag_presets'" class="border-t border-hairline-soft bg-canvas-soft/60 p-4">
              <div class="flex flex-wrap gap-1.5 mb-3 min-h-[28px]">
                <span
                  v-for="tag in parsedJsonSetting<string[]>('image_tag_presets', [])"
                  :key="tag"
                  class="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold shadow-sm"
                  :class="tagChipClass(tag)"
                >
                  {{ tag }}
                  <button
                    class="ml-0.5 -mr-0.5 flex h-4 w-4 items-center justify-center rounded-full opacity-50 transition-all hover:bg-black/10 hover:opacity-100"
                    title="削除"
                    :disabled="settingSaving['image_tag_presets']"
                    @click="askRemoveImageTag(tag)"
                  >×</button>
                </span>
                <p v-if="parsedJsonSetting<string[]>('image_tag_presets', []).length === 0" class="text-[11px] text-muted">
                  タグがありません
                </p>
              </div>
              <div class="flex gap-2">
                <input
                  v-model="imageTagDraft"
                  type="text"
                  placeholder="新しいタグ (英数字推奨)"
                  class="flex-1 rounded-md border border-hairline-strong bg-white/85 px-3 py-1.5 text-[12px] text-ink outline-none transition-colors focus:border-primary"
                  @keyup.enter="addImageTag"
                />
                <button
                  class="rounded-md px-4 py-1.5 text-[12px] font-medium text-canvas transition-all duration-150 disabled:opacity-50"
                  :class="addedFlash ? 'bg-primary scale-95 shadow-inner' : 'bg-ink hover:bg-primary'"
                  :disabled="!imageTagDraft.trim() || settingSaving['image_tag_presets']"
                  @click="addImageTag"
                >{{ addedFlash ? '追加 ✓' : '追加' }}</button>
              </div>
            </div>
          </div>

          <!-- Commission 項目 (アコーディオン) -->
          <div class="border-t border-hairline-soft">
            <button
              class="w-full flex items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-canvas-soft"
              @click="toggleSettingPanel('commission_item_visibility')"
            >
              <div class="min-w-0 flex-1">
                <p class="font-mono text-[12px] font-semibold text-ink">commission_item_visibility</p>
                <p class="mt-0.5 text-[11px] text-muted">licensee の発注フォームで表示する項目 (OFF は入力欄/検証ともに省略)</p>
              </div>
              <span class="shrink-0 font-mono text-[11px]" :class="commissionHiddenCount > 0 ? 'text-muted' : 'text-[#1a9950]'">
                {{ commissionHiddenCount === 0 ? '全 23 項目 表示' : `${commissionHiddenCount} 項目 非表示` }}
              </span>
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                class="shrink-0 text-muted transition-transform"
                :class="expandedSettingKey === 'commission_item_visibility' ? 'rotate-90' : ''"
              ><path d="m9 18 6-6-6-6"/></svg>
            </button>

            <div v-if="expandedSettingKey === 'commission_item_visibility'" class="border-t border-hairline-soft bg-canvas-soft/60">
              <div
                v-for="(item, idx) in COMMISSION_ITEM_LABELS"
                :key="item.key"
                class="flex items-center gap-4 px-4 py-2.5"
                :class="[
                  stepNum(item.step) % 2 === 0 ? 'bg-surface-strong/30' : 'bg-white/50',
                  isStepHead(idx) && idx > 0 ? 'border-t border-hairline-strong' : '',
                ]"
              >
                <span
                  class="shrink-0 font-mono text-[10px] w-12"
                  :class="isStepHead(idx) ? 'font-bold text-seagreen-deep' : 'text-transparent'"
                >{{ item.step }}</span>
                <div class="min-w-0 flex-1">
                  <p class="text-[12px] text-ink">{{ item.label }}</p>
                  <p class="mt-0.5 font-mono text-[10px] text-muted">{{ item.key }}</p>
                </div>
                <span
                  class="shrink-0 font-mono text-[11px]"
                  :class="(parsedJsonSetting<Record<string, boolean>>('commission_item_visibility', {})[item.key] ?? true) ? 'text-[#1a9950]' : 'text-muted'"
                >
                  {{ (parsedJsonSetting<Record<string, boolean>>('commission_item_visibility', {})[item.key] ?? true) ? '表示' : '非表示' }}
                </span>
                <button
                  class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center overflow-hidden rounded-full transition-colors"
                  :class="[
                    (parsedJsonSetting<Record<string, boolean>>('commission_item_visibility', {})[item.key] ?? true) ? 'bg-[#2ecc71]' : 'bg-hairline-strong',
                    settingSaving['commission_item_visibility'] ? 'opacity-50' : '',
                  ]"
                  :disabled="settingSaving['commission_item_visibility']"
                  @click="toggleCommissionItem(item.key)"
                >
                  <span
                    class="absolute left-0 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
                    :class="(parsedJsonSetting<Record<string, boolean>>('commission_item_visibility', {})[item.key] ?? true) ? 'translate-x-[18px]' : 'translate-x-0.5'"
                  />
                </button>
              </div>
            </div>
          </div>

        </div>

        <!-- イメージタグ削除確認 -->
        <ConfirmModal
          :open="tagPendingDelete !== null"
          title="タグを削除"
          variant="danger"
          confirm-label="削除する"
          cancel-label="やめる"
          @update:open="(v) => { if (!v) tagPendingDelete = null }"
          @confirm="confirmRemoveImageTag"
          @cancel="tagPendingDelete = null"
        >
          <p class="text-[13px] text-body">
            タグ <span class="font-mono font-semibold text-ink">{{ tagPendingDelete }}</span> を削除しますか?
          </p>
          <p class="mt-2 text-[11px] text-muted">削除後、creator のアップロード画面の選択肢からも消えます。既存音源に付与済みのタグ自体は残ります。</p>
        </ConfirmModal>
      </div>

    </div>

    <!-- 改訂2.4: DM モーダル -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="dmOpen"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          @click.self="closeDm"
        >
          <div class="flex h-[600px] w-full max-w-[560px] flex-col rounded-lg bg-canvas shadow-xl">
            <div class="flex shrink-0 items-center justify-between border-b border-hairline-soft px-5 py-3">
              <div>
                <p class="text-[10px] font-semibold uppercase tracking-widest text-muted">DM</p>
                <p class="text-[14px] font-semibold text-ink">{{ dmOpen.name }}</p>
              </div>
              <button class="text-muted hover:text-ink" @click="closeDm">×</button>
            </div>
            <div ref="dmListRef" class="flex-1 overflow-y-auto px-4 py-3">
              <div v-if="dmLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>
              <div v-else-if="dmMessages.length === 0" class="py-12 text-center text-[12px] text-muted">
                メッセージはまだありません。
              </div>
              <div v-else class="space-y-1.5">
                <div
                  v-for="m in dmMessages"
                  :key="m.id"
                  class="flex gap-2"
                  :class="dmIsMine(m) ? 'flex-row-reverse' : 'flex-row'"
                >
                  <div
                    class="grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-[11px] font-bold"
                    :class="dmIsMine(m) ? 'bg-admin text-white' : 'bg-primary text-white'"
                  >{{ dmIsMine(m) ? 'A' : 'C' }}</div>
                  <div class="max-w-[75%]" :class="dmIsMine(m) ? 'text-right' : 'text-left'">
                    <p class="mb-0.5 flex items-center gap-1.5 px-1 text-[10px]" :class="dmIsMine(m) ? 'justify-end' : 'justify-start'">
                      <span class="font-medium" :class="dmIsMine(m) ? 'text-admin-deep' : 'text-seagreen-deep'">{{ dmIsMine(m) ? `${m.sender_name ?? 'Admin'} (Admin)` : (m.sender_name ?? 'Creator') }}</span>
                      <span class="text-muted">{{ dmFormatTime(m.created_at) }}</span>
                    </p>
                    <div
                      class="inline-block rounded-2xl px-3.5 py-2 text-left text-[13px] leading-relaxed whitespace-pre-wrap break-words shadow-sm"
                      :class="dmIsMine(m) ? 'bg-admin/25 text-ink' : 'bg-surface-strong/60 text-ink'"
                    >{{ m.content }}</div>
                  </div>
                </div>
              </div>
            </div>
            <div class="shrink-0 border-t border-hairline-soft p-3">
              <textarea
                v-model="dmDraft"
                rows="2"
                maxlength="4000"
                placeholder="creator にメッセージを送る…"
                class="w-full resize-none rounded-md border border-hairline bg-white px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
                @keydown.ctrl.enter.prevent="sendDm"
              />
              <div class="mt-1.5 flex items-center justify-between">
                <span class="font-mono text-[10px] text-muted">{{ dmDraft.length }} / 4000</span>
                <button
                  class="btn-primary-xs"
                  :disabled="dmSending || !dmDraft.trim()"
                  @click="sendDm"
                >{{ dmSending ? '…' : '送信' }}</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.overflow-y-auto::-webkit-scrollbar { display: none; }
.overflow-y-auto { scrollbar-width: none; }

.filter-active {
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.22), 0 0 1px rgba(0, 0, 0, 0.08);
  letter-spacing: 0.01em;
}
</style>
