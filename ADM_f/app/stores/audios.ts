import { defineStore } from 'pinia'
import type {
  AudioTrack,
  ApiAudioListResponse,
  SortKey,
} from '~/types/audio'
import { mapApiAudio } from '~/types/audio'

type PerPage = 5 | 10 | 15 | 20 | 25 | 30 | 35 | 40

interface AudiosState {
  items: AudioTrack[]
  total: number
  loading: boolean
  error: string | null
  sort: SortKey
  perPage: PerPage
  page: number
  searchQuery: string
}

const PER_PAGE_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40] as const

export const useAudiosStore = defineStore('audios', {
  state: (): AudiosState => ({
    items: [],
    total: 0,
    loading: false,
    error: null,
    sort: 'recommended',
    perPage: 10,
    page: 1,
    searchQuery: '',
  }),
  getters: {
    /**
     * Client-side filtering applied on the server-fetched batch (for now).
     * When backend gains a server-side search param, switch to that.
     */
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
    /** Used by Dashboard to render either skeleton or empty state */
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
      const idx = PER_PAGE_OPTIONS.indexOf(this.perPage)
      const next = PER_PAGE_OPTIONS[Math.max(0, Math.min(PER_PAGE_OPTIONS.length - 1, idx + dir))]
      if (next && next !== this.perPage) {
        this.perPage = next
        this.page = 1
        this.fetch()
      }
    },
    setPerPage(n: PerPage) {
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
