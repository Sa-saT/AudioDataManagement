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
  tags?: string[]
  is_public?: boolean
  description?: string | null
  favorite_count?: number
  is_favorited?: boolean
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
  /** Image/mood tags selected by creator at upload */
  tags?: string[]
  isPublic?: boolean
  description?: string | null
  /** Number of users who favorited */
  favoriteCount?: number
  /** Whether the current user has favorited this audio */
  isFavorited?: boolean
  /** For client-side fallback sort */
  recommendScore?: number
}

export type SortKey = 'recommended' | 'newest'

/** POST /audios/{id}/download response */
export interface DownloadApiResponse {
  download_url: string
  is_redownload: boolean
  token_cost: number | null
  remaining_tokens: number | null
}

/**
 * Backend は peaks を「ファイル全体の max で正規化済み」で返すが、
 * 大半が大音量の曲だと値が 0.99 近辺に密集して波形が "ベタ塗り" に見える。
 * クライアント側で min-max を 0..1 に拡げて視覚的コントラストを確保する。
 */
function spreadPeaks(peaks: number[]): number[] {
  if (peaks.length === 0) return peaks
  let min = Infinity
  let max = -Infinity
  for (const p of peaks) {
    if (p < min) min = p
    if (p > max) max = p
  }
  const range = max - min
  if (range < 1e-6) return peaks.map(() => 0.5)
  return peaks.map((p) => (p - min) / range)
}

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
    peaks: spreadPeaks(api.peaks),
    youtubeSafe: api.youtube_safe,
    publishedAt: api.published_at,
    tags: api.tags ?? [],
    isPublic: api.is_public,
    description: api.description,
    favoriteCount: api.favorite_count ?? 0,
    isFavorited: api.is_favorited ?? false,
  }
}
