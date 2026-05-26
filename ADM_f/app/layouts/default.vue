<script setup lang="ts"></script>

<template>
  <div class="min-h-screen text-ink">
    <TopNav />
    <main class="mx-auto max-w-[1200px] px-6 py-8">
      <slot />
    </main>
    <footer class="mt-16 border-t border-primary">
      <div class="mx-auto flex h-16 max-w-[1200px] items-center justify-center gap-6 px-6 text-[12px] text-body">
        <span>© {{ new Date().getFullYear() }} Pathfinder</span>
        <span class="font-mono text-muted">v0.3.0</span>
      </div>
    </footer>
  </div>
</template>
