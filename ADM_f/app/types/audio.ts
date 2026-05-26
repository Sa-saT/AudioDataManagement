export interface AudioTrack {
  id: string
  title: string
  creatorName: string
  creatorId: string
  durationSec: number
  price: number
  publishedAt: string
  recommendScore: number
  /** Pseudo waveform data: normalized 0..1 samples for visual display */
  peaks: number[]
  /** Optional real source URL (.wav). When omitted, only the pseudo waveform renders. */
  src?: string
  youtubeSafe?: boolean
  similarWorks?: number
}

export type SortKey = 'recommended' | 'newest'
