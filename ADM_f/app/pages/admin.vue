<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })
useHead({ title: 'Admin — Pathfinder' })

const auth = useAuthStore()
const api = useApi()
const router = useRouter()

onMounted(() => {
  auth.hydrate()
  if (auth.role !== 'admin') router.replace('/dashboard')
})

// ─── Tab ─────────────────────────────────────────────────────────────────────
type Tab = 'users' | 'payouts' | 'tokens' | 'licenses'
const tab = ref<Tab>('users')

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
type RoleFilter = 'creator' | 'user'
const roleFilter = ref<RoleFilter>('creator')
const groupFilter = ref<string>('all')

const creatorList = computed(() => users.value.filter(u => u.role === 'creator' || u.role === 'admin'))
const userList = computed(() => users.value.filter(u => u.role === 'user'))

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
const userOnlyList = computed(() => users.value.filter(u => u.role === 'user'))

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
const licRole = ref<'user' | 'creator' | 'admin'>('user')
const licQuota = ref(18000)
const licGroup = ref('')
const licExpires = ref('')
const licLoading = ref(false)
const licError = ref<string | null>(null)

function resetLic() {
  licUsername.value = ''
  licRole.value = 'user'
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
      ...(licRole.value === 'user' ? { monthly_quota_tokens: licQuota.value } : {}),
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

// ─── Load on tab change ───────────────────────────────────────────────────────
watch(tab, (t) => {
  if ((t === 'users' || t === 'tokens') && users.value.length === 0) fetchUsers()
  if (t === 'payouts') fetchPayouts()
}, { immediate: true })
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- Header -->
    <div class="flex shrink-0 items-center gap-3 py-5">
      <h1 class="font-mono text-[13px] font-bold uppercase tracking-widest text-ink">Admin</h1>
    </div>

    <!-- Tabs -->
    <div class="flex shrink-0 gap-4 border-b border-hairline-soft pb-0">
      <button
        v-for="t in ([['users','ユーザ管理'],['payouts','Payout'],['tokens','Token付与'],['licenses','lic発行']] as [Tab, string][])"
        :key="t[0]"
        class="relative pb-2 text-[12px] font-semibold text-ink transition-all"
        :class="tab === t[0] ? 'filter-active' : 'opacity-40 hover:opacity-70'"
        @click="tab = t[0]"
      >
        {{ t[1] }}
        <span v-if="tab === t[0]" class="absolute inset-x-0 -bottom-px h-0.5 rounded-sm bg-primary" />
      </button>
    </div>

    <div class="flex-1 overflow-y-auto py-4">

      <!-- ① ユーザ管理 -->
      <div v-if="tab === 'users'">

        <!-- role フィルタ + 更新 -->
        <div class="mb-3 flex items-center gap-4">
          <div class="flex gap-3">
            <button
              v-for="r in (['creator','user'] as RoleFilter[])"
              :key="r"
              class="text-[12px] font-semibold text-ink transition-all"
              :class="roleFilter === r ? 'filter-active' : 'opacity-40 hover:opacity-70'"
              @click="roleFilter = r"
            >{{ r === 'creator' ? 'Creator' : 'User' }}</button>
          </div>
          <button class="ml-auto text-[11px] text-muted hover:text-ink" @click="fetchUsers">↻ 更新</button>
        </div>

        <!-- User: group filter -->
        <div v-if="roleFilter === 'user' && availableGroups.length > 0" class="mb-3 flex flex-wrap gap-2">
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
                  class="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase"
                  :style="u.role === 'admin'
                    ? 'background:#ff634722;color:#c0392b;border:1px solid #ff634755'
                    : 'background:#20b2aa22;color:#0e7a74;border:1px solid #20b2aa55'"
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
                    {{ creatorStats[u.id].total_uploads }}UP
                    <span class="mx-1 text-muted">·</span>
                    {{ creatorStats[u.id].total_sold }}DL
                  </p>
                  <p class="font-mono text-[10px]" :class="creatorStats[u.id].payout_pending_yen > 0 ? 'text-accent' : 'text-muted'">
                    {{ creatorStats[u.id].payout_pending_yen > 0
                      ? `未払 ¥${creatorStats[u.id].payout_pending_yen.toLocaleString()}`
                      : `累計 ¥${creatorStats[u.id].payout_total_yen.toLocaleString()}` }}
                  </p>
                </div>

                <!-- rank selector -->
                <div class="shrink-0 flex items-center gap-1.5" @click.stop>
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
                      <p class="font-mono text-[18px] font-semibold text-ink">{{ creatorStats[u.id].total_uploads }}</p>
                      <p class="mt-0.5 font-mono text-[10px] text-muted uppercase tracking-wider">Total UP</p>
                    </div>
                    <div class="rounded-lg border border-hairline-soft bg-surface-strong/40 px-3 py-2.5 text-center">
                      <p class="font-mono text-[18px] font-semibold text-ink">{{ creatorStats[u.id].total_sold }}</p>
                      <p class="mt-0.5 font-mono text-[10px] text-muted uppercase tracking-wider">Total DL</p>
                    </div>
                    <div class="rounded-lg border border-hairline-soft bg-surface-strong/40 px-3 py-2.5 text-center">
                      <p class="font-mono text-[18px] font-semibold text-ink">{{ creatorStats[u.id].total_unsold }}</p>
                      <p class="mt-0.5 font-mono text-[10px] text-muted uppercase tracking-wider">残</p>
                    </div>
                  </div>

                  <!-- 支払サマリ -->
                  <div class="flex items-center gap-4 rounded-lg border border-hairline-soft bg-surface-strong/40 px-4 py-2.5">
                    <div>
                      <p class="font-mono text-[10px] uppercase tracking-wider text-muted">支払累計</p>
                      <p class="font-mono text-[14px] font-semibold text-ink">¥{{ creatorStats[u.id].payout_total_yen.toLocaleString() }}</p>
                    </div>
                    <div class="h-6 w-px bg-hairline-soft" />
                    <div>
                      <p class="font-mono text-[10px] uppercase tracking-wider text-muted">未払い</p>
                      <p class="font-mono text-[14px] font-semibold" :class="creatorStats[u.id].payout_pending_yen > 0 ? 'text-accent' : 'text-muted'">
                        ¥{{ creatorStats[u.id].payout_pending_yen.toLocaleString() }}
                      </p>
                    </div>
                    <button
                      v-if="creatorStats[u.id].payout_pending_yen > 0"
                      class="ml-auto rounded border border-primary/40 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary-active hover:bg-primary/20"
                      @click="tab = 'payouts'"
                    >Payout 確認 →</button>
                  </div>

                  <!-- 月次テーブル -->
                  <div v-if="creatorStats[u.id].monthly.length > 0">
                    <p class="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted">月次 (直近 {{ creatorStats[u.id].monthly.length }} ヶ月)</p>
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
                          v-for="m in [...creatorStats[u.id].monthly].reverse()"
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
            <span class="shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase"
              style="background:#26251e18;color:#26251e;border-color:#26251e30">user</span>

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
          <div class="flex gap-3">
            <button
              v-for="f in (['pending','all'] as const)"
              :key="f"
              class="text-[12px] font-semibold text-ink transition-all"
              :class="payoutFilter === f ? 'filter-active' : 'opacity-40 hover:opacity-70'"
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
              class="card w-full cursor-pointer px-4 py-3 text-left transition-colors hover:border-primary"
              :class="expandedCreators.has(g.creator_id) ? 'border-primary' : ''"
              @click="toggleCreator(g.creator_id)"
            >
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
                class="flex items-center gap-3 rounded-lg border border-hairline-soft bg-white/50 px-4 py-2.5"
              >
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
              対象ユーザ <span class="text-accent">*</span>
              <span class="ml-1 font-normal normal-case tracking-normal text-muted">(role=user のみ)</span>
            </label>
            <div v-if="usersLoading" class="py-2 text-[12px] text-muted">読み込み中…</div>
            <div v-else-if="userOnlyList.length === 0" class="rounded-md border border-hairline-soft bg-surface-strong/40 px-3 py-2 text-[12px] text-muted">
              role=user のアカウントがまだありません。
            </div>
            <select
              v-else
              v-model="grantUserId"
              class="w-full rounded-md border border-hairline-strong bg-white/85 px-3 py-2 text-[12px] text-ink outline-none transition-colors focus:border-primary"
            >
              <option value="" disabled>ユーザを選択…</option>
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
              class="flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-[12px] font-medium text-canvas transition-colors hover:bg-primary disabled:opacity-50"
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
                v-for="r in ['user','creator','admin'] as const" :key="r" type="button"
                class="rounded-full border px-3 py-1 text-[11px] font-medium transition-colors"
                :class="licRole === r ? 'border-primary bg-primary/10 text-primary-active' : 'border-hairline text-muted hover:text-ink'"
                @click="licRole = r"
              >{{ r }}</button>
            </div>
          </div>
          <!-- token: user のみ表示 -->
          <div v-if="licRole === 'user'">
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
              class="flex items-center gap-1.5 rounded-md bg-ink px-4 py-2 text-[12px] font-medium text-canvas transition-colors hover:bg-primary disabled:opacity-50"
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

    </div>
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
