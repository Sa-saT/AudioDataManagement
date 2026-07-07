<script setup lang="ts">
import { useAudiosStore } from '~/stores/audios'
import { useAuthStore } from '~/stores/auth'

definePageMeta({ layout: 'default' })
useHead({ title: 'Dashboard — Pathfinder' })

const audios = useAudiosStore()
const auth = useAuthStore()

onMounted(async () => {
  auth.hydrate()
  await Promise.all([audios.fetch(), audios.fetchTags()])
})

// per-page options は store で動的計算 (total に応じた 5 の倍数)

const listCount = computed(() => audios.sorted.length)
const countDigits = computed(() =>
  Math.max(2, audios.total.toString().length),
)

// Token quota: monthlyQuota from license, used 累計は DL レスポンスで auth に反映
const monthlyQuota = computed(() => auth.monthlyQuotaTokens)
const tokensUsed = computed(() => auth.tokensUsed)
const tokenPct = computed(() => {
  if (monthlyQuota.value === 0) return 0
  return Math.round((tokensUsed.value / monthlyQuota.value) * 100)
})
const tokenLow = computed(() => tokenPct.value >= 90)

// ─── Search + tag panel ───────────────────────────
const searchInput = ref(audios.searchQuery)
watch(searchInput, (v) => audios.setSearch(v))

const searchFocused = ref(false)
const searchBoxRef = ref<HTMLDivElement | null>(null)

const allTags = computed(() =>
  audios.tagCounts.map(({ name, count }) => [name, count] as [string, number]),
)

const filteredTags = computed(() => {
  const q = searchInput.value.trim().toLowerCase()
  if (!q) return allTags.value
  return allTags.value.filter(([tag]) => tag.toLowerCase().includes(q))
})

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// tag は creator が自由入力するため、v-html に渡す前に必ずエスケープする (stored XSS 防止)
function highlight(tag: string): string {
  const q = searchInput.value.trim()
  if (!q) return escapeHtml(tag)
  const idx = tag.toLowerCase().indexOf(q.toLowerCase())
  if (idx < 0) return escapeHtml(tag)
  return (
    escapeHtml(tag.slice(0, idx)) +
    `<mark class="bg-transparent text-primary-active font-semibold">` +
    escapeHtml(tag.slice(idx, idx + q.length)) +
    `</mark>` +
    escapeHtml(tag.slice(idx + q.length))
  )
}

function pickTag(tag: string) {
  audios.setMine(false)
  audios.toggleTag(tag)
  searchFocused.value = false
}

function toggleMine() {
  audios.setMine(!audios.mineOnly)
  searchInput.value = ''
  searchFocused.value = false
}

function onDocClick(e: MouseEvent) {
  if (!searchBoxRef.value) return
  if (!searchBoxRef.value.contains(e.target as Node)) {
    searchFocused.value = false
  }
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') searchFocused.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
})

