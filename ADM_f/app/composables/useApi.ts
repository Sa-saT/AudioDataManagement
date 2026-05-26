/**
 * Pathfinder API client wrapper.
 * - Injects baseURL from runtimeConfig.public.apiBaseUrl
 * - Injects Authorization: Bearer <jwt> if auth store has token
 * - On 401, deactivates auth and surfaces the error
 */
import { useAuthStore } from '~/stores/auth'

export interface ApiErrorBody {
  code?: string
  message?: string
  detail?: { code?: string; message?: string } | string
}

export class ApiError extends Error {
  code: string
  status: number
  body?: ApiErrorBody
  constructor(message: string, status: number, code: string, body?: ApiErrorBody) {
    super(message)
    this.status = status
    this.code = code
    this.body = body
  }
}

interface ApiRequestOpts {
  body?: unknown
  query?: Record<string, unknown>
  headers?: Record<string, string>
}

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

function extractError(err: unknown): { code: string; message: string; body?: ApiErrorBody } {
  const e = err as { status?: number; response?: { _data?: ApiErrorBody }; data?: ApiErrorBody; message?: string }
  const body = e.response?._data ?? e.data
  const detail = body?.detail
  const code =
    (typeof detail === 'object' && detail?.code) ||
    body?.code ||
    'UNKNOWN_ERROR'
  const message =
    (typeof detail === 'object' && detail?.message) ||
    (typeof detail === 'string' ? detail : undefined) ||
    body?.message ||
    e.message ||
    'リクエストに失敗しました'
  return { code, message, body }
}

export function useApi() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const baseURL = config.public.apiBaseUrl as string

  async function request<T>(path: string, method: Method, opts: ApiRequestOpts = {}): Promise<T> {
    const headers: Record<string, string> = { ...(opts.headers || {}) }
    if (auth.token && !headers.Authorization) {
      headers.Authorization = `Bearer ${auth.token}`
    }
    try {
      return await $fetch<T>(path, {
        baseURL,
        method,
        body: opts.body as never,
        query: opts.query,
        headers,
      })
    } catch (err) {
      const e = err as { status?: number }
      if (e.status === 401) auth.deactivate()
      const { code, message, body } = extractError(err)
      throw new ApiError(message, e.status ?? 0, code, body)
    }
  }

  return {
    get: <T>(path: string, opts?: ApiRequestOpts) => request<T>(path, 'GET', opts),
    post: <T>(path: string, opts?: ApiRequestOpts) => request<T>(path, 'POST', opts),
    delete: <T>(path: string, opts?: ApiRequestOpts) => request<T>(path, 'DELETE', opts),
  }
}
