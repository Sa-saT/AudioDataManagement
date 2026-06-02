// Canvas 2D フォールバック (WebGL 未対応時)。
// 再生位置で色を切替: 未再生 = colors.wave / 再生後 = colors.played

import type { PeaksV2 } from './peaks'

export interface Fallback2DColors {
  wave: string         // 未再生側の色 (rgb / rgba)
  played: string       // 再生後の色 (rgb / rgba)
}

export interface Fallback2DOptions {
  gamma?: number       // default 0.4
}

const RMS_BOOST = 0.35    // RMS 帯の上乗せ濃度
const BAR_COUNT = 128     // 画面上のバー本数 (shader と一致させる)
const BAR_GAP_RATIO = 0.22  // バー幅の 22% を gap

export function drawWaveformFallback(
  canvas: HTMLCanvasElement,
  peaks: PeaksV2,
  playPos: number,             // 0..1
  colors: Fallback2DColors,
  opts: Fallback2DOptions = {},
): void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const W = canvas.width
  const H = canvas.height
  const gamma = opts.gamma ?? 0.4

  ctx.clearRect(0, 0, W, H)

  const n = peaks.n
  if (n === 0) return

  const playX = Math.round(playPos * W)
  const half = H / 2
  const cellW = W / BAR_COUNT
  const barW = cellW * (1 - BAR_GAP_RATIO)
  const barOffset = cellW * (BAR_GAP_RATIO * 0.5)

  for (let i = 0; i < BAR_COUNT; i++) {
    // 1000-point peaks から各バー範囲の max を採用 (ピーク強調)
    const srcStart = Math.floor((i / BAR_COUNT) * n)
    const srcEnd = Math.floor(((i + 1) / BAR_COUNT) * n)
    let mxRaw = 0, mnRaw = 0, rmsRaw = 0
    for (let j = srcStart; j < srcEnd; j++) {
      mxRaw = Math.max(mxRaw, peaks.max[j] ?? 0)
      mnRaw = Math.max(mnRaw, -(peaks.min[j] ?? 0))
      rmsRaw = Math.max(rmsRaw, peaks.rms[j] ?? 0)
    }
    const mx = Math.pow(mxRaw, gamma)
    const mn = Math.pow(mnRaw, gamma)
    const rms = Math.pow(rmsRaw, gamma)

    const cellX = i * cellW
    const barX = cellX + barOffset
    const isPlayed = cellX + cellW * 0.5 < playX
    const fill = isPlayed ? colors.played : colors.wave

    ctx.globalAlpha = 1.0
    ctx.fillStyle = fill
    ctx.fillRect(barX, half - mx * half, Math.max(1, barW), (mx + mn) * half)

    ctx.globalAlpha = RMS_BOOST
    ctx.fillRect(barX, half - rms * half, Math.max(1, barW), rms * 2 * half)
  }
  ctx.globalAlpha = 1.0
}
