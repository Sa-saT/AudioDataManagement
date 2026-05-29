import { defineStore } from 'pinia'

interface UnreadBreakdown {
  action_required: number
  message_unread: number
  info_only: number
}

interface SystemState {
  commissionEnabled: boolean
  // 改訂2: 要対応カウント (status ベース + メッセージ未読の合算)
  commissionActionCount: number
  // 改訂2: 情報通知の有無 (件数バッジは出さず色変化のみ)
  commissionHasInfo: boolean
  commissionBreakdown: UnreadBreakdown
  loaded: boolean
}

export const useSystemStore = defineStore('system', {
  state: (): SystemState => ({
    commissionEnabled: false,
    commissionActionCount: 0,
    commissionHasInfo: false,
    commissionBreakdown: { action_required: 0, message_unread: 0, info_only: 0 },
    loaded: false,
  }),
  getters: {
    // 後方互換: 旧フィールド名を要対応カウントへエイリアス
    commissionUnreadCount(): number {
      return this.commissionActionCount
    },
  },
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
        if (!token) {
          this.commissionActionCount = 0
          this.commissionHasInfo = false
          this.commissionBreakdown = { action_required: 0, message_unread: 0, info_only: 0 }
          return
        }
        const data = await $fetch<{
          action_count: number
          has_info: boolean
          breakdown: UnreadBreakdown
        }>('/api/v1/me/commission/unread', {
          baseURL: config.public.apiBaseUrl as string,
          headers: { Authorization: `Bearer ${token}` },
        })
        this.commissionActionCount = data.action_count
        this.commissionHasInfo = data.has_info
        this.commissionBreakdown = data.breakdown
      } catch {
        this.commissionActionCount = 0
        this.commissionHasInfo = false
        this.commissionBreakdown = { action_required: 0, message_unread: 0, info_only: 0 }
      }
    },

    async sessionPing() {
      try {
        const config = useRuntimeConfig()
        const token = useCookie('adm_token').value
        if (!token) return
        await $fetch('/api/v1/me/session/ping', {
          method: 'POST',
          baseURL: config.public.apiBaseUrl as string,
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch { /* silent */ }
    },

    clearCommissionUnread() {
      this.commissionActionCount = 0
      this.commissionHasInfo = false
      this.commissionBreakdown = { action_required: 0, message_unread: 0, info_only: 0 }
    },
  },
})
