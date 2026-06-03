import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '~/stores/auth'

const STORAGE_KEY = 'pathfinder.auth'

function makeStoredAuth(overrides: object = {}) {
  return {
    token: 'test-jwt-token',
    expiresAt: new Date(Date.now() + 86_400_000).toISOString(), // 1日後
    user: {
      id: 'uid-001',
      username: 'testuser',
      role: 'licensee',
      licenseCode: 'LIC-001',
      monthlyQuotaTokens: 3600,
    },
    ...overrides,
  }
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  // ─── 初期状態 ──────────────────────────────────────────────────────────────

  describe('初期状態', () => {
    it('token / user / tokensUsed は null / 0', () => {
      const store = useAuthStore()
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.tokensUsed).toBe(0)
    })
  })

  // ─── hydrate ───────────────────────────────────────────────────────────────

  describe('hydrate', () => {
    it('localStorage に有効なデータがあればロードする', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStoredAuth()))
      const store = useAuthStore()
      store.hydrate()
      expect(store.token).toBe('test-jwt-token')
      expect(store.user?.username).toBe('testuser')
    })

    it('有効期限切れトークンは破棄する', () => {
      const expired = makeStoredAuth({ expiresAt: new Date(Date.now() - 1000).toISOString() })
      localStorage.setItem(STORAGE_KEY, JSON.stringify(expired))
      const store = useAuthStore()
      store.hydrate()
      expect(store.token).toBeNull()
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    })

    it('不正な JSON は無視して localStorage を削除する', () => {
      localStorage.setItem(STORAGE_KEY, 'not-json{{{')
      const store = useAuthStore()
      store.hydrate()
      expect(store.token).toBeNull()
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    })

    it('localStorage が空なら状態は変わらない', () => {
      const store = useAuthStore()
      store.hydrate()
      expect(store.token).toBeNull()
    })
  })

  // ─── deactivate ────────────────────────────────────────────────────────────

  describe('deactivate', () => {
    it('token / user / tokensUsed を初期化する', () => {
      const store = useAuthStore()
      store.token = 'some-token'
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 100 }
      store.tokensUsed = 50
      store.deactivate()
      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
      expect(store.tokensUsed).toBe(0)
    })

    it('localStorage のエントリを削除する', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStoredAuth()))
      const store = useAuthStore()
      store.deactivate()
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    })
  })

  // ─── invalidateSession ────────────────────────────────────────────────────

  describe('invalidateSession', () => {
    it('deactivate してメッセージをセットする', () => {
      const store = useAuthStore()
      store.token = 'tok'
      store.invalidateSession('別端末でログアウトされました')
      expect(store.token).toBeNull()
      expect(store.sessionInvalidatedMessage).toBe('別端末でログアウトされました')
    })

    it('clearSessionInvalidatedMessage でメッセージを消す', () => {
      const store = useAuthStore()
      store.invalidateSession('msg')
      store.clearSessionInvalidatedMessage()
      expect(store.sessionInvalidatedMessage).toBeNull()
    })
  })

  // ─── applyRemainingTokens ─────────────────────────────────────────────────

  describe('applyRemainingTokens', () => {
    it('tokensUsed = monthlyQuota - remaining', () => {
      const store = useAuthStore()
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 3600 }
      store.applyRemainingTokens(2600)
      expect(store.tokensUsed).toBe(1000)
    })

    it('remaining > quota でも 0 未満にならない', () => {
      const store = useAuthStore()
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 100 }
      store.applyRemainingTokens(9999)
      expect(store.tokensUsed).toBe(0)
    })
  })

  // ─── getters ──────────────────────────────────────────────────────────────

  describe('getters', () => {
    it('isActivated: token と user が両方ある → true', () => {
      const store = useAuthStore()
      store.token = 'tok'
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 0 }
      expect(store.isActivated).toBe(true)
    })

    it('isActivated: token のみ → false', () => {
      const store = useAuthStore()
      store.token = 'tok'
      expect(store.isActivated).toBe(false)
    })

    it('role: user がいない → guest', () => {
      expect(useAuthStore().role).toBe('guest')
    })

    it('role: user が creator → creator', () => {
      const store = useAuthStore()
      store.user = { id: 'x', username: 'x', role: 'creator', licenseCode: 'L', monthlyQuotaTokens: 0 }
      expect(store.role).toBe('creator')
    })

    it('tokensRemaining: quota - used (0 未満にならない)', () => {
      const store = useAuthStore()
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 1000 }
      store.tokensUsed = 300
      expect(store.tokensRemaining).toBe(700)
    })

    it('tokensRemaining: tokensUsed > quota → 0', () => {
      const store = useAuthStore()
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 100 }
      store.tokensUsed = 200
      expect(store.tokensRemaining).toBe(0)
    })

    it('canDownload: isActivated と同義', () => {
      const store = useAuthStore()
      expect(store.canDownload).toBe(false)
      store.token = 'tok'
      store.user = { id: 'x', username: 'x', role: 'licensee', licenseCode: 'L', monthlyQuotaTokens: 0 }
      expect(store.canDownload).toBe(true)
    })
  })
})
