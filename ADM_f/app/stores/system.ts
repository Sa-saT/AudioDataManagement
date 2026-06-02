import { defineStore } from 'pinia'

interface UnreadBreakdown {
  action_required: number
  message_unread: number
  info_only: number
}

// NOTIFICATION_SPEC §5: 領域別の通知サマリ
export interface AreaNotification {
  action_count: number
  has_info: boolean
  breakdown: Record<string, number>
}

interface NotificationsResponse {
  areas: Record<string, AreaNotification>
  totals: { action_count: number; has_info: boolean }
}

interface SystemState {
  commissionEnabled: boolean
  // 改訂2: 要対応カウント (status ベース + メッセージ未読の合算)
  commissionActionCount: number
  // 改訂2: 情報通知の有無 (件数バッジは出さず色変化のみ)
  commissionHasInfo: boolean
  commissionBreakdown: UnreadBreakdown
  // NOTIFICATION_SPEC §5: 領域非依存の通知マップ
  areas: Record<string, AreaNotification>
  totals: { action_count: number; has_info: boolean }
  loaded: boolean
  // admin が設定する公開設定
  imageTagPresets: string[]
  commissionItemVisibility: Record<string, boolean>
  adminConfigLoaded: boolean
}

const EMPTY_AREA: AreaNotification = {
  action_count: 0,
  has_info: false,
  breakdown: {},
}

export const useSystemStore = defineStore('system', {
  state: (): SystemState => ({
    commissionEnabled: false,
    commissionActionCount: 0,
    commissionHasInfo: false,
    commissionBreakdown: { action_required: 0, message_unread: 0, info_only: 0 },
    areas: {},
    totals: { action_count: 0, has_info: false },
    loaded: false,
    imageTagPresets: [],
    commissionItemVisibility: {},
    adminConfigLoaded: false,
  }),
  getters: {
    // 後方互換: 旧フィールド名を要対応カウントへエイリアス
    commissionUnreadCount(): number {
      return this.commissionActionCount
    },
    // NOTIFICATION_SPEC §3.2: admin Level 2 = admin 専用領域の合算
    // R2.4: admin の Commission 通知も合算 (TopNav の Commission line 撤去のため)
    adminAreasActionCount(): number {
      const admin = ['commission', 'payouts', 'creator_dm', 'token_grants', 'lic_requests']
      return admin.reduce((sum, key) => sum + (this.areas[key]?.action_count ?? 0), 0)
    },
    adminAreasHasInfo(): boolean {
      const admin = ['commission', 'payouts', 'creator_dm', 'token_grants', 'lic_requests']
      return admin.some(key => this.areas[key]?.has_info ?? false)
    },
    areaFor(): (name: string) => AreaNotification {
      return (name: string) => this.areas[name] ?? EMPTY_AREA
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
      // NOTIFICATION_SPEC §5.3: 統合エンドポイントに移行。Commission 単体フィールドは
      // 後方互換のため areas.commission からミラーする。
      try {
        const config = useRuntimeConfig()
        const token = useCookie('adm_token').value
        if (!token) {
          this._resetNotifications()
          return
        }
        const data = await $fetch<NotificationsResponse>('/api/v1/me/notifications', {
          baseURL: config.public.apiBaseUrl as string,
          headers: { Authorization: `Bearer ${token}` },
        })
        this.areas = data.areas
        this.totals = data.totals
        const commission = data.areas.commission ?? EMPTY_AREA
        this.commissionActionCount = commission.action_count
        this.commissionHasInfo = commission.has_info
        this.commissionBreakdown = {
          action_required: commission.breakdown.action_required ?? 0,
          message_unread: commission.breakdown.message_unread ?? 0,
          info_only: commission.breakdown.info_only ?? 0,
        }
      } catch {
        this._resetNotifications()
      }
    },

    _resetNotifications() {
      this.areas = {}
      this.totals = { action_count: 0, has_info: false }
      this.commissionActionCount = 0
      this.commissionHasInfo = false
      this.commissionBreakdown = { action_required: 0, message_unread: 0, info_only: 0 }
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
      this._resetNotifications()
    },

    // admin 設定の公開項目を取得 (一度だけ)
    async fetchAdminConfig() {
      if (this.adminConfigLoaded) return
      try {
        const config = useRuntimeConfig()
        const baseURL = config.public.apiBaseUrl as string
        const [tags, comm] = await Promise.all([
          $fetch<{ tags: string[] }>('/api/v1/system/image-tags', { baseURL }),
          $fetch<{ item_visibility: Record<string, boolean> }>('/api/v1/system/commission-config', { baseURL }),
        ])
        this.imageTagPresets = tags.tags ?? []
        this.commissionItemVisibility = comm.item_visibility ?? {}
      } catch {
        // 取得失敗時はフォールバック値で空のまま
      } finally {
        this.adminConfigLoaded = true
      }
    },

    // admin が更新後にキャッシュを破棄して再取得させる
    invalidateAdminConfig() {
      this.adminConfigLoaded = false
    },
  },
})
