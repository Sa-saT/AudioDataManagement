<script setup lang="ts">
import { useAudiosStore } from '~/stores/audios'
import { useAuthStore } from '~/stores/auth'
import type { SortKey } from '~/types/audio'

definePageMeta({ layout: 'default' })
useHead({ title: 'Dashboard — Audio Data Management' })

const audios = useAudiosStore()
const auth = useAuthStore()
onMounted(() => auth.hydrate())

const perPageOptions = [25, 50, 100, 200] as const
const sortOptions: Array<{ key: SortKey; label: string }> = [
  { key: 'recommended', label: 'オススメ順' },
  { key: 'newest', label: '新着順' },
]

const rangeLabel = computed(() => {
  const start = (audios.page - 1) * audios.perPage + 1
  const end = Math.min(audios.page * audios.perPage, audios.totalCount)
  return `${start}件 - ${end}件`
})
</script>

<template>
  <div>
    <!-- Header bar -->
    <div class="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 class="text-[26px] font-normal tracking-[-0.0125em] text-ink">Dashboard</h1>
        <p class="mt-1 text-[13px] text-body">
          {{ rangeLabel }} / 全{{ audios.totalCount }}件
          <span v-if="!auth.isActivated" class="ml-2 text-error">
            * アクティベートされていません。ダウンロードは不可。
          </span>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-2 text-[12px] text-muted">
          <span>表示順:</span>
          <button
            v-for="opt in sortOptions"
            :key="opt.key"
            class="rounded-sm px-2 py-1"
            :class="
              audios.sort === opt.key
                ? 'bg-ink text-canvas'
                : 'text-body hover:text-ink'
            "
            @click="audios.setSort(opt.key)"
          >
            {{ opt.label }}
          </button>
        </div>

        <div class="flex items-center gap-2 text-[12px] text-muted">
          <span>表示件数:</span>
          <button
            v-for="n in perPageOptions"
            :key="n"
            class="rounded-sm px-2 py-1"
            :class="
              audios.perPage === n
                ? 'bg-ink text-canvas'
                : 'text-body hover:text-ink'
            "
            @click="audios.setPerPage(n)"
          >
            {{ n }}
          </button>
        </div>

        <div class="flex items-center gap-1 font-mono text-[12px] text-muted">
          <button
            class="rounded-sm px-2 py-1 hover:text-ink disabled:opacity-30"
            :disabled="audios.page <= 1"
            @click="audios.setPage(audios.page - 1)"
          >
            ‹
          </button>
          <span>{{ audios.page }} / {{ audios.pageCount }}</span>
          <button
            class="rounded-sm px-2 py-1 hover:text-ink disabled:opacity-30"
            :disabled="audios.page >= audios.pageCount"
            @click="audios.setPage(audios.page + 1)"
          >
            ›
          </button>
        </div>
      </div>
    </div>

    <!-- List -->
    <div class="space-y-2">
      <AudioCard v-for="t in audios.paged" :key="t.id" :track="t" />
    </div>
  </div>
</template>
