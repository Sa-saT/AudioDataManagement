<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

definePageMeta({ layout: 'default' })
useHead({ title: 'Activate — Audio Data Management' })

const auth = useAuthStore()
const router = useRouter()

const fileInput = ref<HTMLInputElement | null>(null)
const errorMsg = ref<string | null>(null)
const fileName = ref<string | null>(null)

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
    await router.push('/dashboard')
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

const sampleLic = `{
  "username": "saaaaa",
  "role": "licensee",
  "licenseId": "LIC-2026-0001",
  "issuedAt": "2026-05-26T00:00:00Z"
}`
</script>

<template>
  <div class="mx-auto max-w-[640px]">
    <h1 class="text-[26px] font-normal tracking-[-0.0125em] text-ink">Activate</h1>
    <p class="mt-2 text-[14px] text-body">
      お手持ちの <span class="font-mono">.lic</span> ファイルを選択してアクティベートしてください。
      アクティベート後、ユーザ名が反映され、音源のダウンロードが可能になります。
    </p>

    <div class="card mt-6 p-6">
      <label
        class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-hairline-strong bg-canvas-soft px-6 py-10 text-center transition-colors hover:bg-canvas"
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="text-muted">
          <path d="M12 3v12" />
          <path d="m7 10 5 5 5-5" />
          <path d="M5 21h14" />
        </svg>
        <span class="text-[14px] text-ink">licファイルをクリックして選択</span>
        <span class="font-mono text-[11px] text-muted">{{ fileName ?? '*.lic' }}</span>
        <input
          ref="fileInput"
          type="file"
          accept=".lic,application/octet-stream,text/plain,application/json"
          class="hidden"
          @change="onPick"
        />
      </label>

      <p v-if="errorMsg" class="mt-3 text-[13px] text-error">{{ errorMsg }}</p>

      <div class="mt-6">
        <div class="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
          licファイルの例
        </div>
        <pre class="mt-2 rounded-md bg-canvas-soft p-4 font-mono text-[12px] text-ink overflow-x-auto">{{ sampleLic }}</pre>
      </div>

      <div v-if="auth.isActivated" class="mt-6 rounded-md border border-success/40 bg-success/5 p-4 text-[13px] text-ink">
        現在 <span class="font-medium">{{ auth.displayName }}</span> （{{ auth.role }}）でアクティベート済みです。
        <button class="ml-2 underline" @click="auth.deactivate()">解除する</button>
      </div>
    </div>
  </div>
</template>
