/**
 * vitest グローバルセットアップ。
 * Nuxt 自動インポートのコンポーザブルを最小スタブで差し替える。
 */
import { vi } from 'vitest'

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://localhost:8000' },
}))

vi.stubGlobal('$fetch', vi.fn())

vi.stubGlobal('useCookie', (_key: string) => ({ value: null }))

vi.stubGlobal('useApi', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}))
