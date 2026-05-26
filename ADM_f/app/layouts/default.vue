<script setup lang="ts"></script>

<template>
  <div class="flex h-screen flex-col overflow-hidden">
    <TopNav />

    <div class="flex-1 overflow-hidden">
      <slot />
    </div>

    <!-- Footer: 文字だけ浮いている状態、ボーダーなし -->
    <footer class="shrink-0">
      <div class="mx-auto flex h-12 max-w-[1200px] items-center justify-center gap-6 px-6 text-[11px] text-muted/70">
        <span>© {{ new Date().getFullYear() }} Pathfinder</span>
        <span class="font-mono">v0.3.0</span>
      </div>
    </footer>
  </div>
</template>
