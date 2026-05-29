// Canvas 2D フォールバック (WebGL 未対応時)。
// 改訂: 単一色 + 再生済みは alpha を下げて視覚的に dim。

import type { PeaksV2 } from './peaks'

export interface Fallback2DColors {
  wave: string         // 単一色 (rgb / rgba)
}

export interface Fallback2DOptions {
  gamma?: number       // default 0.4
}

const DIM_ALPHA = 0.35    // 再生済み部分の透明度
const RMS_BOOST = 0.35    // RMS 帯の上乗せ濃度

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
  const stepX = W / n

  for (let i = 0; i < n; i++) {
    const x = i * stepX
    const mx = Math.pow(Math.max(0, peaks.max[i] ?? 0), gamma)
    const mn = Math.pow(Math.max(0, -(peaks.min[i] ?? 0)), gamma)
    const rms = Math.pow(Math.max(0, peaks.rms[i] ?? 0), gamma)

    const isPlayed = x < playX
    ctx.globalAlpha = isPlayed ? DIM_ALPHA : 1.0

    // 包絡 (上端〜下端)
    ctx.fillStyle = colors.wave
    ctx.fillRect(x, half - mx * half, Math.max(1, stepX), (mx + mn) * half)

    // RMS 中央帯 (同色を重ねて濃度アップ)
    ctx.globalAlpha = (isPlayed ? DIM_ALPHA : 1.0) * RMS_BOOST
    ctx.fillRect(x, half - rms * half, Math.max(1, stepX), rms * 2 * half)
  }
  ctx.globalAlpha = 1.0
}
