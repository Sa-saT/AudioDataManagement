<script setup lang="ts">
import type { OrderBrief } from '~/components/OrderBriefWizard.vue'
import { useAuthStore } from '~/stores/auth'
import { useSystemStore } from '~/stores/system'
import { errorMessageJa } from '~/utils/errorMessageJa'

definePageMeta({ layout: 'default' })
useHead({ title: '発注 — Pathfinder' })

const auth = useAuthStore()
const system = useSystemStore()
const api = useApi()
const router = useRouter()

interface OrderListItem {
  id: string
  title: string
  serial: number
  token_cost: number
  desired_deadline: string
  status: string
  user_name: string
  assigned_creator_name: string | null
  notified_at: string | null
  created_at: string
  updated_at: string
}

interface OrderDetail extends OrderListItem {
  brief: OrderBrief | null
  description: string | null
}

const orders = ref<OrderListItem[]>([])
const loading = ref(false)
const fetchError = ref<string | null>(null)

onMounted(async () => {
  auth.hydrate()
  await system.fetchCommissionStatus()
  if (auth.isActivated && system.commissionEnabled) {
    await fetchOrders()
    // Refresh unread count (visiting this page serves as "seen")
    system.fetchCommissionUnread()
  }
})

async function fetchOrders() {
  loading.value = true
  fetchError.value = null
  try {
    orders.value = await api.get<OrderListItem[]>('/api/v1/orders')
  } catch (err) {
    fetchError.value = errorMessageJa(err)
  } finally {
    loading.value = false
  }
}

// draft 一覧 (改訂2: 先頭に表示)
const drafts = computed(() => orders.value.filter(o => o.status === 'draft'))
const activeOrders = computed(() => orders.value.filter(o => o.status !== 'draft'))

// ─── Create / Resume draft ────────────────────────
const showCreate = ref(false)
const createLoading = ref(false)
const createError = ref<string | null>(null)
// 編集中の draft id (null = 新規作成)
const editingDraftId = ref<string | null>(null)
const initialBrief = ref<Partial<OrderBrief> | undefined>(undefined)
const initialDeadline = ref<string | undefined>(undefined)

function openCreate() {
  editingDraftId.value = null
  initialBrief.value = undefined
  initialDeadline.value = undefined
  createError.value = null
  showCreate.value = true
}

async function openResume(draftId: string) {
  createError.value = null
  try {
    const detail = await api.get<OrderDetail>(`/api/v1/orders/${draftId}`)
    editingDraftId.value = draftId
    initialBrief.value = (detail.brief ?? undefined) as Partial<OrderBrief> | undefined
    initialDeadline.value = detail.desired_deadline ?? undefined
    showCreate.value = true
  } catch (err) {
    createError.value = errorMessageJa(err)
  }
}

async function submitCreate(payload: { brief: OrderBrief; desired_deadline: string }) {
  createLoading.value = true
  createError.value = null
  try {
    // 編集中 draft があれば事前に PATCH で内容を上書き、その後 submit
    let id = editingDraftId.value
    if (id) {
      await api.patch(`/api/v1/orders/${id}/draft`, {
        body: { brief: payload.brief, desired_deadline: payload.desired_deadline },
      })
    } else {
      const created = await api.post<OrderListItem>('/api/v1/orders', {
        body: { brief: payload.brief, desired_deadline: payload.desired_deadline },
      })
      id = created.id
    }
    await api.post(`/api/v1/orders/${id}/submit`, { body: {} })
    showCreate.value = false
    router.push(`/orders/${id}`)
  } catch (err) {
    createError.value = errorMessageJa(err)
  } finally {
    createLoading.value = false
  }
}

