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

const mockMonthlyQuota = 30_000
const mockUsed = 12_438
const tokenPct = computed(() => Math.round((mockUsed / mockMonthlyQuota) * 100))
const tokenLow = computed(() => tokenPct.value >= 90)
</script>

<template>
  <!-- h-full + flex-col: 一覧のみスクロール、ヘッダ・コントロールは固定 -->
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6">

    <!-- ① Status row (h1 なし) -->
    <div class="flex shrink-0 flex-wrap items-center justify-between gap-4 pt-5 pb-3">
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
        <button class="text-[12px] text-muted transition-colors hover:text-ink" @click="auth.deactivate()">
          解除
        </button>
      </div>
    </div>

    <!-- ② Controls: ソート / 件数 / ページネーション — スクロールしない -->
    <div class="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-hairline-soft py-2">
      <div class="flex flex-wrap items-center gap-4">
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

      <div class="flex items-center gap-1 font-mono text-[12px] text-muted">
        <button
          class="rounded-sm px-2 py-1 hover:text-ink disabled:opacity-30"
          :disabled="audios.page <= 1"
          @click="audios.setPage(audios.page - 1)"
        >‹</button>
        <span>{{ audios.page }} / {{ audios.pageCount }}</span>
        <button
          class="rounded-sm px-2 py-1 hover:text-ink disabled:opacity-30"
          :disabled="audios.page >= audios.pageCount"
          @click="audios.setPage(audios.page + 1)"
        >›</button>
      </div>
    </div>

    <!-- ③ Card list: ここだけスクロール -->
    <div class="flex-1 overflow-y-auto py-3">
      <div class="space-y-2">
        <AudioCard v-for="t in audios.paged" :key="t.id" :track="t" />
      </div>
    </div>

  </div>
</template>
