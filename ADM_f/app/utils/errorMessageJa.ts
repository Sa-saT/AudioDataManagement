/**
 * API エラーコード → 日本語メッセージ変換。
 * バックエンドの HTTPException detail.code に対応。
 */
import type { ApiError } from '~/composables/useApi'

const MESSAGES: Record<string, (e?: ApiError) => string> = {
  // Auth / activation
  INVALID_LICENSE_SIGNATURE: () => 'ライセンスファイルの署名が不正です。',
  INVALID_LICENSE_FORMAT: () => 'ライセンスファイルの形式が不正です。',
  LICENSE_EXPIRED: () => 'ライセンスの有効期限が切れています。',
  LICENSE_REVOKED: () => 'このライセンスは取り消されています。',

  // Audio upload (Creator)
  INVALID_CODEC: () => '音源は PCM 形式の .wav のみ受け付けます (44.1k or 48k / 16〜24bit / stereo)。',
  INVALID_SAMPLE_RATE: () => 'サンプルレートは 44.1kHz か 48kHz のみ対応しています。',
  INVALID_BIT_DEPTH: () => 'ビット深度は 16/24bit のみ対応しています。',
  INVALID_CHANNELS: () => 'ステレオの音源のみ対応しています。',
  AUDIO_TOO_LONG: () => '音源が長すぎます (上限を超えています)。',
  NO_CREATOR_PROFILE: () => 'クリエイタープロファイルが見つかりません。管理者にお問い合わせください。',
  AUDIO_ALREADY_SOLD: () => '購入済みの音源は削除できません。',
  FORBIDDEN: () => '権限がありません。',

  // Download
  CREATOR_CANNOT_DOWNLOAD: () => '他のクリエイターの音源はダウンロードできません。',
  INSUFFICIENT_TOKENS: (e) => {
    const body = e?.body as { detail?: { required?: number; available?: number } } | undefined
    const req = body?.detail?.required
    const av = body?.detail?.available
    if (typeof req === 'number' && typeof av === 'number') {
      return `トークンが不足しています。必要 ${req} / 残量 ${av}`
    }
    return 'トークン残量が不足しています。'
  },
  ALREADY_SOLD: () => 'この音源は既に他のユーザがダウンロード済みです。',
  NOT_OWNER: () => 'この音源の再ダウンロード権限がありません。',
  NOT_FOUND: () => '指定された音源が見つかりません。',

  // Stream / signed URL
  INVALID_SIGNATURE: () => 'リンクの有効期限が切れたか、署名が不正です。再度お試しください。',

  // Admin
  INVALID_RANK: () => '無効なランクです。',
  ALREADY_PROCESSED: () => 'この支払いは既に処理済みです。',
  INVALID_ID: () => '無効なIDです。',
  USERNAME_TAKEN: () => 'このユーザ名は既に別のライセンスに紐付いています。',

  // Pagination / generic validation
  INVALID_PER_PAGE: () => '表示件数の値が不正です。',
}

export function errorMessageJa(err: unknown): string {
  if (!err || typeof err !== 'object') return '不明なエラーが発生しました。'
  const e = err as ApiError
  const fn = MESSAGES[e.code]
  if (fn) return fn(e)
  if (e.message) return e.message
  return '通信に失敗しました。しばらくしてから再度お試しください。'
}
