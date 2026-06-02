// WebGL2 (フォールバック: WebGL1 / Canvas2D) で波形を描画する composable。
// WAVEFORM_SHADER_SPEC.md §4 準拠。

import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'

import vertSrc from './shaders/waveform.vert.glsl?raw'
import fragSrc from './shaders/waveform.frag.glsl?raw'
import { drawWaveformFallback, type Fallback2DColors } from './fallback2d'
import { packPeaksRGB, toPeaksV2, type PeaksAny, type PeaksV2 } from './peaks'

export interface WaveformColors {
  wave: [number, number, number]      // 未再生側の色 (0..1 RGB)
  played: [number, number, number]    // 再生後の色 (0..1 RGB)
}

interface UseWaveformGLOptions {
  canvasRef: Ref<HTMLCanvasElement | null>
  peaksSource: Ref<PeaksAny | undefined>
  playPos: Ref<number>                 // 0..1
  isPlaying: Ref<boolean>
  colors: Ref<WaveformColors>
  gamma?: number                       // default 0.4
}

type RenderMode = 'webgl2' | 'webgl' | 'canvas2d' | 'none'

export function useWaveformGL(opts: UseWaveformGLOptions) {
  const mode = ref<RenderMode>('none')
  let raf = 0

  // WebGL state
  const gl = shallowRef<WebGL2RenderingContext | WebGLRenderingContext | null>(null)
  const program = shallowRef<WebGLProgram | null>(null)
  const peaksTex = shallowRef<WebGLTexture | null>(null)
  const uniforms: Record<string, WebGLUniformLocation | null> = {}

  function compile(glCtx: WebGL2RenderingContext | WebGLRenderingContext, src: string, type: number): WebGLShader | null {
    const sh = glCtx.createShader(type)!
    glCtx.shaderSource(sh, src)
    glCtx.compileShader(sh)
    if (!glCtx.getShaderParameter(sh, glCtx.COMPILE_STATUS)) {
      console.error('shader compile error', glCtx.getShaderInfoLog(sh))
      glCtx.deleteShader(sh)
      return null
    }
    return sh
  }

  function initGL(canvas: HTMLCanvasElement): boolean {
    const ctx = (canvas.getContext('webgl2', { premultipliedAlpha: false, antialias: true })
      ?? canvas.getContext('webgl', { premultipliedAlpha: false, antialias: true })
      ?? null) as WebGL2RenderingContext | WebGLRenderingContext | null
    if (!ctx) return false
    gl.value = ctx
    mode.value = ('drawBuffers' in ctx) ? 'webgl2' : 'webgl'

    // GLSL ES 1.00 への変換 (webgl1 用に簡易書換)
    // 注: 本来は別ファイル化が綺麗だが、今回は #version 削除 + in/out → attribute/varying のみで通す。
    const isWebGL2 = mode.value === 'webgl2'
    const vsSrc = isWebGL2 ? vertSrc : downgradeShader(vertSrc, true)
    const fsSrc = isWebGL2 ? fragSrc : downgradeShader(fragSrc, false)

    const vs = compile(ctx, vsSrc, ctx.VERTEX_SHADER)
    const fs = compile(ctx, fsSrc, ctx.FRAGMENT_SHADER)
    if (!vs || !fs) return false

    const prog = ctx.createProgram()!
    ctx.attachShader(prog, vs)
    ctx.attachShader(prog, fs)
    ctx.linkProgram(prog)
    if (!ctx.getProgramParameter(prog, ctx.LINK_STATUS)) {
      console.error('link error', ctx.getProgramInfoLog(prog))
      return false
    }
    program.value = prog

    // fullscreen quad (2 triangles)
    const buf = ctx.createBuffer()
    ctx.bindBuffer(ctx.ARRAY_BUFFER, buf)
    ctx.bufferData(ctx.ARRAY_BUFFER, new Float32Array([
      -1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1,
    ]), ctx.STATIC_DRAW)
    const loc = ctx.getAttribLocation(prog, 'aPos')
    ctx.enableVertexAttribArray(loc)
    ctx.vertexAttribPointer(loc, 2, ctx.FLOAT, false, 0, 0)

    // Uniform locations
    for (const name of ['uPeaks', 'uPlayPos', 'uGamma', 'uWaveColor', 'uPlayedColor']) {
      uniforms[name] = ctx.getUniformLocation(prog, name)
    }

    // Peaks texture
    const tex = ctx.createTexture()!
    ctx.bindTexture(ctx.TEXTURE_2D, tex)
    ctx.texParameteri(ctx.TEXTURE_2D, ctx.TEXTURE_MIN_FILTER, ctx.LINEAR)
    ctx.texParameteri(ctx.TEXTURE_2D, ctx.TEXTURE_MAG_FILTER, ctx.LINEAR)
    ctx.texParameteri(ctx.TEXTURE_2D, ctx.TEXTURE_WRAP_S, ctx.CLAMP_TO_EDGE)
    ctx.texParameteri(ctx.TEXTURE_2D, ctx.TEXTURE_WRAP_T, ctx.CLAMP_TO_EDGE)
    peaksTex.value = tex

    ctx.enable(ctx.BLEND)
    ctx.blendFunc(ctx.SRC_ALPHA, ctx.ONE_MINUS_SRC_ALPHA)

    return true
  }

  /** WebGL1 用に #version / in / out / texture() / fragColor を attribute / varying / texture2D / gl_FragColor へ書換。 */
  function downgradeShader(src: string, isVert: boolean): string {
    let s = src.replace(/^#version\s+300\s+es\s*\n/m, '')
    if (isVert) {
      s = s.replace(/\bin\s+/g, 'attribute ').replace(/\bout\s+/g, 'varying ')
    } else {
      s = s.replace(/\bin\s+/g, 'varying ')
      // declare gl_FragColor — 削除 out 宣言、最後の fragColor 出力先を gl_FragColor へ
      s = s.replace(/^out\s+vec4\s+fragColor;\s*\n/m, '')
      s = s.replace(/\bfragColor\b/g, 'gl_FragColor')
      s = s.replace(/\btexture\s*\(/g, 'texture2D(')
      s = 'precision highp float;\n' + s
    }
    return s
  }

  function uploadPeaks(peaks: PeaksV2) {
    const ctx = gl.value
    const tex = peaksTex.value
    if (!ctx || !tex) return
    const data = packPeaksRGB(peaks)
    ctx.bindTexture(ctx.TEXTURE_2D, tex)
    ctx.texImage2D(ctx.TEXTURE_2D, 0, ctx.RGB, peaks.n, 1, 0, ctx.RGB, ctx.UNSIGNED_BYTE, data)
  }

  function resize(canvas: HTMLCanvasElement) {
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const w = Math.max(1, Math.round(rect.width * dpr))
    const h = Math.max(1, Math.round(rect.height * dpr))
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      if (gl.value) gl.value.viewport(0, 0, w, h)
    }
  }

  function renderGL() {
    const ctx = gl.value
    const prog = program.value
    const canvas = opts.canvasRef.value
    if (!ctx || !prog || !canvas) return

    resize(canvas)
    ctx.useProgram(prog)

    ctx.activeTexture(ctx.TEXTURE0)
    ctx.bindTexture(ctx.TEXTURE_2D, peaksTex.value)
    ctx.uniform1i(uniforms.uPeaks!, 0)
    ctx.uniform1f(uniforms.uPlayPos!, opts.playPos.value)
    ctx.uniform1f(uniforms.uGamma!, opts.gamma ?? 0.4)

    const c = opts.colors.value
    ctx.uniform3f(uniforms.uWaveColor!, c.wave[0], c.wave[1], c.wave[2])
    ctx.uniform3f(uniforms.uPlayedColor!, c.played[0], c.played[1], c.played[2])

    ctx.clearColor(0, 0, 0, 0)
    ctx.clear(ctx.COLOR_BUFFER_BIT)
    ctx.drawArrays(ctx.TRIANGLES, 0, 6)
  }

  function renderFallback() {
    const canvas = opts.canvasRef.value
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = Math.max(1, Math.round(rect.width * dpr))
    canvas.height = Math.max(1, Math.round(rect.height * dpr))

    const peaks = opts.peaksSource.value ? toPeaksV2(opts.peaksSource.value) : null
    if (!peaks) return
    const c = opts.colors.value
    const toCss = (rgb: [number, number, number], a = 1) =>
      `rgba(${Math.round(rgb[0] * 255)},${Math.round(rgb[1] * 255)},${Math.round(rgb[2] * 255)},${a})`
    const fallbackColors: Fallback2DColors = { wave: toCss(c.wave), played: toCss(c.played) }
    drawWaveformFallback(canvas, peaks, opts.playPos.value, fallbackColors, { gamma: opts.gamma ?? 0.4 })
  }

  function render() {
    if (mode.value === 'webgl2' || mode.value === 'webgl') renderGL()
    else if (mode.value === 'canvas2d') renderFallback()
  }

  function loop() {
    render()
    // 再生中だけ次フレーム継続 (ホバー演出は削除済 → idle で 0%)
    if (opts.isPlaying.value) raf = requestAnimationFrame(loop)
    else raf = 0
  }

  function kick() {
    if (raf === 0) raf = requestAnimationFrame(loop)
  }

  // ─── Public ─────────────────────────────────────
  function init() {
    const canvas = opts.canvasRef.value
    if (!canvas) return
    const ok = initGL(canvas)
    if (!ok) {
      mode.value = 'canvas2d'
    } else {
      // Initial upload
      const p = opts.peaksSource.value
      if (p) uploadPeaks(toPeaksV2(p))
    }
    render()
  }

  // peaks 変更で再アップロード + 再描画
  watch(() => opts.peaksSource.value, (p) => {
    if (p && (mode.value === 'webgl2' || mode.value === 'webgl')) uploadPeaks(toPeaksV2(p))
    render()
  })
  // play 位置 / 再生状態変更で再描画
  watch(opts.playPos, () => kick())
  watch(opts.isPlaying, (p) => {
    if (p) kick()
    else render()
  })
  watch(opts.colors, () => render(), { deep: true })

  onBeforeUnmount(() => {
    if (raf) cancelAnimationFrame(raf)
    const ctx = gl.value
    if (ctx) {
      if (program.value) ctx.deleteProgram(program.value)
      if (peaksTex.value) ctx.deleteTexture(peaksTex.value)
    }
  })

  return { mode, init, kick }
}
