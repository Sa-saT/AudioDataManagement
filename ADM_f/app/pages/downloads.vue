<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

definePageMeta({ layout: 'default' })
useHead({ title: 'Downloads — Pathfinder' })

const auth = useAuthStore()
onMounted(() => auth.hydrate())
</script>

<template>
  <div class="mx-auto flex h-full max-w-[1200px] flex-col px-6 py-6">
    <h1 class="text-[22px] font-normal tracking-[-0.0125em] text-ink">My Downloads</h1>
    <p class="mt-1 text-[13px] text-body">
      ダウンロード済みの音源をここで再取得できます。
    </p>

    <div class="mt-6 flex-1 overflow-y-auto">
      <div v-if="!auth.isActivated" class="card p-6 text-[13px] text-body">
        アクティベートしていないため、ダウンロード履歴はありません。
      </div>
      <div v-else class="card p-6 text-[13px] text-body">
        まだダウンロードされた音源はありません。
      </div>
    </div>
  </div>
</template>
