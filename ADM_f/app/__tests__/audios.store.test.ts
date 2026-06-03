import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { computePerPageOptions, useAudiosStore } from '~/stores/audios'

// ─── computePerPageOptions (純粋関数) ────────────────────────────────────────

describe('computePerPageOptions', () => {
  it('total < STEP (5) → 空配列', () => {
    expect(computePerPageOptions(0)).toEqual([])
    expect(computePerPageOptions(4)).toEqual([])
  })

  it('total が 5 の倍数 → その倍数の配列のみ', () => {
    expect(computePerPageOptions(5)).toEqual([5])
    expect(computePerPageOptions(10)).toEqual([5, 10])
    expect(computePerPageOptions(20)).toEqual([5, 10, 15, 20])
  })

  it('total が 5 の倍数でない → 倍数 + total を末尾に追加', () => {
    expect(computePerPageOptions(12)).toEqual([5, 10, 12])
    expect(computePerPageOptions(7)).toEqual([5, 7])
    expect(computePerPageOptions(23)).toEqual([5, 10, 15, 20, 23])
  })
})

// ─── store state mutations ────────────────────────────────────────────────────

describe('useAudiosStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('removeAudio', () => {
    it('対象 ID を items から削除し total を 1 減らす', () => {
      const store = useAudiosStore()
      store.items = [
        { id: 'aaa', title: 'A' } as never,
        { id: 'bbb', title: 'B' } as never,
      ]
      store.total = 2
      store.removeAudio('aaa')
      expect(store.items).toHaveLength(1)
      expect(store.items[0]!.id).toBe('bbb')
      expect(store.total).toBe(1)
    })

    it('存在しない ID → items 変化なし, total は 0 未満にならない', () => {
      const store = useAudiosStore()
      store.items = [{ id: 'aaa', title: 'A' } as never]
      store.total = 0
      store.removeAudio('zzz')
      expect(store.items).toHaveLength(1)
      expect(store.total).toBe(0)
    })
  })

  describe('updateAudio', () => {
    it('一致する ID の item を置き換える', () => {
      const store = useAudiosStore()
      store.items = [{ id: 'aaa', title: 'old' } as never]
      store.updateAudio({ id: 'aaa', title: 'new' } as never)
      expect(store.items[0]!.title).toBe('new')
    })

    it('一致しない ID → items 変化なし', () => {
      const store = useAudiosStore()
      store.items = [{ id: 'aaa', title: 'A' } as never]
      store.updateAudio({ id: 'zzz', title: 'Z' } as never)
      expect(store.items[0]!.title).toBe('A')
    })
  })

  describe('toggleTag', () => {
    it('未選択タグを追加する', () => {
      const store = useAudiosStore()
      store.toggleTag('piano')
      expect(store.activeTags).toContain('piano')
    })

    it('選択済みタグを削除する', () => {
      const store = useAudiosStore()
      store.activeTags = ['piano', 'guitar']
      store.toggleTag('piano')
      expect(store.activeTags).not.toContain('piano')
      expect(store.activeTags).toContain('guitar')
    })

    it('page を 1 にリセットする', () => {
      const store = useAudiosStore()
      store.page = 3
      store.toggleTag('drums')
      expect(store.page).toBe(1)
    })
  })

  describe('clearTags', () => {
    it('activeTags をクリアして page を 1 にする', () => {
      const store = useAudiosStore()
      store.activeTags = ['a', 'b']
      store.page = 5
      store.clearTags()
      expect(store.activeTags).toEqual([])
      expect(store.page).toBe(1)
    })

    it('空のときは何もしない (副作用なし)', () => {
      const store = useAudiosStore()
      store.page = 3
      store.clearTags()
      expect(store.page).toBe(3)
    })
  })

  describe('setSearch', () => {
    it('searchQuery を更新する', () => {
      const store = useAudiosStore()
      store.setSearch('piano')
      expect(store.searchQuery).toBe('piano')
    })
  })

  // ─── getters ──────────────────────────────────────────────────────────────

  describe('pageCount', () => {
    it('total / perPage の切り上げ', () => {
      const store = useAudiosStore()
      store.total = 23
      store.perPage = 10
      expect(store.pageCount).toBe(3)
    })

    it('total=0 → 1 ページ', () => {
      const store = useAudiosStore()
      store.total = 0
      expect(store.pageCount).toBe(1)
    })
  })

  describe('isEmpty', () => {
    it('loading=false, items=[], error=null → true', () => {
      const store = useAudiosStore()
      store.loading = false
      store.items = []
      store.error = null
      expect(store.isEmpty).toBe(true)
    })

    it('loading=true → false', () => {
      const store = useAudiosStore()
      store.loading = true
      expect(store.isEmpty).toBe(false)
    })

    it('items が存在する → false', () => {
      const store = useAudiosStore()
      store.items = [{ id: 'x' } as never]
      expect(store.isEmpty).toBe(false)
    })
  })

  describe('showPerPageStepper', () => {
    it('total >= 5 → true', () => {
      const store = useAudiosStore()
      store.total = 10
      expect(store.showPerPageStepper).toBe(true)
    })

    it('total < 5 → false', () => {
      const store = useAudiosStore()
      store.total = 3
      expect(store.showPerPageStepper).toBe(false)
    })
  })

  describe('sorted (searchQuery フィルタ)', () => {
    it('searchQuery 空 → items をそのまま返す', () => {
      const store = useAudiosStore()
      store.items = [
        { id: '1', title: 'Piano Ballad', creatorName: 'Alice', tags: [] } as never,
      ]
      store.searchQuery = ''
      expect(store.sorted).toHaveLength(1)
    })

    it('title に一致 → 絞り込み', () => {
      const store = useAudiosStore()
      store.items = [
        { id: '1', title: 'Piano Ballad', creatorName: 'Alice', tags: [] } as never,
        { id: '2', title: 'Drum Beat', creatorName: 'Bob', tags: [] } as never,
      ]
      store.searchQuery = 'piano'
      expect(store.sorted).toHaveLength(1)
      expect(store.sorted[0]!.id).toBe('1')
    })

    it('tag に一致 → 絞り込み', () => {
      const store = useAudiosStore()
      store.items = [
        { id: '1', title: 'A', creatorName: 'X', tags: ['ambient'] } as never,
        { id: '2', title: 'B', creatorName: 'Y', tags: ['rock'] } as never,
      ]
      store.searchQuery = 'ambient'
      expect(store.sorted.map((t) => t.id)).toEqual(['1'])
    })
  })
})
