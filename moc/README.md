# Pathfinder — Presentation Mock (`moc/`)

クライアント提案用の静的モック。HTML/CSS/JS のみ（ビルド不要）。

## 画面とフロー

| ファイル | 内容 |
|---|---|
| `index.html` | Activate / ランディング。ロール選択（creator / licensee / admin） |
| `dashboard.html` | 音源一覧。ロールで UI が変化（licensee=DL / creator=♥人数） |
| `commission.html` | 発注一覧。ステータス pill + 要対応ドット |
| `order.html` | 発注チケット詳細。ブリーフ + LINE 風チャット + 共有メモ |
| `admin.html` | 運営画面。Users / Payout / Token / lic / ログ / 設定 タブ |
| `uploads.html` | creator のアップロード画面。タグ選択 + 波形プレビュー |

- ロールは `index.html` で選択 → `localStorage` に保存。以降のページがその視点で表示。
- 右上 **⏻** で `index.html` に戻り、別ロールへ切替。

## ローカル確認

`file://` 直開きでも概ね動くが、`localStorage` 制限を避けるため簡易サーバ推奨：

```bash
cd moc && python3 -m http.server 8080   # → http://localhost:8080/
```

## GitHub Pages 公開

`.github/workflows/deploy-moc.yml` が `moc/**` の push で自動デプロイ。
**Settings → Pages → Source = "GitHub Actions"** を一度だけ設定すれば有効化。

公開 URL: `https://sa-sat.github.io/AudioDataManagement/`
