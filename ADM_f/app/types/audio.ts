export interface CreatorBrief {
  id: string
  displayName: string
}

/** API response item (snake_case) — internal use only */
export interface ApiAudioListItem {
  id: string
  title: string
  creator: { id: string; display_name: string }
  duration_sec: number
  token_cost: number
  peaks: number[]
  youtube_safe: boolean
  published_at: string | null
}

export interface ApiAudioListResponse {
  total: number
  page: number
  per_page: number
  items: ApiAudioListItem[]
}

/** Frontend domain model (camelCase) */
export interface AudioTrack {
  id: string
  title: string
  creator: CreatorBrief
  /** Backward-compat flat fields for legacy components */
  creatorId: string
  creatorName: string
  durationSec: number
  /** = duration_sec, but exposed as user-visible cost */
  tokenCost: number
  peaks: number[]
  youtubeSafe: boolean
  publishedAt: string | null
  /** Optional real source URL (.wav). When omitted, only waveform renders. */
  src?: string
  /** Image/mood tags selected by creator at upload (Phase 3 backend extension) */
  tags?: string[]
  /** Number of users who favorited (Phase 3 backend extension) */
  favoriteCount?: number
  /** For client-side fallback sort */
  recommendScore?: number
}

export type SortKey = 'recommended' | 'newest'

/** Map API → frontend domain */
export function mapApiAudio(api: ApiAudioListItem): AudioTrack {
  return {
    id: api.id,
    title: api.title,
    creator: { id: api.creator.id, displayName: api.creator.display_name },
    creatorId: api.creator.id,
    creatorName: api.creator.display_name,
    durationSec: api.duration_sec,
    tokenCost: api.token_cost,
    peaks: api.peaks,
    youtubeSafe: api.youtube_safe,
    publishedAt: api.published_at,
    tags: [],
    favoriteCount: 0,
  }
}
