import { defineStore } from 'pinia'

interface SystemState {
  commissionEnabled: boolean
  loaded: boolean
}

export const useSystemStore = defineStore('system', {
  state: (): SystemState => ({
    commissionEnabled: false,
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
  },
})
