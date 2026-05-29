<script setup lang="ts">
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
  token_cost: number
  status: string
  user_name: string
  assigned_creator_name: string | null
  notified_at: string | null
  created_at: string
  updated_at: string
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

// ─── Create order (wizard) ────────────────────────
const showCreate = ref(false)
const createLoading = ref(false)
const createError = ref<string | null>(null)

function openCreate() {
  createError.value = null
  showCreate.value = true
}

async function submitCreate(payload: { title: string; token_cost: number; brief: Record<string, unknown> }) {
  if (payload.token_cost <= 0) { createError.value = 'token数は1以上にしてください。'; return }
  createLoading.value = true
  createError.value = null
  try {
    const res = await api.post<OrderListItem>('/api/v1/orders', {
      body: {
        title: payload.title,
        brief: payload.brief,
        token_cost: payload.token_cost,
      },
    })
    showCreate.value = false
    router.push(`/orders/${res.id}`)
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

const isUser = computed(() => auth.role === 'user')
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
      <div v-else class="space-y-2">
        <NuxtLink
          v-for="order in orders"
          :key="order.id"
          :to="`/orders/${order.id}`"
          class="card flex items-center gap-4 px-4 py-3 transition-colors hover:border-primary/40"
        >
          <!-- Status badge -->
          <span
            class="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
            :class="STATUS_CLASS[order.status] ?? 'bg-hairline-soft text-body'"
          >{{ STATUS_LABEL[order.status] ?? order.status }}</span>

          <!-- Title + meta -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate text-[14px] font-medium text-ink">{{ order.title }}</span>
              <!-- Done notification dot -->
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
              <span>{{ formatDate(order.updated_at) }}</span>
            </div>
          </div>

          <!-- Arrow -->
          <svg class="shrink-0 text-muted" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </NuxtLink>
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
              <h2 class="text-[15px] font-semibold text-ink">新規発注</h2>
              <button class="text-muted hover:text-ink" @click="showCreate = false">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <OrderBriefWizard
              @submit="submitCreate"
              @cancel="showCreate = false"
            />

            <p v-if="createError" class="mt-3 text-[12px] text-accent">{{ createError }}</p>
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
