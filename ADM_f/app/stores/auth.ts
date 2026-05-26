import { defineStore } from 'pinia'
import type { LicensePayload, Role } from '~/types/auth'

interface AuthState {
  license: LicensePayload | null
}

const STORAGE_KEY = 'adm.license'

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    license: null,
  }),
  getters: {
    isActivated: (s) => s.license !== null,
    role: (s): Role => s.license?.role ?? 'guest',
    displayName: (s) => s.license?.username ?? 'guest',
    canDownload(): boolean {
      return this.isActivated
    },
  },
  actions: {
    /**
     * Parse a .lic file payload.
     * Accepted formats:
     *   - JSON  → {"username":"...", "role":"user|creator", "licenseId":"...", "issuedAt":"..."}
     *   - KV    → username=foo\nrole=user\nlicenseId=xxx
     */
    activateFromText(text: string): LicensePayload {
      let parsed: Partial<LicensePayload> = {}
      const trimmed = text.trim()
      if (trimmed.startsWith('{')) {
        parsed = JSON.parse(trimmed)
      } else {
        for (const line of trimmed.split(/\r?\n/)) {
          const [k, ...rest] = line.split('=')
          if (!k || rest.length === 0) continue
          ;(parsed as Record<string, string>)[k.trim()] = rest.join('=').trim()
        }
      }

      if (!parsed.username || !parsed.role || !parsed.licenseId) {
        throw new Error('licファイルの形式が不正です (username/role/licenseId が必要)')
      }
      if (parsed.role !== 'user' && parsed.role !== 'creator' && parsed.role !== 'admin') {
        throw new Error(`role は user / creator / admin のいずれかです (取得値: ${parsed.role})`)
      }

      const license: LicensePayload = {
        username: parsed.username,
        role: parsed.role,
        licenseId: parsed.licenseId,
        issuedAt: parsed.issuedAt ?? new Date().toISOString(),
        expiresAt: parsed.expiresAt,
      }
      this.license = license
      if (import.meta.client) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(license))
      }
      return license
    },
    deactivate() {
      this.license = null
      if (import.meta.client) localStorage.removeItem(STORAGE_KEY)
    },
    hydrate() {
      if (!import.meta.client) return
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      try {
        this.license = JSON.parse(raw) as LicensePayload
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    },
  },
})
