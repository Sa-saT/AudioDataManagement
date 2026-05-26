<script setup lang="ts"></script>

<template>
  <div class="min-h-screen bg-canvas text-ink">
    <TopNav />
    <main class="mx-auto max-w-[1200px] px-6 py-8">
      <slot />
    </main>
    <footer class="mt-16 border-t border-hairline">
      <div class="mx-auto max-w-[1200px] px-6 py-8 text-[13px] text-body">
        © {{ new Date().getFullYear() }} Audio Data Management
      </div>
    </footer>
  </div>
</template>
