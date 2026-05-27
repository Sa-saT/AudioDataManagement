<script setup lang="ts"></script>

<template>
  <div class="flex h-screen flex-col overflow-hidden">
    <TopNav />

    <div class="flex-1 overflow-hidden">
      <slot />
    </div>

    <footer class="shrink-0" style="background:transparent;">
      <div class="mx-auto flex h-11 max-w-[1200px] items-center justify-center gap-6 px-6">
        <span class="text-[12px] font-semibold text-ink" style="text-shadow:0 1px 3px rgba(255,255,255,0.85);">© {{ new Date().getFullYear() }} Pathfinder</span>
        <span class="font-mono text-[11px] font-medium text-body-strong" style="text-shadow:0 1px 3px rgba(255,255,255,0.85);">v0.3.0</span>
      </div>
    </footer>
  </div>
</template>
