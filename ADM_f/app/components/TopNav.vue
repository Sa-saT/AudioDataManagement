<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

onMounted(() => auth.hydrate())

const isActive = (path: string) => route.path === path

// ─── Dropdown menu ────────────────────────────────
const menuOpen = ref(false)
const menuRef = ref<HTMLDivElement | null>(null)
const toggleMenu = () => { menuOpen.value = !menuOpen.value }
const closeMenu = () => { menuOpen.value = false }

function onDocClick(e: MouseEvent) {
  if (!menuRef.value) return
  if (!menuRef.value.contains(e.target as Node)) closeMenu()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

// ─── Activate modal ────────────────────────────────
const showModal = ref(false)
const fileName = ref<string | null>(null)
const errorMsg = ref<string | null>(null)

function openActivate() {
  fileName.value = null
  errorMsg.value = null
  showModal.value = true
  closeMenu()
}
function closeActivate() { showModal.value = false }

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
    await auth.activateFromFile(f)
    closeActivate()
  } catch (err: unknown) {
    const e = err as { data?: { detail?: { code?: string; message?: string } | string }; message?: string }
    const detail = e?.data?.detail
    if (typeof detail === 'object' && detail?.message) {
      errorMsg.value = detail.message
    } else if (typeof detail === 'string') {
      errorMsg.value = detail
    } else {
      errorMsg.value = e?.message ?? 'アクティベートに失敗しました。'
    }
  }
}

function deactivate() {
  auth.deactivate()
  closeMenu()
}

function goTo(path: string) {
  router.push(path)
  closeMenu()
}

const isCreator = computed(() => auth.role === 'creator' || auth.role === 'admin')
const isAdmin = computed(() => auth.role === 'admin')
</script>

<template>
  <header
    class="sticky top-0 z-10 h-12 border-b border-hairline backdrop-blur-[14px] saturate-150"
    style="background: rgba(255,255,255,0.55);"
  >
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

      <!-- Right: dropdown menu -->
      <div ref="menuRef" class="relative">
        <button
          class="flex items-center gap-2 px-1 py-1.5 text-[12px] text-ink transition-colors hover:text-primary-active"
          aria-label="メニュー"
          @click.stop="toggleMenu"
        >
          <span v-if="auth.isActivated" class="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-widest"
            :style="auth.role === 'admin'
              ? 'background:#ff634722;color:#c0392b;border:1px solid #ff634755'
              : auth.role === 'creator'
                ? 'background:#20b2aa22;color:#0e7a74;border:1px solid #20b2aa55'
                : 'background:#26251e18;color:#26251e;border:1px solid #26251e30'"
          >{{ auth.role }}</span>
          <span v-if="auth.isActivated" class="text-[12px] font-medium text-ink">{{ auth.displayName }}</span>
          <span class="hamburger" :class="{ open: menuOpen }">
            <span class="line line-top"></span>
            <span class="line line-bot"></span>
          </span>
        </button>

        <!-- Dropdown panel -->
        <Transition name="menu">
          <div
            v-if="menuOpen"
            class="absolute right-0 top-[calc(100%+6px)] w-56 overflow-hidden rounded-lg border border-hairline bg-white/85 shadow-lg backdrop-blur-md"
          >
            <!-- Activate / Deactivate -->
            <button
              v-if="!auth.isActivated"
              class="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] text-ink transition-colors hover:bg-white"
              @click="openActivate"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
              </svg>
              Activate
            </button>
            <button
              v-else
              class="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] text-ink transition-colors hover:bg-white"
              @click="deactivate"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 5 12 10 7"/><line x1="5" y1="12" x2="15" y2="12"/>
              </svg>
              Deactivate
            </button>

            <!-- Downloads (all roles) -->
            <button
              class="flex w-full items-center gap-2 border-t border-hairline-soft px-4 py-2.5 text-left text-[13px] text-ink transition-colors hover:bg-white"
              @click="goTo('/downloads')"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Downloads
            </button>

            <!-- Uploads (creator / admin) -->
            <button
              v-if="isCreator"
              class="flex w-full items-center gap-2 border-t border-hairline-soft px-4 py-2.5 text-left text-[13px] text-ink transition-colors hover:bg-white"
              @click="goTo('/uploads')"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              Uploads
              <span class="ml-auto rounded bg-primary/15 px-1.5 py-0.5 font-mono text-[10px] text-primary-active">creator</span>
            </button>

            <!-- Admin (admin のみ) -->
            <button
              v-if="isAdmin"
              class="flex w-full items-center gap-2 border-t border-hairline-soft px-4 py-2.5 text-left text-[13px] text-ink transition-colors hover:bg-white"
              @click="goTo('/admin')"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              Admin
              <span class="ml-auto rounded bg-accent/15 px-1.5 py-0.5 font-mono text-[10px] text-accent">admin</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>

  <!-- Activate modal -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-start justify-center bg-black/25 pt-24 backdrop-blur-sm"
        @click.self="closeActivate"
      >
        <div class="card mx-4 w-full max-w-[480px] p-6">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-[16px] font-semibold text-ink">Activate</h2>
            <button class="text-muted hover:text-ink" @click="closeActivate">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <p class="mb-4 text-[13px] text-body">
            お手持ちの <span class="font-mono">.lic</span> ファイルを選択してアクティベートしてください。
          </p>
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

.menu-enter-active, .menu-leave-active { transition: opacity 150ms, transform 150ms; }
.menu-enter-from, .menu-leave-to { opacity: 0; transform: translateY(-4px); }

/* 2-line hamburger → X (transform-only animation, 参考: helloworld753315/vue_hamburger) */
.hamburger {
  position: relative;
  display: inline-block;
  width: 18px;
  height: 14px;
  color: currentColor;
}
.hamburger .line {
  position: absolute;
  left: 0;
  width: 100%;
  height: 1.6px;
  background: currentColor;
  border-radius: 1px;
  transform-origin: center;
  transition: transform 0.4s ease;
}
.hamburger .line-top { top: 4px; }
.hamburger .line-bot { top: 10px; }
.hamburger.open .line-top { transform: translateY(3px) rotate(-45deg); }
.hamburger.open .line-bot { transform: translateY(-3px) rotate(45deg); }
</style>
