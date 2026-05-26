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
}

const STEP = 5
const DEFAULT_PER_PAGE = 10

/** Compute valid per-page options based on total (multiples of STEP, ≤ total) */
function computePerPageOptions(total: number): number[] {
  if (total < STEP) return []
  const max = Math.floor(total / STEP) * STEP
  const opts: number[] = []
  for (let i = STEP; i <= max; i += STEP) opts.push(i)
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
        const res = await api.get<ApiAudioListResponse>('/api/v1/audios', {
          query: {
            sort: this.sort,
            page: this.page,
            per_page: this.perPage,
          },
        })
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
  },
})
