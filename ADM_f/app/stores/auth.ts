import { defineStore } from 'pinia'
import type { ActivateApiResponse, AuthUser, Role } from '~/types/auth'

interface AuthState {
  token: string | null
  expiresAt: string | null
  user: AuthUser | null
}

const STORAGE_KEY = 'pathfinder.auth'

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: null,
    expiresAt: null,
    user: null,
  }),
  getters: {
    isActivated: (s) => s.token !== null && s.user !== null,
    role: (s): Role => s.user?.role ?? 'guest',
    displayName: (s) => s.user?.username ?? 'guest',
    canDownload(): boolean {
      return this.isActivated
    },
  },
  actions: {
    /**
     * Activate by uploading a .lic file to backend /api/v1/auth/activate.
     * The server verifies the signature, then returns JWT + user info.
     */
    async activateFromFile(file: File): Promise<void> {
      const config = useRuntimeConfig()
      const form = new FormData()
      form.append('file', file)

      const data = await $fetch<ActivateApiResponse>('/api/v1/auth/activate', {
        baseURL: config.public.apiBaseUrl as string,
        method: 'POST',
        body: form,
      })

      this.token = data.access_token
      this.expiresAt = data.expires_at
      this.user = {
        id: data.user.id,
        username: data.user.username,
        role: data.user.role,
        licenseCode: data.user.license_code,
        monthlyQuotaTokens: data.user.monthly_quota_tokens,
      }

      if (import.meta.client) {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            token: this.token,
            expiresAt: this.expiresAt,
            user: this.user,
          }),
        )
      }
    },

    deactivate() {
      this.token = null
      this.expiresAt = null
      this.user = null
      if (import.meta.client) localStorage.removeItem(STORAGE_KEY)
    },

    hydrate() {
      if (!import.meta.client) return
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      try {
        const parsed = JSON.parse(raw) as AuthState
        // Expiry check
        if (parsed.expiresAt && Date.parse(parsed.expiresAt) <= Date.now()) {
          localStorage.removeItem(STORAGE_KEY)
          return
        }
        this.token = parsed.token
        this.expiresAt = parsed.expiresAt
        this.user = parsed.user
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    },
  },
})
