// Canvas 2D フォールバック。WebGL/WebGL2 が取れない環境向け。
// RMS 帯 + ガンマ補正は維持し、Shader 版の見た目に近づける。

import type { PeaksV2 } from './peaks'

export interface Fallback2DColors {
  wave: string         // 未再生側 (washi)
  progress: string     // 再生済側 (turquoise)
  rms: string          // RMS 帯
  cursor: string       // 再生位置線
}

export interface Fallback2DOptions {
  gamma?: number       // default 0.4
}

export function drawWaveformFallback(
  canvas: HTMLCanvasElement,
  peaks: PeaksV2,
  playPos: number,             // 0..1
  colors: Fallback2DColors,
  opts: Fallback2DOptions = {},
): void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  const W = canvas.width
  const H = canvas.height
  const gamma = opts.gamma ?? 0.4

  ctx.clearRect(0, 0, W, H)

  const n = peaks.n
  if (n === 0) return

  const playX = Math.round(playPos * W)
  const half = H / 2

  // 各 bucket を縦 1〜2px の細い帯として描画
  const stepX = W / n
  for (let i = 0; i < n; i++) {
    const x = i * stepX
    const mx = Math.pow(Math.max(0, peaks.max[i] ?? 0), gamma)
    const mn = Math.pow(Math.max(0, -(peaks.min[i] ?? 0)), gamma)
    const rms = Math.pow(Math.max(0, peaks.rms[i] ?? 0), gamma)

    const topY = half - mx * half
    const botY = half + mn * half
    const rmsTop = half - rms * half
    const rmsBot = half + rms * half

    // 再生位置を境に色切替
    const isProgress = x < playX
    ctx.fillStyle = isProgress ? colors.progress : colors.wave
    ctx.fillRect(x, topY, Math.max(1, stepX), botY - topY)

    // RMS 帯 (中央濃色)
    ctx.fillStyle = colors.rms
    ctx.globalAlpha = 0.7
    ctx.fillRect(x, rmsTop, Math.max(1, stepX), rmsBot - rmsTop)
    ctx.globalAlpha = 1.0
  }

  // 再生位置カーソル
  ctx.fillStyle = colors.cursor
  ctx.fillRect(playX, 0, Math.max(1, dpr), H)
}
