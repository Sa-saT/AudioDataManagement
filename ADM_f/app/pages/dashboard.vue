<script setup lang="ts">
import { useAudiosStore } from '~/stores/audios'
import { useAuthStore } from '~/stores/auth'

definePageMeta({ layout: 'default' })
useHead({ title: 'Dashboard — Pathfinder' })

const audios = useAudiosStore()
const auth = useAuthStore()

onMounted(async () => {
  auth.hydrate()
  await audios.fetch()
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

const allTags = computed(() => {
  const map = new Map<string, number>()
  for (const t of audios.items) {
    if (!t.tags) continue
    for (const tag of t.tags) {
      map.set(tag, (map.get(tag) ?? 0) + 1)
    }
  }
  return Array.from(map.entries()).sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1]
    return a[0].localeCompare(b[0])
  })
})

const filteredTags = computed(() => {
  const q = searchInput.value.trim().toLowerCase()
  if (!q) return allTags.value
  return allTags.value.filter(([tag]) => tag.toLowerCase().includes(q))
})

function highlight(tag: string): string {
  const q = searchInput.value.trim()
  if (!q) return tag
  const idx = tag.toLowerCase().indexOf(q.toLowerCase())
  if (idx < 0) return tag
  return (
    tag.slice(0, idx) +
    `<mark class="bg-transparent text-primary-active font-semibold">` +
    tag.slice(idx, idx + q.length) +
    `</mark>` +
    tag.slice(idx + q.length)
  )
}

function pickTag(tag: string) {
  searchInput.value = tag
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
      <p v-if="!auth.isActivated" class="text-[13px] text-accent">
        * アクティベートされていません。ダウンロードは不可。
      </p>
      <span v-else />

      <div v-if="auth.isActivated" class="flex items-center gap-4">
        <div class="flex min-w-[200px] flex-col gap-1">
          <div class="flex justify-between font-mono text-[11px] text-muted">
            <span>TOKENS</span>
            <span :class="tokenLow ? 'text-accent' : ''">
              {{ tokensUsed.toLocaleString('ja-JP') }} / {{ monthlyQuota.toLocaleString('ja-JP') }}
            </span>
          </div>
          <div class="h-1 overflow-hidden rounded-full border border-hairline-soft bg-white/50">
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
            placeholder="タイトル / クリエイター / タグで検索…"
            class="w-full rounded-lg border bg-white/60 py-1.5 pl-8 pr-8 text-[12px] text-ink placeholder:text-muted-soft backdrop-blur-sm outline-none transition-all"
            :class="searchFocused ? 'border-primary bg-white/85 shadow-sm' : 'border-hairline'"
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
            class="absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-[60vh] overflow-y-auto rounded-xl border border-hairline bg-white/90 p-4 shadow-xl backdrop-blur-md"
          >
            <div class="mb-3 flex items-center justify-between text-[10px] font-semibold uppercase tracking-widest text-muted">
              <span>タグから絞り込み</span>
              <span class="font-mono">{{ filteredTags.length }} / {{ allTags.length }}</span>
            </div>

            <div v-if="filteredTags.length > 0" class="flex flex-wrap gap-1.5">
              <button
                v-for="([tag, count], idx) in filteredTags"
                :key="tag"
                class="tag-chip-anim group flex items-center gap-1.5 rounded-full border border-hairline bg-white/70 px-2.5 py-1 font-mono text-[11px] text-body transition-all hover:-translate-y-px hover:border-primary hover:bg-white"
                :style="`animation-delay: ${Math.min(idx * 22, 300)}ms`"
                @click="pickTag(tag)"
              >
                <span v-html="highlight(tag)" />
                <span class="rounded-full bg-hairline-soft px-1.5 py-0 text-[10px] text-muted group-hover:bg-primary/15 group-hover:text-primary-active">
                  {{ count }}
                </span>
              </button>
            </div>
            <div v-else class="py-4 text-center text-[12px] text-muted">
              「{{ searchInput }}」に一致するタグはありません
            </div>

          </div>
        </Transition>
      </div>

      <!-- Per-page + 全件 統合表示: ◀ [perPage] ▶ / 全 [total] 件 -->
      <div class="flex shrink-0 items-center gap-1 font-mono text-[12px]">
        <template v-if="audios.showPerPageStepper">
          <button
            class="rounded-sm px-2 py-1 text-muted hover:text-ink disabled:opacity-30"
            :disabled="audios.perPage === audios.perPageOptions[0]"
            @click="onPrev"
          >◀</button>
          <div class="flex items-center justify-center rounded-md bg-primary px-3 py-1 text-white">
            <NumberRoller
              :value="audios.perPage"
              :digits="Math.max(2, audios.perPage.toString().length)"
              :font-size="13"
              font-weight="600"
              hide-leading-zeros
            />
          </div>
          <button
            class="rounded-sm px-2 py-1 text-muted hover:text-ink disabled:opacity-30"
            :disabled="audios.perPage === audios.perPageOptions[audios.perPageOptions.length - 1]"
            @click="onNext"
          >▶</button>
        </template>

        <!-- total < 5: 静的に [total] -->
        <div
          v-else
          class="flex items-center justify-center rounded-md bg-primary px-3 py-1 font-semibold text-white"
        >{{ audios.total }}</div>

        <!-- /全 N 件 -->
        <span class="ml-1 flex items-center gap-0.5 text-body">
          <span>/ 全</span>
          <NumberRoller
            :value="listCount"
            :digits="countDigits"
            :font-size="12"
            font-weight="500"
            hide-leading-zeros
          />
          <span>件</span>
        </span>
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
          class="mt-4 rounded-md bg-ink px-4 py-1.5 text-[12px] font-medium text-canvas hover:bg-primary"
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
</style>
