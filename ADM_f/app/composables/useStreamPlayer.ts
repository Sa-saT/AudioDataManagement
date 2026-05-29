/**
 * 10秒チャンク視聴の Web Audio API ラッパ。
 * audioId に対して seekTo(t) を呼ぶと:
 *  1. /audios/{id}/stream-url?start=t を叩き signed URL を取得
 *  2. signed URL を fetch → arrayBuffer
 *  3. decodeAudioData → AudioBufferSourceNode で再生
 *  4. チャンク終端 (約10秒) で自動停止
 *
 * AudioContext はインスタンスごとに 1 つ持ち、ユーザ操作起点で resume() する。
 */
export interface StreamPlayer {
  isPlaying: Ref<boolean>
  isLoading: Ref<boolean>
  /** チャンクの開始位置 (秒) */
  chunkStartSec: Ref<number>
  /** 現在の再生位置 (秒、トラック全体での絶対位置) */
  currentTime: Ref<number>
  /** チャンクの長さ (秒) */
  chunkDuration: Ref<number>
  /** 任意位置から 10秒チャンクを再生 */
  seekTo: (sec: number) => Promise<void>
  /** 一時停止 (再開せず) */
  pause: () => void
  /** 完全停止 + クリーンアップ */
  stop: () => void
  /** 再開 (現在のチャンクが残っていれば、なければ chunkStart から再フェッチ) */
  resume: () => Promise<void>
}

interface StreamUrlResponse {
  url: string
}

export function useStreamPlayer(audioId: string): StreamPlayer {
  const isPlaying = ref(false)
  const isLoading = ref(false)
  const chunkStartSec = ref(0)
  const currentTime = ref(0)
  const chunkDuration = ref(0)

  let ctx: AudioContext | null = null
  let source: AudioBufferSourceNode | null = null
  let buffer: AudioBuffer | null = null
  let startCtxTime = 0 // ctx.currentTime when playback started
  let pausedOffsetSec = 0 // pause した時点のチャンク内オフセット
  let rafId: number | null = null

  function ensureCtx(): AudioContext {
    if (!ctx) ctx = new (window.AudioContext || (window as never as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    return ctx
  }

  function cleanupSource() {
    if (source) {
      try { source.onended = null; source.stop(0) } catch { /* already stopped */ }
      source.disconnect()
      source = null
    }
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function trackTime() {
    if (!ctx || !source) return
    const elapsed = ctx.currentTime - startCtxTime + pausedOffsetSec
    currentTime.value = chunkStartSec.value + Math.min(elapsed, chunkDuration.value)
    if (isPlaying.value) rafId = requestAnimationFrame(trackTime)
  }

  async function fetchAndDecode(start: number): Promise<AudioBuffer> {
    const api = useApi()
    const config = useRuntimeConfig()
    const baseURL = config.public.apiBaseUrl as string
    const { url } = await api.get<StreamUrlResponse>(
      `/api/v1/audios/${audioId}/stream-url`,
      { query: { start } },
    )
    // backend は相対パス /api/v1/audios/stream?... を返すので apiBaseUrl を付与
    const fullUrl = url.startsWith('http') ? url : `${baseURL}${url}`
    const res = await fetch(fullUrl)
    if (!res.ok) throw new Error(`stream fetch failed: ${res.status}`)
    const arr = await res.arrayBuffer()
    return await ensureCtx().decodeAudioData(arr)
  }

  function playBufferFromOffset(offset: number) {
    if (!buffer || !ctx) return
    cleanupSource()
    source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)
    source.onended = () => {
      // チャンク終端 or 明示停止 (stop() で source.stop(0) を呼んでも発火する)。
      // 明示停止の場合は呼び出し側が既に isPlaying=false にしているので二重更新しない
      if (isPlaying.value) {
        isPlaying.value = false
        pausedOffsetSec = 0
        currentTime.value = chunkStartSec.value + chunkDuration.value
      }
    }
    source.start(0, offset)
    startCtxTime = ctx.currentTime
    pausedOffsetSec = offset
    isPlaying.value = true
    rafId = requestAnimationFrame(trackTime)
  }

  async function seekTo(sec: number): Promise<void> {
    const start = Math.max(0, Math.floor(sec))
    cleanupSource()
    isLoading.value = true
    try {
      const c = ensureCtx()
      if (c.state === 'suspended') await c.resume()
      buffer = await fetchAndDecode(start)
      chunkStartSec.value = start
      chunkDuration.value = buffer.duration
      currentTime.value = start
      pausedOffsetSec = 0
      playBufferFromOffset(0)
    } finally {
      isLoading.value = false
    }
  }

  function pause(): void {
    if (!isPlaying.value || !ctx || !source) return
    const elapsed = ctx.currentTime - startCtxTime + pausedOffsetSec
    pausedOffsetSec = Math.min(elapsed, chunkDuration.value)
    cleanupSource()
    isPlaying.value = false
  }

  async function resume(): Promise<void> {
    if (isPlaying.value) return
    if (!buffer) {
      // チャンクが無ければ chunkStart から再取得
      await seekTo(chunkStartSec.value)
      return
    }
    const c = ensureCtx()
    if (c.state === 'suspended') await c.resume()
    if (pausedOffsetSec >= chunkDuration.value) {
      // チャンク終端まで再生済み → 次のチャンクへ進む
      await seekTo(chunkStartSec.value + Math.floor(chunkDuration.value))
      return
    }
    playBufferFromOffset(pausedOffsetSec)
  }

  function stop(): void {
    cleanupSource()
    isPlaying.value = false
    pausedOffsetSec = 0
    currentTime.value = chunkStartSec.value
  }

  return {
    isPlaying,
    isLoading,
    chunkStartSec,
    currentTime,
    chunkDuration,
    seekTo,
    pause,
    stop,
    resume,
  }
}
