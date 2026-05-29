<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useSystemStore } from '~/stores/system'

const auth = useAuthStore()
const system = useSystemStore()

onMounted(async () => {
  auth.hydrate()
  await system.fetchCommissionStatus()
  if (auth.isActivated && system.commissionEnabled) {
    // 改訂2: 主要ページ訪問時に session ping (30分dedupはサーバ側)
    system.sessionPing()
    system.fetchCommissionUnread()
  }
})

const route = useRoute()
const router = useRouter()

const isActive = (path: string) => route.path === path

// ─── Dropdown menu ────────────────────────────────
const menuOpen = ref(false)
const menuRef = ref<HTMLDivElement | null>(null)
const toggleMenu = () => { menuOpen.value = !menuOpen.value }
const closeMenu = () => {
  menuOpen.value = false
  infoOpen.value = null
}

function onDocClick(e: MouseEvent) {
  if (!menuRef.value) return
  if (!menuRef.value.contains(e.target as Node)) closeMenu()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

// ─── (i) info panel ───────────────────────────────
const infoOpen = ref<string | null>(null)
function toggleInfo(key: string) {
  infoOpen.value = infoOpen.value === key ? null : key
}

// Close info when menu closes
watch(menuOpen, (v) => { if (!v) infoOpen.value = null })

// ─── Menu item definitions ────────────────────────
const INFO: Record<string, string> = {
  activate:    'ライセンスファイル (.lic) を適用してユーザーロールを有効化します',
  deactivate:  'ロールを解除してゲストモードに戻ります。再アクティベートは .lic ファイルから行えます',
  commission:  'オリジナル音源の制作依頼フロー。発注 → クリエイター選定 → 制作 → 承認まで一元管理します',
  downloads:   '購入済み音源の管理。ストレージ内のファイルを再ダウンロード・削除できます',
  uploads:     '音源のアップロード・公開設定・編集・削除ができます (creator / admin)',
  admin:       'ユーザー管理・payout 承認・lic 発行・token 付与・システム設定 (admin)',
}

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
// admin はメニューバーに Commission を出さない (Admin タブ > 発注管理から操作)
const showCommission = computed(() => auth.isActivated && system.commissionEnabled && !isAdmin.value)
// 改訂2: 通知二系統
//   要対応 (action_count > 0) → 橙 + 件数バッジ + 金ドット
//   情報のみ (action_count == 0 && has_info) → 橙のみ (件数なし)
//   両方ゼロ → デフォルト
const actionCount = computed(() => system.commissionActionCount)
const hasInfo = computed(() => system.commissionHasInfo)
const hasAction = computed(() => actionCount.value > 0)
const isHighlighted = computed(() => hasAction.value || hasInfo.value)
</script>

<template>
  <header
    class="sticky top-0 z-10 h-12 backdrop-blur-sm"
    style="background:transparent;"
  >
    <div class="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">

      <!-- Left: brand + nav -->
      <div class="flex items-center gap-8" style="text-shadow:0 1px 3px rgba(255,255,255,0.8);">
        <NuxtLink to="/dashboard" class="flex items-center gap-2 text-[15px] font-bold tracking-[-0.03em] text-ink">
          <img src="/kapikapi.png" alt="" class="h-9 w-9 object-contain" />
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
          class="relative flex items-center gap-2 px-1 py-1.5 text-[12px]"
          :class="isHighlighted ? 'text-[#ffa500]' : 'text-ink'"
          style="text-shadow:0 1px 3px rgba(255,255,255,0.8);"
          aria-label="メニュー"
          @click.stop="toggleMenu"
        >
          <!-- Gold notification dot (top-left of button) — 要対応がある時のみ -->
          <span
            v-if="hasAction"
            class="absolute -left-0.5 -top-0.5 h-2 w-2 rounded-full"
            style="background:#ffd700;box-shadow:0 0 4px #ffd700cc;"
          />
          <span v-if="auth.isActivated" class="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-widest"
            :style="auth.role === 'admin'
              ? 'background:#ff634722;color:#c0392b;border:1px solid #ff634755'
              : auth.role === 'creator'
                ? 'background:#20b2aa22;color:#0e7a74;border:1px solid #20b2aa55'
                : 'background:#26251e18;color:#26251e;border:1px solid #26251e30'"
          >{{ auth.role }}</span>
          <span v-if="auth.isActivated" class="text-[12px] font-medium" :class="isHighlighted ? 'text-[#ffa500]' : 'text-ink'">{{ auth.displayName }}</span>
          <span class="hamburger" :class="{ open: menuOpen }">
            <span class="line line-top"></span>
            <span class="line line-bot"></span>
          </span>
        </button>

        <!-- Dropdown panel -->
        <Transition name="menu">
          <div
            v-if="menuOpen"
            class="absolute right-0 top-[calc(100%+6px)] w-60 overflow-hidden rounded-lg border border-hairline bg-white/85 shadow-lg backdrop-blur-md"
          >

            <!-- Admin (改訂: 最上部配置) -->
            <div v-if="isAdmin">
              <div
                class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-white/80"
                @click="goTo('/admin')"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="shrink-0">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                <span class="flex-1 text-[13px] text-ink">Admin</span>
                <span class="mr-1 rounded bg-accent/15 px-1.5 py-0.5 font-mono text-[9px] text-accent">admin</span>
                <button
                  class="group rounded-full p-0.5 transition-opacity"
                  :class="infoOpen === 'admin' ? 'text-ink' : ''"
                  @click.stop="toggleInfo('admin')"
                  aria-label="説明"
                >
                  <img src="/information.png" alt="info" class="h-[18px] w-[18px] opacity-50 transition-opacity group-hover:opacity-80" />
                </button>
              </div>
              <div v-if="infoOpen === 'admin'" class="border-t border-hairline-soft bg-white/40 px-4 pb-2.5 pt-2 text-[11px] leading-relaxed text-muted">
                {{ INFO.admin }}
              </div>
            </div>

            <!-- Commission (admin 以外) -->
            <div v-if="showCommission" :class="isAdmin ? 'border-t border-hairline-soft' : ''">
              <div
                class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-white/80"
                @click="goTo('/orders')"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                  :stroke="isHighlighted ? '#ffa500' : 'currentColor'"
                  stroke-width="1.8" class="shrink-0"
                >
                  <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                  <rect x="9" y="3" width="6" height="4" rx="1"/>
                  <line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/>
                </svg>
                <span class="flex-1 text-[13px] font-medium" :class="isHighlighted ? 'text-[#ffa500]' : 'text-ink'">Commission</span>
                <!-- 要対応: 件数バッジ -->
                <span
                  v-if="hasAction"
                  class="mr-1 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 font-mono text-[10px] font-bold text-white"
                  style="background:#ffa500;"
                >{{ actionCount }}</span>
                <!-- 情報のみ: ドット (件数なし) -->
                <span
                  v-else-if="hasInfo"
                  class="mr-1 h-1.5 w-1.5 shrink-0 rounded-full"
                  style="background:#ffa500;"
                  title="確認が必要な情報があります"
                />
                <span
                  v-else-if="route.path.startsWith('/orders')"
                  class="mr-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                />
                <button
                  class="group rounded-full p-0.5 transition-opacity"
                  :class="infoOpen === 'commission' ? 'text-ink' : ''"
                  @click.stop="toggleInfo('commission')"
                  aria-label="説明"
                >
                  <img src="/information.png" alt="info" class="h-[18px] w-[18px] opacity-50 transition-opacity group-hover:opacity-80" />
                </button>
              </div>
              <div v-if="infoOpen === 'commission'" class="border-t border-hairline-soft bg-white/40 px-4 pb-2.5 pt-2 text-[11px] leading-relaxed text-muted">
                {{ INFO.commission }}
              </div>
            </div>

            <!-- Uploads (creator / admin) -->
            <div v-if="isCreator" class="border-t border-hairline-soft">
              <div
                class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-white/80"
                @click="goTo('/uploads')"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="shrink-0">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <span class="flex-1 text-[13px] text-ink">Uploads</span>
                <span class="mr-1 rounded bg-primary/15 px-1.5 py-0.5 font-mono text-[9px] text-primary-active">creator</span>
                <button
                  class="group rounded-full p-0.5 transition-opacity"
                  :class="infoOpen === 'uploads' ? 'text-ink' : ''"
                  @click.stop="toggleInfo('uploads')"
                  aria-label="説明"
                >
                  <img src="/information.png" alt="info" class="h-[18px] w-[18px] opacity-50 transition-opacity group-hover:opacity-80" />
                </button>
              </div>
              <div v-if="infoOpen === 'uploads'" class="border-t border-hairline-soft bg-white/40 px-4 pb-2.5 pt-2 text-[11px] leading-relaxed text-muted">
                {{ INFO.uploads }}
              </div>
            </div>

            <!-- Downloads -->
            <div class="border-t border-hairline-soft">
              <div
                class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-white/80"
                @click="goTo('/downloads')"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="shrink-0">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                <span class="flex-1 text-[13px] text-ink">DL List</span>
                <button
                  class="group rounded-full p-0.5 transition-opacity"
                  :class="infoOpen === 'downloads' ? 'text-ink' : ''"
                  @click.stop="toggleInfo('downloads')"
                  aria-label="説明"
                >
                  <img src="/information.png" alt="info" class="h-[18px] w-[18px] opacity-50 transition-opacity group-hover:opacity-80" />
                </button>
              </div>
              <div v-if="infoOpen === 'downloads'" class="border-t border-hairline-soft bg-white/40 px-4 pb-2.5 pt-2 text-[11px] leading-relaxed text-muted">
                {{ INFO.downloads }}
              </div>
            </div>

            <!-- Activate / Deactivate — 常に最下段・視覚的に分離 -->
            <div class="border-t-2 border-hairline-strong">
              <!-- Activate (未アクティベート時・警告色) -->
              <div v-if="!auth.isActivated">
                <div
                  class="flex cursor-pointer items-center gap-2 bg-[#fff8f0] px-4 py-2.5 transition-colors hover:bg-[#fff0e0]"
                  @click="openActivate"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c0600a" stroke-width="1.8" class="shrink-0">
                    <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
                  </svg>
                  <span class="flex-1 text-[13px] font-semibold text-[#c0600a]">Activate</span>
                  <button
                    class="group rounded-full p-0.5 transition-opacity"
                    @click.stop="toggleInfo('activate')"
                    aria-label="説明"
                  >
                    <img src="/information.png" alt="info" class="h-[18px] w-[18px] opacity-50 transition-opacity group-hover:opacity-80" />
                  </button>
                </div>
                <div v-if="infoOpen === 'activate'" class="border-t border-[#f0c090] bg-[#fff8f0] px-4 pb-2.5 pt-2 text-[11px] leading-relaxed text-[#c0600a]/80">
                  {{ INFO.activate }}
                </div>
              </div>

              <!-- Deactivate (アクティベート済み) -->
              <div v-else>
                <div
                  class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-white/80"
                  @click="deactivate"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="shrink-0 text-muted">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 5 12 10 7"/><line x1="5" y1="12" x2="15" y2="12"/>
                  </svg>
                  <span class="flex-1 text-[13px] text-muted">Deactivate</span>
                  <button
                    class="group rounded-full p-0.5 transition-opacity"
                    @click.stop="toggleInfo('deactivate')"
                    aria-label="説明"
                  >
                    <img src="/information.png" alt="info" class="h-[18px] w-[18px] opacity-50 transition-opacity group-hover:opacity-80" />
                  </button>
                </div>
                <div v-if="infoOpen === 'deactivate'" class="border-t border-hairline-soft bg-white/40 px-4 pb-2.5 pt-2 text-[11px] leading-relaxed text-muted">
                  {{ INFO.deactivate }}
                </div>
              </div>
            </div>

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