// ─── List scroll sync with ◀▶ ────────────────────
const cardListRef = ref<HTMLDivElement | null>(null)
function scrollByItems(delta: number) {
  const container = cardListRef.value
  if (!container) return
  const firstCard = container.querySelector('.card') as HTMLElement | null
  if (!firstCard) return
  const gap = 8
  const itemHeight = firstCard.offsetHeight + gap
  container.scrollBy({ top: delta * itemHeight, behavior: 'smooth' })
}
function onPrev() { audios.stepPerPage(-1); scrollByItems(-5) }
function onNext() { audios.stepPerPage(1); scrollByItems(5) }
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- ① Status row: activation warning / token info のみ (件数は controls 行へ統合) -->
    <div class="flex shrink-0 flex-wrap items-center justify-between gap-4 pb-3 pt-5 min-h-[28px]">
      <div v-if="!auth.isActivated" class="w-full rounded-lg border border-seagreen/50 bg-seagreen/10 px-4 py-2.5">
        <p class="text-[15px] font-bold text-seagreen-deep">アクティベートされていません。ダウンロードは不可。</p>
      </div>
      <span v-else />

      <div v-if="auth.isActivated && auth.role !== 'creator'" class="flex items-center gap-4">
        <div class="flex min-w-[200px] flex-col gap-1">
          <div class="flex justify-between font-mono text-[11px] font-semibold text-ink">
            <span>TOKENS</span>
            <span :class="tokenLow ? 'text-accent font-bold' : ''">
              {{ tokensUsed.toLocaleString('ja-JP') }} / {{ monthlyQuota.toLocaleString('ja-JP') }}
            </span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full border border-hairline-strong bg-surface-strong">
            <div
              class="h-full rounded-full transition-all"
              :class="tokenLow ? 'bg-accent' : 'bg-primary'"
              :style="`width: ${tokenPct}%`"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- ② Controls -->
    <div class="relative flex shrink-0 items-center gap-3 border-b border-hairline-soft pb-3">
      <!-- Search with expandable tag panel -->
      <div ref="searchBoxRef" class="relative flex-1">
        <div class="relative">
          <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            v-model="searchInput"
            type="search"
            placeholder="タイトル / タグで検索…"
            class="w-full rounded-lg border bg-white/75 py-1.5 pl-8 pr-8 text-[12px] text-ink placeholder:text-muted backdrop-blur-sm outline-none transition-all"
            :class="searchFocused ? 'border-primary bg-white/90 shadow-sm' : 'border-hairline-strong'"
            @focus="searchFocused = true"
          />
          <button
            v-if="searchInput"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
            @click.stop="searchInput = ''"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <!-- Expand panel -->
        <Transition name="panel">
          <div
            v-if="searchFocused"
            class="absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-[60vh] overflow-y-auto rounded-xl border border-hairline-strong bg-white/95 p-4 shadow-xl backdrop-blur-md"
          >
            <div class="mb-3 flex items-center justify-between text-[10px] font-semibold uppercase tracking-widest text-body">
              <span>タグから絞り込み</span>
              <span class="font-mono">{{ filteredTags.length }} / {{ allTags.length }}</span>
            </div>

            <!-- 自身の音源 (creator/admin のみ) -->
            <div v-if="auth.role === 'creator' || auth.role === 'admin'" class="mb-3">
              <button
                class="flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium transition-colors"
                :class="audios.mineOnly
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-hairline bg-white/70 text-body hover:border-primary hover:text-ink'"
                @click="toggleMine"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                </svg>
                自身の音源
              </button>
            </div>

            <div v-if="filteredTags.length > 0" class="flex flex-wrap gap-1.5">
              <button
                v-for="([tag, count], idx) in filteredTags"
                :key="tag"
                class="tag-chip-anim group flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] transition-all hover:-translate-y-px"
                :class="audios.activeTags.includes(tag)
                  ? 'border-primary bg-primary/10 text-primary-active'
                  : 'border-hairline-strong bg-surface-strong/70 text-body-strong hover:border-primary hover:bg-white'"
                :style="`animation-delay: ${Math.min(idx * 22, 300)}ms`"
                @click="pickTag(tag)"
              >
                <span v-html="highlight(tag)" />
                <span
                  class="rounded-full px-1.5 py-0 text-[10px]"
                  :class="audios.activeTags.includes(tag)
                    ? 'bg-primary/15 text-primary-active'
                    : 'bg-hairline-strong/80 text-body group-hover:bg-primary/15 group-hover:text-primary-active'"
                >{{ count }}</span>
              </button>
            </div>
            <div v-else class="py-4 text-center text-[12px] text-muted">
              「{{ searchInput }}」に一致するタグはありません
            </div>

          </div>
        </Transition>
      </div>

      <!-- Active tag chips -->
      <TransitionGroup
        v-if="audios.activeTags.length > 0"
        tag="div"
        name="chip"
        class="flex shrink-0 items-center gap-1"
      >
        <button
          v-for="tag in audios.activeTags"
          :key="tag"
          class="flex items-center gap-1 rounded-full border border-primary bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-primary-active transition-colors hover:bg-primary/20"
          @click="audios.toggleTag(tag)"
        >
          {{ tag }}
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
        <button
          class="rounded-full border border-hairline-strong px-2 py-0.5 font-mono text-[10px] text-muted transition-colors hover:border-accent hover:text-accent"
          @click="audios.clearTags()"
        >全解除</button>
      </TransitionGroup>

      <!-- Per-page + 全件: ◀ count ▶ / 全 N 件 (プレーンテキスト、黒統一) -->
      <div class="flex shrink-0 items-center gap-1 font-mono text-[12px] font-semibold text-ink">
        <template v-if="audios.showPerPageStepper">
          <button
            class="px-1 text-muted transition-colors hover:text-ink disabled:opacity-30"
            :disabled="audios.perPage === audios.perPageOptions[0]"
            @click="onPrev"
          >◀</button>
          <NumberRoller
            :value="audios.perPage"
            :digits="Math.max(2, audios.perPage.toString().length)"
            :font-size="13"
            font-weight="700"
            hide-leading-zeros
          />
          <button
            class="px-1 text-muted transition-colors hover:text-ink disabled:opacity-30"
            :disabled="audios.perPage === audios.perPageOptions[audios.perPageOptions.length - 1]"
            @click="onNext"
          >▶</button>
        </template>
        <template v-else>
          <span>{{ audios.total }}</span>
        </template>

        <span class="text-muted">/</span>
        <span>全</span>
        <NumberRoller
          :value="listCount"
          :digits="countDigits"
          :font-size="12"
          font-weight="700"
          hide-leading-zeros
        />
        <span>件</span>
      </div>
    </div>

    <!-- ③ Card list -->
    <div
      ref="cardListRef"
      class="flex-1 overflow-y-auto py-3"
      style="mask-image: linear-gradient(to bottom, transparent 0px, black 28px, black calc(100% - 28px), transparent 100%); -webkit-mask-image: linear-gradient(to bottom, transparent 0px, black 28px, black calc(100% - 28px), transparent 100%);"
    >
      <!-- Loading skeletons -->
      <div v-if="audios.loading && audios.items.length === 0" class="space-y-2">
        <div
          v-for="i in 4"
          :key="i"
          class="card flex items-center gap-4 px-4 py-3"
        >
          <div class="h-12 w-[260px] animate-pulse rounded bg-hairline-soft" />
          <div class="flex-1 space-y-2">
            <div class="h-4 w-1/2 animate-pulse rounded bg-hairline-soft" />
            <div class="h-3 w-1/3 animate-pulse rounded bg-hairline-soft" />
          </div>
        </div>
      </div>

      <!-- Error -->
      <div
        v-else-if="audios.error"
        class="card mx-auto mt-6 max-w-[520px] p-6 text-center text-[13px]"
      >
        <p class="text-accent font-medium">API への接続に失敗しました</p>
        <p class="mt-1 text-muted">{{ audios.error }}</p>
        <button
          class="btn-primary mt-4"
          @click="audios.fetch()"
        >再試行</button>
      </div>

      <!-- Empty (no data at all) -->
      <div
        v-else-if="audios.total === 0 && !audios.searchQuery"
        class="py-16 text-center text-[13px] text-muted"
      >
        まだ公開されている音源はありません。
      </div>

      <!-- Filtered empty -->
      <div
        v-else-if="audios.paged.length === 0"
        class="py-16 text-center text-[13px] text-muted"
      >
        「{{ audios.searchQuery }}」に一致する音源は見つかりませんでした。
      </div>

      <!-- Normal list -->
      <div v-else class="space-y-2">
        <AudioCard v-for="t in audios.paged" :key="t.id" :track="t" />
      </div>
    </div>

  </div>
</template>

<style scoped>
/* Panel expand: CardNav 風 height + opacity */
.panel-enter-active { transition: opacity 200ms ease-out, transform 280ms cubic-bezier(0.34, 1.56, 0.64, 1); transform-origin: top; }
.panel-leave-active { transition: opacity 150ms ease-in, transform 200ms ease-in; transform-origin: top; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(-8px) scaleY(0.92); }

/* Tag chip stagger */
.tag-chip-anim {
  animation: chipIn 380ms cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
}
@keyframes chipIn {
  0%   { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}

/* hide scrollbar inside panel */
.overflow-y-auto::-webkit-scrollbar { display: none; }
.overflow-y-auto { scrollbar-width: none; }

/* Active tag chip enter/leave */
.chip-enter-active, .chip-leave-active { transition: opacity 180ms, transform 180ms; }
.chip-enter-from { opacity: 0; transform: scale(0.8); }
.chip-leave-to   { opacity: 0; transform: scale(0.8); }
.chip-leave-active { position: absolute; }
</style>
