/**
 * errorMessageJa — API エラーコード → 日本語変換のユニットテスト。
 * Nuxt / Vue ランタイム不要な純粋関数なので node 環境で動く。
 * `import type { ApiError }` は esbuild が消去するため useApi の実行依存はない。
 */
import { describe, expect, it } from 'vitest'
import { ApiError } from '~/composables/useApi'
import { errorMessageJa } from '~/utils/errorMessageJa'

describe('errorMessageJa', () => {
  describe('認証 / ライセンスエラー', () => {
    it('INVALID_LICENSE_SIGNATURE', () => {
      expect(errorMessageJa(new ApiError('', 401, 'INVALID_LICENSE_SIGNATURE')))
        .toBe('ライセンスファイルの署名が不正です。')
    })
    it('INVALID_LICENSE_FORMAT', () => {
      expect(errorMessageJa(new ApiError('', 422, 'INVALID_LICENSE_FORMAT')))
        .toBe('ライセンスファイルの形式が不正です。')
    })
    it('LICENSE_EXPIRED', () => {
      expect(errorMessageJa(new ApiError('', 401, 'LICENSE_EXPIRED')))
        .toBe('ライセンスの有効期限が切れています。')
    })
    it('LICENSE_REVOKED', () => {
      expect(errorMessageJa(new ApiError('', 401, 'LICENSE_REVOKED')))
        .toBe('このライセンスは取り消されています。')
    })
  })

  describe('音源アップロードエラー', () => {
    it('INVALID_CODEC', () => {
      expect(errorMessageJa(new ApiError('', 422, 'INVALID_CODEC'))).toContain('PCM')
    })
    it('INVALID_SAMPLE_RATE', () => {
      expect(errorMessageJa(new ApiError('', 422, 'INVALID_SAMPLE_RATE'))).toContain('44.1kHz')
    })
    it('INVALID_BIT_DEPTH', () => {
      expect(errorMessageJa(new ApiError('', 422, 'INVALID_BIT_DEPTH'))).toContain('16/24bit')
    })
    it('INVALID_CHANNELS', () => {
      expect(errorMessageJa(new ApiError('', 422, 'INVALID_CHANNELS'))).toContain('ステレオ')
    })
    it('AUDIO_TOO_LONG', () => {
      expect(errorMessageJa(new ApiError('', 422, 'AUDIO_TOO_LONG'))).toContain('長すぎます')
    })
    it('NO_CREATOR_PROFILE', () => {
      expect(errorMessageJa(new ApiError('', 404, 'NO_CREATOR_PROFILE'))).toContain('クリエイタープロファイル')
    })
    it('AUDIO_ALREADY_SOLD', () => {
      expect(errorMessageJa(new ApiError('', 409, 'AUDIO_ALREADY_SOLD'))).toContain('購入済み')
    })
    it('FORBIDDEN', () => {
      expect(errorMessageJa(new ApiError('', 403, 'FORBIDDEN'))).toBe('権限がありません。')
    })
  })

  describe('ダウンロードエラー', () => {
    it('CREATOR_CANNOT_DOWNLOAD', () => {
      expect(errorMessageJa(new ApiError('', 403, 'CREATOR_CANNOT_DOWNLOAD')))
        .toContain('他のクリエイター')
    })

    it('INSUFFICIENT_TOKENS — detail に required/available あり', () => {
      const err = new ApiError('', 402, 'INSUFFICIENT_TOKENS', {
        detail: { required: 120, available: 30 },
      })
      const msg = errorMessageJa(err)
      expect(msg).toContain('必要 120')
      expect(msg).toContain('残量 30')
    })

    it('INSUFFICIENT_TOKENS — detail なし → 汎用文言', () => {
      expect(errorMessageJa(new ApiError('', 402, 'INSUFFICIENT_TOKENS')))
        .toBe('トークン残量が不足しています。')
    })

    it('ALREADY_SOLD', () => {
      expect(errorMessageJa(new ApiError('', 409, 'ALREADY_SOLD'))).toContain('他のユーザ')
    })

    it('NOT_OWNER', () => {
      expect(errorMessageJa(new ApiError('', 403, 'NOT_OWNER'))).toContain('再ダウンロード')
    })

    it('NOT_FOUND', () => {
      expect(errorMessageJa(new ApiError('', 404, 'NOT_FOUND'))).toContain('見つかりません')
    })
  })

  describe('Admin エラー', () => {
    it('INVALID_RANK', () => {
      expect(errorMessageJa(new ApiError('', 400, 'INVALID_RANK'))).toBe('無効なランクです。')
    })
    it('ALREADY_PROCESSED', () => {
      expect(errorMessageJa(new ApiError('', 409, 'ALREADY_PROCESSED'))).toContain('処理済み')
    })
    it('USERNAME_TAKEN', () => {
      expect(errorMessageJa(new ApiError('', 409, 'USERNAME_TAKEN'))).toContain('ユーザ名')
    })
  })

  describe('汎用フォールバック', () => {
    it('未知コードはメッセージをそのまま返す', () => {
      expect(errorMessageJa(new ApiError('カスタムエラー', 500, 'UNKNOWN_CODE')))
        .toBe('カスタムエラー')
    })

    it('null → 不明なエラー', () => {
      expect(errorMessageJa(null)).toBe('不明なエラーが発生しました。')
    })

    it('文字列 → 不明なエラー', () => {
      expect(errorMessageJa('error string')).toBe('不明なエラーが発生しました。')
    })

    it('コードもメッセージも空 → 通信失敗文言', () => {
      expect(errorMessageJa(new ApiError('', 500, 'X'))).toContain('通信に失敗しました')
    })
  })
})
