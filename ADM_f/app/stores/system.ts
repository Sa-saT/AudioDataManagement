import { defineStore } from 'pinia'

interface SystemState {
  commissionEnabled: boolean
  commissionUnreadCount: number
  loaded: boolean
}

export const useSystemStore = defineStore('system', {
  state: (): SystemState => ({
    commissionEnabled: false,
    commissionUnreadCount: 0,
    loaded: false,
  }),
  actions: {
    async fetchCommissionStatus() {
      if (this.loaded) return
      try {
        const config = useRuntimeConfig()
        const data = await $fetch<{ enabled: boolean }>('/api/v1/system/commission', {
          baseURL: config.public.apiBaseUrl as string,
        })
        this.commissionEnabled = data.enabled
      } catch {
        this.commissionEnabled = false
      } finally {
        this.loaded = true
      }
    },

    async fetchCommissionUnread() {
      try {
        const config = useRuntimeConfig()
        const token = useCookie('adm_token').value
        if (!token) { this.commissionUnreadCount = 0; return }
        const data = await $fetch<{ count: number }>('/api/v1/me/commission/unread', {
          baseURL: config.public.apiBaseUrl as string,
          headers: { Authorization: `Bearer ${token}` },
        })
        this.commissionUnreadCount = data.count
      } catch {
        this.commissionUnreadCount = 0
      }
    },

    clearCommissionUnread() {
      this.commissionUnreadCount = 0
    },
  },
})
