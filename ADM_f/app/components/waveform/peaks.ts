// peaks v1 (number[]) を v2 ({n, max, min, rms}) に変換する互換ラッパー。
// migration 完了前後の双方で破綻しない。

export interface PeaksV2 {
  n: number
  max: number[]
  min: number[]
  rms: number[]
}

export type PeaksAny = number[] | PeaksV2

export function isPeaksV2(p: PeaksAny): p is PeaksV2 {
  return !Array.isArray(p) && typeof p === 'object' && Array.isArray((p as PeaksV2).max)
}

/**
 * v1 (単一ピーク配列) を v2 形式へ変換。
 * v2 は素通し。v1 は max にコピー、min は対称、rms は値の半分で代用 (近似)。
 */
export function toPeaksV2(p: PeaksAny): PeaksV2 {
  if (isPeaksV2(p)) return p
  const arr = p as number[]
  return {
    n: arr.length,
    max: arr,
    min: arr.map(v => -v),
    rms: arr.map(v => v * 0.5),
  }
}

/**
 * peaks v2 を RGB UNSIGNED_BYTE 列にパック (R=max, G=|min|, B=rms)。
 * シェーダー側で G を負に戻す。
 */
export function packPeaksRGB(peaks: PeaksV2): Uint8Array {
  const n = peaks.n
  const data = new Uint8Array(n * 3)
  for (let i = 0; i < n; i++) {
    const mx = Math.max(0, Math.min(1, peaks.max[i] ?? 0))
    const mn = Math.max(0, Math.min(1, -(peaks.min[i] ?? 0)))
    const rms = Math.max(0, Math.min(1, peaks.rms[i] ?? 0))
    data[i * 3]     = Math.round(mx * 255)
    data[i * 3 + 1] = Math.round(mn * 255)
    data[i * 3 + 2] = Math.round(rms * 255)
  }
  return data
}
