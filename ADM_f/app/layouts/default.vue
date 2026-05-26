<script setup lang="ts"></script>

<template>
  <div class="flex h-screen flex-col overflow-hidden">
    <!-- Sticky header -->
    <TopNav />

    <!-- Page content: fixed height, scroll is delegated to child pages -->
    <div class="flex-1 overflow-hidden">
      <slot />
    </div>

    <!-- Footer: fixed at bottom -->
    <footer class="shrink-0 border-t border-primary">
      <div class="mx-auto flex h-14 max-w-[1200px] items-center justify-center gap-6 px-6 text-[12px] text-body">
        <span>© {{ new Date().getFullYear() }} Pathfinder</span>
        <span class="font-mono text-muted">v0.3.0</span>
      </div>
    </footer>
  </div>
</template>
