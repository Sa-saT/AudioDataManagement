import { defineStore } from 'pinia'
import type {
  AudioTrack,
  ApiAudioListResponse,
  SortKey,
} from '~/types/audio'
import { mapApiAudio } from '~/types/audio'

interface AudiosState {
  items: AudioTrack[]
  total: number
  loading: boolean
  error: string | null
  sort: SortKey
  perPage: number
  page: number
  searchQuery: string
  mineOnly: boolean
}

const STEP = 5
const DEFAULT_PER_PAGE = 10

/**
 * Per-page options:
 *   - total < STEP: 空配列 (静的に [total] を表示)
 *   - total >= STEP: 5刻み + 最終に total 自体を追加 (5倍数でない場合)
 *     例: total=12 → [5, 10, 12]  /  total=80 → [5,10,...,80]
 */
function computePerPageOptions(total: number): number[] {
  if (total < STEP) return []
  const opts: number[] = []
  const maxMultiple = Math.floor(total / STEP) * STEP
  for (let i = STEP; i <= maxMultiple; i += STEP) opts.push(i)
  if (maxMultiple < total) opts.push(total)
  return opts
}

export const useAudiosStore = defineStore('audios', {
  state: (): AudiosState => ({
    items: [],
    total: 0,
    loading: false,
    error: null,
    sort: 'recommended',
    perPage: DEFAULT_PER_PAGE,
    page: 1,
    searchQuery: '',
    mineOnly: false,
  }),
  getters: {
    sorted(state): AudioTrack[] {
      const q = state.searchQuery.trim().toLowerCase()
      if (!q) return state.items
      return state.items.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.creatorName.toLowerCase().includes(q) ||
          t.tags?.some((tag) => tag.toLowerCase().includes(q)),
      )
    },
    totalCount: (s): number => s.total,
    pageCount(): number {
      return Math.max(1, Math.ceil(this.total / this.perPage))
    },
    paged(): AudioTrack[] {
      return this.sorted
    },
    /** Valid per-page options for the stepper (dynamic from total) */
    perPageOptions(): number[] {
      return computePerPageOptions(this.total)
    },
    /** When total < STEP, show static "全N件" instead of stepper */
    showPerPageStepper(): boolean {
      return this.perPageOptions.length > 0
    },
    isEmpty(): boolean {
      return !this.loading && this.items.length === 0 && !this.error
    },
  },
  actions: {
    async fetch() {
      this.loading = true
      this.error = null
      try {
        const api = useApi()
        const query: Record<string, unknown> = {
          sort: this.sort,
          page: this.page,
          per_page: this.perPage,
        }
        if (this.mineOnly) query.mine = true
        const res = await api.get<ApiAudioListResponse>('/api/v1/audios', { query })
        this.items = res.items.map(mapApiAudio)
        this.total = res.total
        // Clamp perPage to valid options after total is known
        const opts = computePerPageOptions(this.total)
        if (opts.length > 0 && !opts.includes(this.perPage)) {
          const max = opts[opts.length - 1] ?? STEP
          this.perPage = this.perPage > max ? max : (opts[0] ?? STEP)
        }
      } catch (err: unknown) {
        const e = err as { message?: string; code?: string }
        this.error = e?.message ?? 'API への接続に失敗しました'
        this.items = []
        this.total = 0
      } finally {
        this.loading = false
      }
    },
    setSort(s: SortKey) {
      this.sort = s
      this.page = 1
      this.fetch()
    },
    stepPerPage(dir: 1 | -1) {
      const opts = this.perPageOptions
      if (opts.length === 0) return
      const idx = opts.indexOf(this.perPage)
      const next = opts[Math.max(0, Math.min(opts.length - 1, idx + dir))]
      if (next != null && next !== this.perPage) {
        this.perPage = next
        this.page = 1
        this.fetch()
      }
    },
    setPerPage(n: number) {
      if (n === this.perPage) return
      this.perPage = n
      this.page = 1
      this.fetch()
    },
    setPage(p: number) {
      const next = Math.min(Math.max(1, p), this.pageCount)
      if (next === this.page) return
      this.page = next
      this.fetch()
    },
    setSearch(q: string) {
      this.searchQuery = q
    },
    setMine(enabled: boolean) {
      if (this.mineOnly === enabled) return
      this.mineOnly = enabled
      this.searchQuery = ''
      this.page = 1
      this.fetch()
    },
    /** DL 成立により一覧から取り除く (単発販売: 売切れ) */
    removeAudio(audioId: string) {
      this.items = this.items.filter((t) => t.id !== audioId)
      if (this.total > 0) this.total -= 1
    },
    updateAudio(updated: AudioTrack) {
      const idx = this.items.findIndex((t) => t.id === updated.id)
      if (idx !== -1) this.items[idx] = updated
    },
  },
})
