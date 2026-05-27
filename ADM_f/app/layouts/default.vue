<script setup lang="ts"></script>

<template>
  <div class="flex h-screen flex-col overflow-hidden">
    <TopNav />

    <div class="flex-1 overflow-hidden">
      <slot />
    </div>

    <footer class="shrink-0 border-t border-hairline" style="background:rgba(255,255,255,0.60);backdrop-filter:blur(8px);">
      <div class="mx-auto flex h-11 max-w-[1200px] items-center justify-center gap-6 px-6">
        <span class="text-[12px] font-medium text-body-strong">© {{ new Date().getFullYear() }} Pathfinder</span>
        <span class="font-mono text-[11px] text-body">v0.3.0</span>
      </div>
    </footer>
  </div>
</template>
