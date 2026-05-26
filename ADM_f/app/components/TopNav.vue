<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const route = useRoute()

onMounted(() => {
  auth.hydrate()
})

const isActive = (path: string) => route.path === path
</script>

<template>
  <header class="border-b border-hairline bg-canvas">
    <div class="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-6">
      <NuxtLink to="/dashboard" class="flex items-center gap-2">
        <span class="text-[20px] font-semibold tracking-[-0.02em] text-ink">ADM</span>
        <span class="text-[13px] text-muted">/ Audio Data Management</span>
      </NuxtLink>

      <nav class="flex items-center gap-6 text-sm">
        <NuxtLink
          to="/dashboard"
          :class="['text-body hover:text-ink', isActive('/dashboard') && 'text-ink font-medium']"
        >
          Dashboard
        </NuxtLink>
        <NuxtLink
          to="/activate"
          :class="['text-body hover:text-ink', isActive('/activate') && 'text-ink font-medium']"
        >
          Activate
        </NuxtLink>
      </nav>

      <div class="flex items-center gap-3">
        <span
          class="pill"
          :class="auth.isActivated ? 'bg-ink text-canvas' : 'bg-surface-strong text-ink'"
        >
          {{ auth.role }}
        </span>
        <span class="text-sm text-body">{{ auth.displayName }}</span>
        <button
          v-if="auth.isActivated"
          class="text-sm text-muted hover:text-ink"
          @click="auth.deactivate()"
        >
          解除
        </button>
      </div>
    </div>
  </header>
</template>
