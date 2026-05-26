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
  <header class="sticky top-0 z-10 h-12 border-b border-hairline-soft/50">
    <div class="mx-auto flex h-full max-w-[1200px] items-center gap-8 px-6">
      <!-- Brand -->
      <NuxtLink to="/dashboard" class="flex items-center gap-2 text-[15px] font-bold tracking-[-0.03em] text-ink">
        <span class="relative flex h-4 w-4 items-center justify-center rounded-full border-[1.5px] border-primary">
          <span class="h-[5px] w-[5px] rounded-full bg-primary" />
        </span>
        Pathfinder
      </NuxtLink>

      <!-- Nav -->
      <nav class="flex items-center gap-5">
        <NuxtLink
          v-for="link in [
            { to: '/dashboard', label: 'Dashboard' },
            { to: '/activate',  label: 'Activate' },
          ]"
          :key="link.to"
          :to="link.to"
          class="relative flex h-12 items-center text-[13px] font-medium text-ink transition-opacity"
          :class="isActive(link.to) ? 'opacity-100' : 'opacity-[0.55] hover:opacity-100'"
        >
          {{ link.label }}
          <span
            v-if="isActive(link.to)"
            class="absolute inset-x-0 -bottom-px h-0.5 rounded-sm bg-primary"
          />
        </NuxtLink>
      </nav>
    </div>
  </header>
</template>