async function saveDraft(payload: { brief: OrderBrief; desired_deadline: string }) {
  createLoading.value = true
  createError.value = null
  try {
    if (editingDraftId.value) {
      await api.patch(`/api/v1/orders/${editingDraftId.value}/draft`, {
        body: { brief: payload.brief, desired_deadline: payload.desired_deadline },
      })
    } else {
      const created = await api.post<OrderListItem>('/api/v1/orders', {
        body: { brief: payload.brief, desired_deadline: payload.desired_deadline },
      })
      editingDraftId.value = created.id
    }
    showCreate.value = false
    await fetchOrders()
  } catch (err) {
    createError.value = errorMessageJa(err)
  } finally {
    createLoading.value = false
  }
}

// ─── Helpers ─────────────────────────────────────
const STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  open: 'Open',
  recruiting: '募集中',
  assigned: 'アサイン済',
  reviewing: 'レビュー中',
  done: '完了',
  cancelled: 'キャンセル',
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

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ja-JP', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

// 改訂2.2: 旧 order 互換 — title 末尾の `#N` を除去して件名のみ返す
function stripSerialFromTitle(title: string): string {
  return title.replace(/\s*#\d+\s*$/, '')
}

const isUser = computed(() => auth.role === 'user')
const isAdmin = computed(() => auth.role === 'admin')

// ─── Admin: draft 表示モーダル ───────────────────
const showDraftView = ref(false)
const draftViewing = ref<OrderDetail | null>(null)
const draftViewLoading = ref(false)
const editConfirmOpen = ref(false)   // [編集] 確認ポップアップ
const adminSubmitLoading = ref(false)

async function openAdminView(draftId: string) {
  draftViewLoading.value = true
  showDraftView.value = true
  try {
    draftViewing.value = await api.get<OrderDetail>(`/api/v1/orders/${draftId}`)
  } catch (err) {
    showDraftView.value = false
    alert(errorMessageJa(err))
  } finally {
    draftViewLoading.value = false
  }
}

function closeAdminView() {
  showDraftView.value = false
  draftViewing.value = null
  editConfirmOpen.value = false
}

// 編集確認ポップアップ で yes → wizard 起動
function confirmEdit() {
  editConfirmOpen.value = false
  if (!draftViewing.value) return
  const id = draftViewing.value.id
  showDraftView.value = false
  // 既存の openResume を再利用 (wizard 起動 + 既存 brief プリフィル)
  openResume(id)
}

// admin が代理で [発注] (draft → open)
async function adminSubmit() {
  if (!draftViewing.value) return
  if (!confirm('この発注を提出して open 状態にしますか?')) return
  adminSubmitLoading.value = true
  try {
    await api.post(`/api/v1/orders/${draftViewing.value.id}/submit`, { body: {} })
    closeAdminView()
    await fetchOrders()
    router.push(`/orders/${draftViewing.value?.id ?? ''}`)
  } catch (err) {
    alert(errorMessageJa(err))
  } finally {
    adminSubmitLoading.value = false
  }
}

// 表示用ラベル
const SOUND_TYPE_L: Record<string, string> = { bgm: 'BGM', se: 'SE' }
const PURPOSE_L: Record<string, string> = { game: 'ゲーム', video: '映像', podcast: 'ポッドキャスト', other: 'その他' }
const EMOTION_L: Record<string, string> = {
  excitement: '高揚感/興奮', tension: '緊張感', fear: '恐怖/不安',
  relief: '安らぎ/安心', loneliness: '孤独感', grandeur: '壮大さ/圧倒感',
  speed: '疾走感', sadness: '哀愁/切なさ', mystery: '神秘/異世界感',
  achievement: '達成感/充足感', heaviness: '重厚感/威圧感',
  comfort: '心地よさ/まったり感', euphoria: '爽快感',
  dread: 'じわじわとした恐怖', wonder: '驚き/発見の喜び',
}
const BGM_SCENE_L: Record<string, string> = {
  battle: 'バトル/戦闘', boss: 'ボス戦', explore: '探索/フィールド',
  menu: 'メニュー/UI', title: 'タイトル', event: 'イベント/ムービー',
  ending: 'エンディング', ambient: 'アンビエント', other: 'その他',
}
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- Header -->
    <div class="flex shrink-0 items-end justify-between gap-4 pb-3 pt-5">
      <div>
        <h1 class="text-[20px] font-normal tracking-[-0.0125em] text-ink">発注 (Commission)</h1>
        <p class="mt-0.5 text-[12px] text-muted">オリジナル音源の制作依頼</p>
      </div>
      <button
        v-if="auth.isActivated && system.commissionEnabled && isUser"
        class="flex items-center gap-1.5 rounded-md bg-ink px-3 py-1.5 text-[12px] font-medium text-canvas transition-colors hover:bg-primary"
        @click="openCreate"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        新規発注
      </button>
    </div>

    <div class="h-px shrink-0 bg-hairline-soft" />

    <div class="flex-1 overflow-y-auto py-3">

      <!-- Not activated -->
      <div v-if="!auth.isActivated" class="card p-6 text-center text-[13px] text-body">
        アクティベートするとご利用いただけます。
      </div>

      <!-- Commission disabled -->
      <div v-else-if="!system.commissionEnabled" class="card p-6 text-center text-[13px] text-muted">
        現在、発注機能は準備中です。
      </div>

      <!-- Loading -->
      <div v-else-if="loading" class="space-y-2">
        <div v-for="i in 4" :key="i" class="card h-14 animate-pulse bg-hairline-soft/40" />
      </div>

      <!-- Error -->
      <div v-else-if="fetchError" class="card mx-auto mt-6 max-w-[520px] p-6 text-center text-[13px]">
        <p class="font-medium text-accent">読み込みに失敗しました</p>
        <p class="mt-1 text-muted">{{ fetchError }}</p>
        <button
          class="mt-4 rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary"
          @click="fetchOrders"
        >再試行</button>
      </div>

      <!-- Empty -->
      <div v-else-if="orders.length === 0" class="py-16 text-center text-[13px] text-muted">
        発注はまだありません。
        <template v-if="isUser">
          <br/><button class="mt-2 text-primary-active hover:underline" @click="openCreate">新規発注を作成する</button>
        </template>
      </div>

      <!-- List -->
      <div v-else class="space-y-4">

        <!-- Drafts セクション (改訂2: 一時保存中) -->
        <section v-if="drafts.length > 0">
          <p class="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-widest text-muted">
            一時保存中 ({{ drafts.length }})
          </p>
          <div class="space-y-2">
            <!-- 行全体クリックで開ける (admin → 表示モーダル / user → wizard 再開) -->
            <div
              v-for="draft in drafts"
              :key="draft.id"
              class="card flex cursor-pointer items-center gap-4 border-dashed border-primary/30 bg-primary/5 px-4 py-3 transition-all hover:-translate-y-px hover:border-primary hover:shadow-md"
              role="button"
              tabindex="0"
              @click="isAdmin ? openAdminView(draft.id) : openResume(draft.id)"
              @keydown.enter.prevent="isAdmin ? openAdminView(draft.id) : openResume(draft.id)"
            >
              <span class="shrink-0 rounded-full bg-hairline-soft px-2 py-0.5 font-mono text-[10px] font-semibold text-body">Draft</span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 truncate text-[14px] font-medium text-ink">
                  <span class="shrink-0 rounded bg-ink/5 px-1.5 py-0.5 font-mono text-[10px]">#{{ draft.serial }}</span>
                  <span class="truncate">{{ stripSerialFromTitle(draft.title) }}</span>
                </div>
                <div class="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
                  <span class="font-mono">{{ draft.token_cost }} tk</span>
                  <span class="h-1 w-1 rounded-full bg-muted" />
                  <span>締切 {{ formatDate(draft.desired_deadline) }}</span>
                  <span class="h-1 w-1 rounded-full bg-muted" />
                  <span>{{ formatDate(draft.updated_at) }} 更新</span>
                </div>
              </div>
              <!-- Admin: [表示] [キャンセル(戻る)] -->
              <template v-if="isAdmin">
                <button
                  class="shrink-0 rounded-md bg-ink px-3 py-1 text-[11px] font-medium text-canvas hover:bg-primary"
                  @click.stop="openAdminView(draft.id)"
                >表示</button>
                <button
                  class="shrink-0 rounded-md border border-hairline-strong bg-white px-3 py-1 text-[11px] font-medium text-muted hover:border-ink hover:text-ink"
                  @click.stop
                  title="戻る (一覧に留まる)"
                >キャンセル(戻る)</button>
              </template>
              <!-- User / その他: [続きから入力] -->
              <button
                v-else
                class="shrink-0 rounded-md bg-ink px-3 py-1 text-[11px] font-medium text-canvas hover:bg-primary"
                @click.stop="openResume(draft.id)"
              >続きから入力</button>
            </div>
          </div>
        </section>

        <!-- Active orders -->
        <section v-if="activeOrders.length > 0">
          <div class="space-y-2">
            <NuxtLink
              v-for="order in activeOrders"
              :key="order.id"
              :to="`/orders/${order.id}`"
              class="card flex items-center gap-4 px-4 py-3 transition-colors hover:border-primary/40"
            >
              <span
                class="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
                :class="STATUS_CLASS[order.status] ?? 'bg-hairline-soft text-body'"
              >{{ STATUS_LABEL[order.status] ?? order.status }}</span>

              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="shrink-0 rounded bg-ink/5 px-1.5 py-0.5 font-mono text-[10px] text-ink">#{{ order.serial }}</span>
                  <span class="truncate text-[14px] font-medium text-ink">{{ stripSerialFromTitle(order.title) }}</span>
                  <span
                    v-if="order.status === 'done' && order.notified_at"
                    class="h-1.5 w-1.5 shrink-0 rounded-full bg-[#2ecc71]"
                    title="完了"
                  />
                </div>
                <div class="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
                  <span>{{ order.user_name }}</span>
                  <template v-if="order.assigned_creator_name">
                    <span class="h-1 w-1 rounded-full bg-muted" />
                    <span>{{ order.assigned_creator_name }}</span>
                  </template>
                  <span class="h-1 w-1 rounded-full bg-muted" />
                  <span class="font-mono">{{ order.token_cost }} tk</span>
                  <span class="h-1 w-1 rounded-full bg-muted" />
                  <span>締切 {{ formatDate(order.desired_deadline) }}</span>
                </div>
              </div>

              <svg class="shrink-0 text-muted" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </NuxtLink>
          </div>
        </section>
      </div>
    </div>

    <!-- Create modal (wizard) -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showCreate"
          class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-12 pb-6 backdrop-blur-sm overflow-y-auto"
          @click.self="showCreate = false"
        >
          <div class="card mx-4 w-full max-w-[540px] p-6">
            <div class="mb-5 flex items-center justify-between">
              <h2 class="text-[15px] font-semibold text-ink">
                {{ editingDraftId ? '続きから入力' : '新規発注' }}
              </h2>
              <button class="text-muted hover:text-ink" @click="showCreate = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <OrderBriefWizard
              :initial-brief="initialBrief"
              :initial-deadline="initialDeadline"
              @submit="submitCreate"
              @save-draft="saveDraft"
              @cancel="showCreate = false"
            />

            <p v-if="createError" class="mt-3 text-[12px] text-accent">{{ createError }}</p>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Admin: draft 表示モーダル ([表示] で開く) -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showDraftView"
          class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-12 pb-6 backdrop-blur-sm overflow-y-auto"
          @click.self="closeAdminView"
        >
          <div class="card mx-4 w-full max-w-[600px] p-6">
            <div class="mb-4 flex items-center justify-between">
              <h2 class="text-[15px] font-semibold text-ink">発注内容の確認</h2>
              <button class="text-muted hover:text-ink" @click="closeAdminView">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <div v-if="draftViewLoading" class="py-8 text-center text-[12px] text-muted">読み込み中…</div>

            <template v-else-if="draftViewing">
              <!-- Header info -->
              <div class="mb-4 rounded-lg border border-hairline bg-canvas-soft/50 px-4 py-3">
                <p class="font-mono text-[11px] text-muted">{{ draftViewing.title }}</p>
                <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
                  <span class="text-body">発注者: <span class="font-semibold text-ink">{{ draftViewing.user_name }}</span></span>
                  <span class="font-mono text-body">{{ draftViewing.token_cost }} tk</span>
                  <span class="text-body">締切: <span class="font-mono">{{ formatDate(draftViewing.desired_deadline) }}</span></span>
                </div>
              </div>

              <!-- Brief 一覧 (構造化リスト) -->
              <div class="mb-5 space-y-2 text-[12px]">
                <p class="text-[10px] font-semibold uppercase tracking-widest text-muted">ブリーフ内容</p>
                <template v-if="draftViewing.brief">
                  <!-- Step 1: 基本情報 -->
                  <div class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5">
                    <span class="text-muted">サウンドタイプ</span>
                    <span class="text-ink">{{ SOUND_TYPE_L[draftViewing.brief.sound_type ?? ''] ?? '-' }}</span>

                    <span class="text-muted">用途</span>
                    <span class="text-ink">
                      {{ PURPOSE_L[draftViewing.brief.purpose ?? ''] ?? '-' }}
                      <span v-if="draftViewing.brief.purpose_note" class="text-body">({{ draftViewing.brief.purpose_note }})</span>
                    </span>

                    <span class="text-muted">長さ</span>
                    <span class="font-mono text-ink">{{ draftViewing.brief.length_sec ?? '-' }}秒</span>

                    <!-- BGM scenes -->
                    <template v-if="draftViewing.brief.bgm_scenes && draftViewing.brief.bgm_scenes.length > 0">
                      <span class="text-muted">シーン</span>
                      <span class="text-ink">{{ draftViewing.brief.bgm_scenes.map((s: string) => BGM_SCENE_L[s] ?? s).join(', ') }}</span>
                    </template>
                    <template v-if="draftViewing.brief.bgm_loop !== undefined && (draftViewing.brief.sound_type === 'bgm')">
                      <span class="text-muted">ループ</span>
                      <span class="text-ink">{{ draftViewing.brief.bgm_loop ? 'ON' : 'OFF' }}</span>
                    </template>
                    <template v-if="draftViewing.brief.bgm_note">
                      <span class="text-muted">シーン補足</span>
                      <span class="text-ink whitespace-pre-line">{{ draftViewing.brief.bgm_note }}</span>
                    </template>

                    <!-- SE -->
                    <template v-if="draftViewing.brief.se_trigger">
                      <span class="text-muted">SE トリガー</span>
                      <span class="text-ink">{{ draftViewing.brief.se_trigger }}</span>
                    </template>
                    <template v-if="draftViewing.brief.se_functions && draftViewing.brief.se_functions.length > 0">
                      <span class="text-muted">SE 役割</span>
                      <span class="text-ink">{{ draftViewing.brief.se_functions.join(', ') }}</span>
                    </template>

                    <!-- Step 3: 感情 -->
                    <template v-if="draftViewing.brief.emotions_target && draftViewing.brief.emotions_target.length > 0">
                      <span class="text-muted">狙う感情</span>
                      <span class="text-ink">
                        <span
                          v-for="e in draftViewing.brief.emotions_target"
                          :key="e"
                          class="mr-1 inline-block rounded-full bg-primary/15 px-2 py-0.5 text-[11px] text-primary-active"
                        >{{ EMOTION_L[e] ?? e }}</span>
                      </span>
                    </template>
                    <template v-if="draftViewing.brief.emotions_avoid && draftViewing.brief.emotions_avoid.length > 0">
                      <span class="text-muted">避けたい感情</span>
                      <span class="text-ink">
                        <span
                          v-for="e in draftViewing.brief.emotions_avoid"
                          :key="e"
                          class="mr-1 inline-block rounded-full bg-hairline-soft px-2 py-0.5 text-[11px] text-muted line-through"
                        >{{ EMOTION_L[e] ?? e }}</span>
                      </span>
                    </template>
                    <template v-if="draftViewing.brief.memory_impression">
                      <span class="text-muted">イメージ</span>
                      <span class="italic text-body">「{{ draftViewing.brief.memory_impression }}」</span>
                    </template>

                    <!-- Step 5: reference -->
                    <template v-if="draftViewing.brief.reference_urls">
                      <span class="text-muted">参考 URL</span>
                      <span class="whitespace-pre-line break-all font-mono text-[11px] text-body">{{ draftViewing.brief.reference_urls }}</span>
                    </template>
                    <template v-if="draftViewing.brief.reference_elements && draftViewing.brief.reference_elements.length > 0">
                      <span class="text-muted">参考要素</span>
                      <span class="text-ink">{{ draftViewing.brief.reference_elements.join(', ') }}</span>
                    </template>
                    <template v-if="draftViewing.brief.reference_avoid">
                      <span class="text-muted">避ける要素</span>
                      <span class="text-ink whitespace-pre-line">{{ draftViewing.brief.reference_avoid }}</span>
                    </template>

                    <!-- Step 6 -->
                    <template v-if="draftViewing.brief.delivery_format">
                      <span class="text-muted">納品形式</span>
                      <span class="font-mono text-ink">{{ draftViewing.brief.delivery_format }}</span>
                    </template>
                    <template v-if="draftViewing.brief.note">
                      <span class="text-muted">備考</span>
                      <span class="text-ink whitespace-pre-line">{{ draftViewing.brief.note }}</span>
                    </template>
                  </div>
                </template>
                <p v-else class="text-muted">ブリーフが未入力です。</p>
              </div>

              <!-- Action buttons -->
              <div class="flex items-center justify-end gap-2 border-t border-hairline-soft pt-4">
                <button
                  class="rounded-md border border-hairline bg-white/60 px-4 py-1.5 text-[12px] text-body transition-colors hover:border-ink hover:text-ink"
                  @click="closeAdminView"
                >閉じる</button>
                <!-- [編集] 注意色 -->
                <button
                  class="rounded-md border border-accent bg-accent/10 px-4 py-1.5 text-[12px] font-medium text-accent transition-colors hover:bg-accent hover:text-white"
                  @click="editConfirmOpen = true"
                  title="user の brief を代理編集 (ミス防止のため確認あり)"
                >編集</button>
                <button
                  class="flex items-center gap-2 rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas transition-colors hover:bg-primary hover:text-white disabled:opacity-50"
                  :disabled="adminSubmitLoading"
                  @click="adminSubmit"
                >
                  <svg
                    v-if="adminSubmitLoading"
                    class="animate-spin" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                  ><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  発注
                </button>
              </div>
            </template>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- [編集] 確認ポップアップ (ミス防止) -->
    <ConfirmModal
      v-model:open="editConfirmOpen"
      title="本当に編集しますか?"
      :message="'admin が代理編集します。ブリーフ内容が変更されると、発注者と認識のズレが起きる可能性があります。'"
      confirm-label="編集する"
      cancel-label="戻る"
      variant="danger"
      @confirm="confirmEdit"
    />
  </div>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 200ms; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.overflow-y-auto::-webkit-scrollbar { display: none; }
.overflow-y-auto { scrollbar-width: none; }
</style>
