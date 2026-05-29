import type { PeaksAny } from '~/components/waveform/peaks'

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
  /** v1: number[] (legacy) / v2: { n, max, min, rms } */
  peaks: PeaksAny
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
  /** v1 number[] (legacy) or v2 {max,min,rms} — shader handles both via toPeaksV2 */
  peaks: PeaksAny
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

/** Map API → frontend domain.
 * v2 peaks (max/min/rms) はそのまま透過。v1 (number[]) も透過し、
 * 描画側 (Shader) でガンマ補正 + RMS 帯処理を行う。
 * 旧 spreadPeaks クライアント補正は不要になったため廃止。 */
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
    tags: api.tags ?? [],
    isPublic: api.is_public,
    description: api.description,
    favoriteCount: api.favorite_count ?? 0,
    isFavorited: api.is_favorited ?? false,
  }
}
