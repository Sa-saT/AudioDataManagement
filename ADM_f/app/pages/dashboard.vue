<script setup lang="ts">
import { useAudiosStore } from '~/stores/audios'
import { useAuthStore } from '~/stores/auth'
import type { SortKey } from '~/types/audio'

definePageMeta({ layout: 'default' })
useHead({ title: 'Dashboard — Pathfinder' })

const audios = useAudiosStore()
const auth = useAuthStore()
onMounted(() => auth.hydrate())

const perPageOptions = [25, 50, 100, 200] as const
const sortOptions: Array<{ key: SortKey; label: string }> = [
  { key: 'recommended', label: 'オススメ順' },
  { key: 'newest',      label: '新着順' },
]

const rangeLabel = computed(() => {
  const start = (audios.page - 1) * audios.perPage + 1
  const end = Math.min(audios.page * audios.perPage, audios.totalCount)
  return `${start}–${end}`
})

// Windowed page number buttons  ◀ 3 4 [5] 6 7 ▶
const pageWindow = computed(() => {
  const total = audios.pageCount
  const cur = audios.page
  const size = 5
  let start = Math.max(1, cur - Math.floor(size / 2))
  const end = Math.min(total, start + size - 1)
  if (end - start < size - 1) start = Math.max(1, end - size + 1)
  const pages: number[] = []
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

// Token state (mock — replaced by real API in Phase 3)
const mockMonthlyQuota = 30_000
const mockUsed = 12_438
const tokenPct = computed(() => Math.round((mockUsed / mockMonthlyQuota) * 100))
const tokenLow = computed(() => tokenPct.value >= 90)

// Search
const searchInput = ref(audios.searchQuery)
watch(searchInput, (v) => audios.setSearch(v))
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- ① Status row -->
    <div class="flex shrink-0 flex-wrap items-center justify-between gap-4 pb-3 pt-5">
      <p class="text-[13px] text-body">
        {{ rangeLabel }} / 全{{ audios.totalCount }}件
        <span v-if="!auth.isActivated" class="ml-2 text-accent">
          * アクティベートされていません。ダウンロードは不可。
        </span>
      </p>

      <div v-if="auth.isActivated" class="flex items-center gap-4">
        <div class="flex min-w-[200px] flex-col gap-1">
          <div class="flex justify-between font-mono text-[11px] text-muted">
            <span>TOKENS</span>
            <span :class="tokenLow ? 'text-accent' : ''">
              {{ mockUsed.toLocaleString('ja-JP') }} / {{ mockMonthlyQuota.toLocaleString('ja-JP') }}
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
        <span class="rounded-full bg-ink px-3 py-1 font-mono text-[11px] font-medium uppercase tracking-widest text-canvas">
          {{ auth.role }}
        </span>
        <span class="text-[13px] text-body">{{ auth.displayName }}</span>
      </div>
    </div>

    <!-- ② Search bar -->
    <div class="shrink-0 pb-2">
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          v-model="searchInput"
          type="search"
          placeholder="タイトル / クリエイター / タグで検索…"
          class="w-full rounded-lg border border-hairline bg-white/60 py-2 pl-9 pr-4 text-[13px] text-ink placeholder:text-muted-soft backdrop-blur-sm outline-none transition-colors focus:border-primary focus:bg-white/80"
        />
        <button
          v-if="searchInput"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
          @click="searchInput = ''"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- ③ Controls: ソート / 件数 / ページネーション — 固定 -->
    <div class="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-hairline-soft py-2">
      <div class="flex flex-wrap items-center gap-4">
        <!-- Sort -->
        <div class="flex items-center gap-2 text-[12px] text-muted">
          <span>表示順:</span>
          <button
            v-for="opt in sortOptions"
            :key="opt.key"
            class="rounded-sm px-2 py-1 transition-colors"
            :class="audios.sort === opt.key ? 'bg-ink text-canvas' : 'text-body hover:text-ink'"
            @click="audios.setSort(opt.key)"
          >{{ opt.label }}</button>
        </div>

        <!-- Per page -->
        <div class="flex items-center gap-2 text-[12px] text-muted">
          <span>表示件数:</span>
          <button
            v-for="n in perPageOptions"
            :key="n"
            class="rounded-sm px-2 py-1 transition-colors"
            :class="audios.perPage === n ? 'bg-ink text-canvas' : 'text-body hover:text-ink'"
            @click="audios.setPerPage(n)"
          >{{ n }}</button>
        </div>
      </div>

      <!-- Windowed pagination: ◀ 3 4 [5] 6 7 ▶ -->
      <div class="flex items-center gap-1 font-mono text-[12px]">
        <button
          class="rounded-sm px-2 py-1 text-muted hover:text-ink disabled:opacity-30"
          :disabled="audios.page <= 1"
          @click="audios.setPage(audios.page - 1)"
        >◀</button>

        <template v-for="p in pageWindow" :key="p">
          <button
            class="min-w-[28px] rounded-sm px-2 py-1 transition-colors"
            :class="p === audios.page
              ? 'bg-primary text-white font-semibold'
              : 'text-body hover:text-ink'"
            @click="audios.setPage(p)"
          >{{ p }}</button>
        </template>

        <button
          class="rounded-sm px-2 py-1 text-muted hover:text-ink disabled:opacity-30"
          :disabled="audios.page >= audios.pageCount"
          @click="audios.setPage(audios.page + 1)"
        >▶</button>
      </div>
    </div>

    <!-- ④ Card list — ここだけスクロール -->
    <div class="flex-1 overflow-y-auto py-3">
      <div v-if="audios.paged.length === 0" class="py-16 text-center text-[13px] text-muted">
        「{{ audios.searchQuery }}」に一致する音源は見つかりませんでした。
      </div>
      <div v-else class="space-y-2">
        <AudioCard v-for="t in audios.paged" :key="t.id" :track="t" />
      </div>
    </div>

  </div>
</template>
