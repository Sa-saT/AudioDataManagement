import { defineStore } from 'pinia'
import type { AudioTrack, SortKey } from '~/types/audio'
import { buildMockTracks } from '~/utils/mockTracks'

interface AudiosState {
  all: AudioTrack[]
  sort: SortKey
  perPage: 25 | 50 | 100 | 200
  page: number
}

export const useAudiosStore = defineStore('audios', {
  state: (): AudiosState => ({
    all: buildMockTracks(),
    sort: 'recommended',
    perPage: 50,
    page: 1,
  }),
  getters: {
    sorted(state): AudioTrack[] {
      const list = [...state.all]
      if (state.sort === 'newest') {
        list.sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
      } else {
        list.sort((a, b) => b.recommendScore - a.recommendScore)
      }
      return list
    },
    totalCount(): number {
      return this.all.length
    },
    pageCount(): number {
      return Math.max(1, Math.ceil(this.all.length / this.perPage))
    },
    paged(): AudioTrack[] {
      const start = (this.page - 1) * this.perPage
      return this.sorted.slice(start, start + this.perPage)
    },
  },
  actions: {
    setSort(s: SortKey) {
      this.sort = s
      this.page = 1
    },
    setPerPage(n: AudiosState['perPage']) {
      this.perPage = n
      this.page = 1
    },
    setPage(p: number) {
      this.page = Math.min(Math.max(1, p), this.pageCount)
    },
  },
})
