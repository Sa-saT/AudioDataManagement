import type { AudioTrack } from '~/types/audio'

const titles = [
  'ロック感ある王道的フュージョン',
  'キュートなテクノポップフュージョン',
  'トリッキーなキメのフュージョン',
  '生フルート爽やかな南国風フュージョン',
  '激しくも優しさのあるフュージョン',
  'スポーツフュージョン',
  'スタイリッシュなギターのフュージョン',
  'エレキギターのフュージョン・ジングル',
  '夜風に乗せるシティ・フュージョン',
  '疾走感あふれるドライブフュージョン',
]

const tagSets: string[][] = [
  ['rock', 'fusion', 'energetic'],
  ['cute', 'techno', 'pop'],
  ['tricky', 'syncopated', 'jazz'],
  ['flute', 'tropical', 'organic'],
  ['intense', 'emotional', 'cinematic'],
  ['sports', 'upbeat', 'driving'],
  ['guitar', 'stylish', 'lo-fi'],
  ['electric', 'jingle', 'short'],
  ['city', 'night', 'ambient'],
  ['drive', 'fast', 'electronic'],
]

const creators = [
  'モくろろ',
  'Sapphire',
  'Garin',
  'arachang',
  'ナカガワ',
  'WHITE BEAM',
  'Lumière',
]

function seededRandom(seed: number) {
  let s = seed
  return () => {
    s = (s * 9301 + 49297) % 233280
    return s / 233280
  }
}

function generatePeaks(seed: number, length = 256): number[] {
  const rng = seededRandom(seed)
  const out: number[] = []
  // Envelope: build a couple of swells across the track for realism
  for (let i = 0; i < length; i++) {
    const t = i / length
    const envelope = 0.35 + 0.55 * Math.sin(Math.PI * t) + 0.15 * Math.sin(6 * Math.PI * t)
    const noise = rng() * 0.6 + 0.2
    out.push(Math.min(1, Math.max(0.05, envelope * noise)))
  }
  return out
}

export function buildMockTracks(): AudioTrack[] {
  const baseDate = new Date('2026-05-20T00:00:00Z').getTime()
  return titles.map((title, i) => {
    const durationSec = [354, 254, 317, 180, 337, 201, 191, 10, 240, 195][i] ?? 200
    return {
      id: `trk_${(i + 1).toString().padStart(4, '0')}`,
      title,
      creatorName: creators[i % creators.length] as string,
      creatorId: `crt_${(i % creators.length) + 1}`,
      durationSec,
      price: [2420, 2420, 2420, 1290, 2420, 2420, 3630, 1290, 2200, 1980][i] ?? 1980,
      publishedAt: new Date(baseDate - i * 86400_000).toISOString(),
      recommendScore: Math.round(100 - i * 3.5),
      peaks: generatePeaks(i + 1),
      youtubeSafe: i % 3 !== 1,
      similarWorks: 100 + i * 7,
      tags: tagSets[i] ?? [],
      favoriteCount: [24, 7, 52, 3, 18, 11, 39, 2, 15, 6][i] ?? 0,
    }
  })
}
