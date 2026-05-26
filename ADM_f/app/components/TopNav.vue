<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const route = useRoute()

onMounted(() => auth.hydrate())

const isActive = (path: string) => route.path === path

// Activate modal
const showModal = ref(false)
const fileName = ref<string | null>(null)
const errorMsg = ref<string | null>(null)

function openModal() {
  fileName.value = null
  errorMsg.value = null
  showModal.value = true
}
function closeModal() { showModal.value = false }

async function onPick(e: Event) {
  errorMsg.value = null
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  fileName.value = f.name
  if (!f.name.toLowerCase().endsWith('.lic')) {
    errorMsg.value = '拡張子が .lic のファイルを選択してください。'
    return
  }
  try {
    const text = await f.text()
    auth.activateFromText(text)
    closeModal()
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : 'アクティベートに失敗しました。'
  }
}

function deactivate() {
  auth.deactivate()
}
</script>

<template>
  <header class="sticky top-0 z-10 h-12 border-b border-hairline-soft/50">
    <div class="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">

      <!-- Left: brand + nav -->
      <div class="flex items-center gap-8">
        <NuxtLink to="/dashboard" class="flex items-center gap-2 text-[15px] font-bold tracking-[-0.03em] text-ink">
          <span class="relative flex h-4 w-4 items-center justify-center rounded-full border-[1.5px] border-primary">
            <span class="h-[5px] w-[5px] rounded-full bg-primary" />
          </span>
          Pathfinder
        </NuxtLink>

        <nav class="flex items-center gap-5">
          <NuxtLink
            to="/dashboard"
            class="relative flex h-12 items-center text-[13px] font-medium text-ink transition-opacity"
            :class="isActive('/dashboard') ? 'opacity-100' : 'opacity-[0.55] hover:opacity-100'"
          >
            Dashboard
            <span v-if="isActive('/dashboard')" class="absolute inset-x-0 -bottom-px h-0.5 rounded-sm bg-primary" />
          </NuxtLink>
        </nav>
      </div>

      <!-- Right: activate / deactivate -->
      <div class="flex items-center gap-3">
        <template v-if="auth.isActivated">
          <span class="rounded-full bg-ink px-3 py-1 font-mono text-[11px] font-medium uppercase tracking-widest text-canvas">
            {{ auth.role }}
          </span>
          <span class="text-[13px] text-body">{{ auth.displayName }}</span>
          <button
            class="rounded-md border border-hairline px-3 py-1 text-[12px] text-muted transition-colors hover:border-accent hover:text-accent"
            @click="deactivate"
          >Deactivate</button>
        </template>
        <template v-else>
          <button
            class="rounded-md bg-ink px-3 py-1.5 text-[12px] font-medium text-canvas transition-colors hover:bg-primary hover:text-white"
            @click="openModal"
          >Activate</button>
        </template>
      </div>
    </div>
  </header>

  <!-- Activate modal -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-start justify-center bg-black/25 pt-24 backdrop-blur-sm"
        @click.self="closeModal"
      >
        <div class="card mx-4 w-full max-w-[480px] p-6">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-[16px] font-semibold text-ink">Activate</h2>
            <button class="text-muted hover:text-ink" @click="closeModal">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <p class="mb-4 text-[13px] text-body">
            お手持ちの <span class="font-mono">.lic</span> ファイルを選択してアクティベートしてください。
          </p>

          <!-- File drop zone -->
          <label class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-hairline-strong bg-white/40 px-6 py-8 text-center transition-colors hover:border-primary hover:bg-white/60">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="text-muted">
              <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
            </svg>
            <span class="text-[14px] text-ink">クリックして .lic ファイルを選択</span>
            <span class="font-mono text-[11px] text-muted">{{ fileName ?? '*.lic' }}</span>
            <input
              type="file"
              accept=".lic,application/octet-stream,text/plain,application/json"
              class="hidden"
              @change="onPick"
            />
          </label>

          <p v-if="errorMsg" class="mt-3 text-[12px] text-accent">{{ errorMsg }}</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 150ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
