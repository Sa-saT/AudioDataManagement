## Overview

Cursor's marketing site reads as a quietly-confident developer brand that believes in editorial calm over IDE-darkness. The base canvas is **warm cream** (`{colors.canvas}` — #f7f7f4) holding warm near-black ink (`{colors.ink}` — #26251e) for body and display alike. The single brand voltage is **Cursor Orange** (`{colors.primary}` — #f54e00) reserved for primary CTAs and the wordmark — used scarcely.

Type runs **CursorGothic** as the single sans family. Display sits at weight 400 with negative letter-spacing — a magazine-editorial voice rather than tech-bombastic. JetBrains Mono carries every code surface (and code surfaces are roughly half the page).

The brand's strongest visual signature is the **AI-timeline pill palette**: five pastel pills (peach `{colors.timeline-thinking}`, mint `{colors.timeline-grep}`, blue `{colors.timeline-read}`, lavender `{colors.timeline-edit}`, gold `{colors.timeline-done}`) marking AI-action stages inside in-product timeline visualizations. Used only in product UI — never as system action colors.

**Key Characteristics:**
- Warm cream canvas, not white. Ink is warm (#26251e), not pure black.
- Single CTA color: `{colors.primary}` (Cursor Orange #f54e00). Used scarcely.
- Display weight stays at 400 — never bold. Magazine voice.
- AI timeline pastels: 5 dedicated tokens for in-product agent action stages.
- Compact 8px CTA radius — developer dialect.
- Hairline-only depth; no drop shadows.
- 80px section rhythm.

## Colors

### Brand & Accent
- **Cursor Orange** (`{colors.primary}` — #f54e00): Primary CTA pills, wordmark, hero accent. Used scarcely.
- **Cursor Orange Active** (`{colors.primary-active}` — #d04200): Press state.

### Surface
- **Canvas** (`{colors.canvas}` — #f7f7f4): Warm cream page floor.
- **Canvas Soft** (`{colors.canvas-soft}` — #fafaf7): IDE-pane background inside mockups.
- **Surface Card** (`{colors.surface-card}` — #ffffff): Pure white card surface — slight contrast against the cream canvas.
- **Surface Strong** (`{colors.surface-strong}` — #e6e5e0): Badges, tag pills.

### Hairlines
- **Hairline** (`{colors.hairline}` — #e6e5e0): 1px divider.
- **Hairline Soft** (`{colors.hairline-soft}` — #efeee8): Lighter divider.
- **Hairline Strong** (`{colors.hairline-strong}` — #cfcdc4): Stronger panel outline.

### Text
- **Ink** (`{colors.ink}` — #26251e): Display, body emphasis. Warm near-black.
- **Body** (`{colors.body}` — #5a5852): Default running-text.
- **Body Strong** (`{colors.body-strong}` — #26251e): Same as ink.
- **Muted** (`{colors.muted}` — #2f4f4f): Sub-titles.
- **Muted Soft** (`{colors.muted-soft}` — #a09c92): Disabled text.
- **On Primary** (`{colors.on-primary}` — #ffffff): White text on Cursor Orange.

### Timeline (AI-action signature)
- **Thinking** (`{colors.timeline-thinking}` — #dfa88f): Peach. Used inside in-product agent timeline only.
- **Grep** (`{colors.timeline-grep}` — #9fc9a2): Mint.
- **Read** (`{colors.timeline-read}` — #9fbbe0): Pastel blue.
- **Edit** (`{colors.timeline-edit}` — #c0a8dd): Lavender.
- **Done** (`{colors.timeline-done}` — #c08532): Warm gold.

### Semantic
- **Success** (`{colors.semantic-success}` — #1f8a65): Confirmation indicators.
- **Error** (`{colors.semantic-error}` — #cf2d56): Validation errors.

## Typography

### Font Family
**CursorGothic** is the licensed display + body family. Fallback: `system-ui, "Helvetica Neue", Helvetica, Arial, sans-serif`. Code surfaces switch to **JetBrains Mono**.

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|
| `{typography.display-mega}` | 72px | 400 | 1.1 | -2.16px | Homepage hero h1 |
| `{typography.display-lg}` | 36px | 400 | 1.2 | -0.72px | Section heads |
| `{typography.display-md}` | 26px | 400 | 1.25 | -0.325px | Sub-section heads |
| `{typography.display-sm}` | 22px | 400 | 1.3 | -0.11px | Card group titles |
| `{typography.title-md}` | 18px | 600 | 1.4 | 0 | Component titles |
| `{typography.title-sm}` | 16px | 600 | 1.4 | 0 | List labels |
| `{typography.body-md}` | 16px | 400 | 1.5 | 0 | Default body |
| `{typography.body-tracked}` | 16px | 400 | 1.5 | 0.08px | Tracked editorial body |
| `{typography.body-sm}` | 14px | 400 | 1.5 | 0 | Footer body |
| `{typography.caption}` | 13px | 400 | 1.4 | 0 | Photo captions |
| `{typography.caption-uppercase}` | 11px | 600 | 1.4 | 0.88px | Section labels, timeline pill labels |
| `{typography.code}` | 13px | 400 | 1.5 | 0 | Code blocks — JetBrains Mono |
| `{typography.button}` | 14px | 500 | 1.0 | 0 | CTA pill labels |
| `{typography.nav-link}` | 14px | 500 | 1.4 | 0 | Top-nav menu |

### Principles
- **Display weight stays at 400.** Magazine voice, never bold.
- **Negative letter-spacing on display only.** -0.11px to -2.16px tracking.
- **JetBrains Mono on every code surface.**

### Note on Font Substitutes
CursorGothic is licensed. Open-source substitute: **Inter** at weight 400 with letter-spacing -1.5%. Or **GT Sectra** for a more editorial feel.

## Layout

### Spacing System
- **Base unit:** 4px.
- **Tokens:** `{spacing.xxs}` 4px · `{spacing.xs}` 8px · `{spacing.sm}` 12px · `{spacing.base}` 16px · `{spacing.md}` 20px · `{spacing.lg}` 24px · `{spacing.xl}` 32px · `{spacing.xxl}` 48px · `{spacing.section}` 80px.
- **Section padding:** 80px.

### Grid & Container
- Max content width: ~1200px.
- Editorial body: 12-column grid.
- Feature card grids: 2-up at desktop for splits, 3-up for benefits.
- Footer: 5-column at desktop.

### Whitespace Philosophy
Generous editorial pacing — closer to a print magazine than a tech site. The cream canvas has plenty of breathing room; cards within bands sit close (16-24px gap).

## Elevation & Depth

The system uses **hairline-only depth**. No drop shadows, no elevation tiers. Cards float above the canvas via 1px hairlines and the slight white-on-cream contrast.

| Level | Treatment | Use |
|---|---|---|
| Flat (canvas) | `{colors.canvas}` (#f7f7f4) | Body bands, footer |
| Card | `{colors.surface-card}` (#ffffff) | Content cards |
| Hairline border | 1px `{colors.hairline}` | Card outlines, dividers |
| IDE pane | `{colors.canvas-soft}` (#fafaf7) | Inside IDE mockup cards |

### Decorative Depth
- **IDE-mockup cards** are the only "elevated" element. White card on cream canvas with internal pane structure mimicking the actual Cursor editor.
- **Timeline pastel pills** add chromatic depth without surface elevation.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.none}` | 0px | Reserved |
| `{rounded.xs}` | 4px | Inline tags |
| `{rounded.sm}` | 6px | Compact rows |
| `{rounded.md}` | 8px | CTA buttons, form inputs |
| `{rounded.lg}` | 12px | Cards, IDE panes |
| `{rounded.xl}` | 16px | Larger feature cards (rare) |
| `{rounded.pill}` | 9999px | Timeline pills, badges |
| `{rounded.full}` | 9999px | Avatars (rare) |

## Components

### Top Navigation

**`top-nav`** — Background `{colors.canvas}`, text `{colors.ink}`, height 64px. Layout: Cursor wordmark left, primary horizontal menu (Pricing / Features / Enterprise / Blog / Forum / Careers), Sign In + Download primary CTA right.

### Buttons

**`button-primary`** — The signature Cursor Orange CTA. Background `{colors.primary}`, text `{colors.on-primary}`, type `{typography.button}` (14px / 500), padding 10px × 18px, height 40px, rounded `{rounded.md}` (8px).

**`button-primary-active`** — Press state. Background `{colors.primary-active}`.

**`button-secondary`** — White card pill on cream canvas. Background `{colors.surface-card}`, text `{colors.ink}`, 1px `{colors.hairline-strong}` border.

**`button-tertiary-text`** — Inline ink text link.

**`button-download`** — Larger ink-canvas CTA. Background `{colors.ink}`, text `{colors.canvas}`, padding 12px × 20px, height 44px. Used for "Download for macOS" type CTAs.

### Hero & IDE Mockups

**`hero-band`** — Background `{colors.canvas}`, full-width display headline in `{typography.display-mega}` (72px / 400 / -2.16px), subhead in `{typography.body-md}`, two CTAs (`button-download` + `button-tertiary-text`), and a centered IDE-mockup card below the hero copy.

**`ide-mockup-card`** — A white card containing a multi-pane IDE mockup (sidebar + main editor + chat panel + terminal). Background `{colors.surface-card}`, rounded `{rounded.lg}` (12px), 1px `{colors.hairline}` border, no padding (panes fill the card edge-to-edge).

**`ide-pane`** — Individual IDE pane inside the mockup. Background `{colors.canvas-soft}`, text `{colors.body}` in `{typography.code}` (JetBrains Mono 13px), rounded `{rounded.md}` (8px), padding 16px.

### Cards

**`feature-card`** — Background `{colors.surface-card}`, text `{colors.ink}`, type `{typography.title-md}`, rounded `{rounded.lg}`, padding 24px. 1px `{colors.hairline}` border.

**`comparison-card`** — Side-by-side "Cursor vs other tools" card. Same surface and rounding; internally split into 2 columns.

**`testimonial-card`** — Quote card. Background `{colors.surface-card}`, text `{colors.body}`, rounded `{rounded.lg}`, padding 24px.

### AI Timeline (signature)

**`timeline-pill-thinking`** — Peach pill. Background `{colors.timeline-thinking}`, text `{colors.ink}`, type `{typography.caption-uppercase}` (11px / 600 / 0.88px tracking, uppercase), rounded `{rounded.pill}`, padding 4px × 10px. Marks "Thinking" stage in product timeline.

**`timeline-pill-grep`** — Mint pill. Same shape, background `{colors.timeline-grep}`. Marks "Grepping" stage.

**`timeline-pill-read`** — Pastel-blue pill. Background `{colors.timeline-read}`. Marks "Reading" stage.

**`timeline-pill-edit`** — Lavender pill. Background `{colors.timeline-edit}`. Marks "Editing" stage.

**`timeline-pill-done`** — Gold pill. Background `{colors.timeline-done}`, text `{colors.on-primary}` white. Marks "Done" stage.

### Code

**`code-block`** — Inline code block. Background `{colors.surface-card}`, text `{colors.ink}` in `{typography.code}`, rounded `{rounded.lg}`, padding 20px, 1px `{colors.hairline}` border.

### Pricing

**`pricing-tier-card`** — Background `{colors.surface-card}`, rounded `{rounded.lg}`, padding 32px, 1px `{colors.hairline}` border.

**`pricing-tier-featured`** — Featured tier inverts to ink. Background `{colors.ink}`, text `{colors.canvas}`. Same shape, dark inversion signals "highlighted" without colored ribbon.

### Forms & Tags

**`text-input`** — Background `{colors.surface-card}`, text `{colors.ink}`, rounded `{rounded.md}` (8px), padding 12px × 16px, height 44px.

**`badge-pill`** — Small uppercase pill. Background `{colors.surface-strong}`, text `{colors.ink}`, type `{typography.caption-uppercase}`, rounded `{rounded.pill}`, padding 4px × 10px.

### CTA / Footer

**`cta-band`** — Pre-footer "Try Cursor now" band. Background `{colors.canvas}`, centered display headline in `{typography.display-lg}`, single Cursor Orange CTA. 96px vertical padding.

**`footer`** — Closing footer. Background `{colors.canvas}`, text `{colors.body}`. 5-column link list. 64×48px padding.

**`footer-link`** — Background transparent, text `{colors.body}`, type `{typography.body-sm}`.

## Do's and Don'ts

### Do
- Reserve `{colors.primary}` (Cursor Orange) for primary CTAs and brand wordmark.
- Keep display weight at 400. The editorial voice depends on this.
- Use the cream `{colors.canvas}` page floor — never pure white.
- Render every code surface (inline, blocks, IDE panes) in JetBrains Mono.
- Use timeline pastels only inside in-product agent visualizations — never as system action colors.

### Don't
- Don't introduce a secondary brand action color. Cursor Orange is the only one.
- Don't drop display to bold weights (700+). Magazine voice depends on 400.
- Don't add drop shadows. Hairlines + ink-on-cream contrast carry the depth.
- Don't use timeline pastels on non-timeline UI. They're scoped to the agent timeline only.
- Don't extract a CTA color from a third-party widget (cookie consent, OneTrust). The brand's CTA is what appears on actual product CTAs.

## Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|---|---|---|
| Mobile | < 640px | Hero h1 72→32px; IDE mockup collapses to single pane preview; feature grid 1-up; nav hamburger. |
| Tablet | 640–1024px | Hero h1 56px; IDE mockup compresses; feature grid 2-up. |
| Desktop | 1024–1280px | Full hero h1 72px; full multi-pane IDE mockup; feature grid 3-up. |
| Wide | > 1280px | Content caps at 1200px. |

### Touch Targets
- Primary CTA at 40px height — at WCAG AA, padded for AAA.
- Download CTA at 44px — at AAA.

### Collapsing Strategy
- Top nav switches to hamburger below 768px.
- IDE mockup multi-pane collapses to a single primary pane preview on mobile.
- Feature grid: 3-up → 2-up → 1-up.

## Iteration Guide

1. Focus on a single component at a time.
2. CTAs default to `{rounded.md}` (8px). Cards use `{rounded.lg}` (12px).
3. Variants live as separate entries inside `components:`.
4. Use `{token.refs}` everywhere — never inline hex.
5. Hover state never documented.
6. CursorGothic 400 for display, 400/500/600 for body. JetBrains Mono on every code surface.
7. Cursor Orange stays scarce.
8. Timeline pastels stay scoped to in-product agent visualizations.

## Pathfinder Brand Override

Cursor リファレンスから以下の点のみ差し替え。他のトークン・タイポグラフィ・spacing は継承。

### Colors

| Token | Cursor 値 | Pathfinder 値 |
|---|---|---|
| `{colors.primary}` | Cursor Orange `#f54e00` | MediumAquamarine `#66cdaa` |
| `{colors.primary-active}` | `#d04200` | `#006400` |
| `{colors.accent}` | (なし) | Crimson `#dc143c`（警戒色）— NEW バッジ / token 残量 ≤10% / error 限定 |
| `{colors.seagreen}` | (なし) | LightSeaGreen `#20b2aa` — 副次 interactive teal |
| `{colors.seagreen.deep}` | (なし) | `#0e7a74` — seagreen 上のテキスト/濃淡 |
| `{colors.admin}` | (なし) | Coral `#ff7f50` — admin ロール識別 (`.deep` `#c0451f` = テキスト) |
| `{colors.licensee}` | (なし) | LightSteelBlue `#b0c4de` — licensee ロール識別 (`.deep` `#5a6e8c` = テキスト) |
| `{colors.notify}` | (なし) | 橙 `#ffa500` 通知ベース / `.dot` 金 `#ffd700`（NOTIFICATION_SPEC §7） |

> **seagreen の用途** (primary とは別系統の「副次的な相互作用色」):
> - ✅ creator / Commission 文脈の識別 (creator ロールバッジ、DM creator バブル、受諾/指名ボタン)
> - ✅ Order ステータス `assigned`、候補 `accepted`
> - ✅ AudioCard の編集ボタン、Admin token 使用率ゲージ、guest 未アクティベート バナー
> - ✅ チャート系 (BarChart / Heatmap / RadarChart) のデフォルト色
> - ❌ primary (CTA / アクティブページ下線) の代替として使わない — 役割を混ぜない
> - 透過は Tailwind opacity 修飾子を使う (`bg-seagreen/15` 等)。生 hex 直書き禁止 (チャートの JS prop と canvas 演出のみ例外)

### Canvas (背景)
- Cursor: warm cream `{colors.canvas}` (#f7f7f4)
- Pathfinder: `public/background.png` (washi 和紙テクスチャ 1920×1080)
  `background-size: cover; background-repeat: no-repeat; background-attachment: fixed`

### Card
- Cursor: `{colors.surface-card}` (solid #ffffff)
- Pathfinder: `rgba(255,255,255,0.72)` + `backdrop-filter: blur(8px)` + 1px `{colors.hairline}` border

### Header
- 高さ: **48px** (Cursor 64px から縮小)
- 背景: 透明 — washi がそのまま透ける
- Active page indicator: ロゴ下 2px primary `#66cdaa` 下線 (`bg-primary`)
- 表示: ロゴ (Pathfinder) + nav リンクのみ。role / token 等の status は Dashboard ページ側に表示

### Footer
- 高さ: **44px** (`h-11`)
- 背景: 透明
- 上辺: hairline なし (現状の実装は透明・ボーダーなし)
- 内容: `© YYYY Pathfinder` + バージョン番号、中央揃え

### Buttons (Pathfinder)

Cursor の単色 CTA を上書き。Pathfinder の主要アクションは **ink ベース → hover で primary に点灯**。
クラスは `app/assets/css/main.css` の `@layer components` に定義。**生 hex / inline 配色でボタンを作らない** (この体系を使う)。

| クラス | 用途 | 配色 | サイズ (px / text) |
|---|---|---|---|
| `.btn-primary` | 主要アクション (デフォルト) | `bg-ink text-canvas` → hover `bg-primary text-white` | px-4 py-1.5 / 12px |
| `.btn-primary-sm` | 同上・小 | 同上 | px-3 py-1.5 / 12px |
| `.btn-primary-xs` | 同上・密なリスト/Commission | 同上 | px-3 py-1 / 11px |
| `.btn-emphasis` | 強調アクション (例: 提出) | `bg-primary text-ink` → hover `bg-primary-active text-white` | px-3 py-1.5 / 12px |
| `.btn-secondary` | 副次 (白ピル) | `bg-surface-card text-ink` + hairline-strong border | h-10 px-[18px] |
| `.btn-ink` | 単色 ink CTA (hover 変化なし) | `bg-ink text-canvas` | h-11 px-5 |

- `disabled:opacity-50` は全クラス内蔵。`w-full` / `mt-*` 等のレイアウトは併用クラスで付与。
- **例外 (クラス化しない意図的特殊):** `ConfirmModal` の confirm (danger=accent 兼用) / Admin 設定の追加ボタン (成功フラッシュ `bg-primary scale-95`) / group-hover で点灯するラベル span。

### Card hover
- `transform: translateY(-1px)` + border-color → primary `#66cdaa` (200ms)

### Waveform
- Idle (未再生): DarkGray `#a9a9a9` (専用色、`muted` トークンとは独立)
- Playing progress (再生後): MediumAquamarine `#66cdaa`
- Cursor: primary `#66cdaa`

### Navigation Conventions

#### 戻るボタン `[<]`

親子関係にある全ページのヘッダーに共通して配置するルール。

| 項目 | 値 |
|---|---|
| アイコン | `<polyline points="15 18 9 12 15 6"/>` / 22×22px / stroke-width=3 |
| 色 | `text-ink/70`、hover: `text-ink` |
| 動作 | `router.back()` / 履歴なし時は親一覧へ |
| 縦揃え | ヘッダー flex コンテナは **`items-center`** に統一 |

**ヘッダーレイアウト規則:**

```html
<!-- 親子ページ共通テンプレート -->
<div class="flex shrink-0 items-center gap-3 pb-3 pt-5">
  <button @click="goBack">          <!-- 常に items-center で縦中央 -->
    <svg width="22" height="22" stroke-width="3">
      <polyline points="15 18 9 12 15 6"/>
    </svg>
  </button>
  <div>タイトル / メタ情報</div>
</div>
```

- admin 限定の `[<]` は `v-if="isAdmin"` で出し分けるが、コンテナは常に `items-center` を維持する
- `items-end` は使わない（子ページ間で `[<]` の縦位置がずれるため）
- 適用ページ: `orders/index.vue`（Commission 一覧）、`orders/[id].vue`（チケット詳細）、および今後追加する親子ページすべて

### Card content (AudioCard)
- Layout (grid): `[WaveformPlayer: 260px] [meta+tags: 1fr] [right: 88px]`
- meta: title / creator / tags (イメージタグ pill)
- right: token 数 + ♥ heart (user: toggle only / creator: ♥ + 人数)

### Accent (Crimson 警戒色) usage rules
- ✅ NEW バッジ
- ✅ token 残量 ≤10% のゲージ
- ✅ error / validation
- ❌ それ以外での使用禁止 — primary と同様に scarce に保つ
- ※ admin ロール識別は accent ではなく専用 `admin` (Coral) を使う (警戒色と混同させない)

### ロール識別色 (role identity)
役割を色で一目で判別させる。バッジ・DM/チャットのアバター&バブルで使用。

| ロール | 色 | バッジ (washi 上) | バブル |
|---|---|---|---|
| **admin** | `admin` Coral `#ff7f50` | `bg-admin/15 text-admin-deep border-admin/35` | `bg-admin text-white` |
| **creator** | `seagreen` `#20b2aa` | `bg-seagreen/15 text-seagreen-deep border-seagreen/35` | `bg-seagreen text-white` |
| **licensee** | `licensee` LightSteelBlue `#b0c4de` | `bg-licensee/25 text-licensee-deep border-licensee/40` | `bg-licensee text-ink` (淡色のため ink 文字) |
| guest | `ink` | (未アクティベートはバッジ無し) | — |

---

## Admin Settings UI — Card Grouping & Accordion

`/admin > 設定` タブのレイアウト規約 (2026-06-02 確定)。

### Card のグループ単位

設定項目は **機能ドメイン単位で 1 枚の Card にまとめる**。違う機能の設定が追加される場合は **新しい Card に分ける**。

| Card | 含める設定 |
|---|---|
| **Commission 設定** | `commission_enabled` / `image_tag_presets` / `commission_item_visibility` ほか Commission に関わるもの全て |
| **将来追加例: アップロード設定** | (例) `max_file_size_mb` / `allowed_sample_rates` など → 新しい Card に |
| **将来追加例: 通知設定** | (例) `notification_email_enabled` など → 新しい Card に |

> なぜ: 1 枚の Card にすべて詰め込むと、`/admin > 設定` を開いた人が「どの機能の設定か」を識別しにくくなる。Card 単位で domain を区切ることで「Commission 周りの設定はこの Card にまとまっている」という mental model が成立する。

### Card 内の行レイアウト

各設定行は `commission_enabled` を基準形とする:

```
┌──────────────────────────────────────────────────┐
│ <key (font-mono)>                  <状態> <UI>   │
│ <description (text-muted)>                       │
└──────────────────────────────────────────────────┘
```

- key は `font-mono text-[12px] font-semibold`
- description は `text-[11px] text-muted`
- 右側: 状態ラベル ("有効/無効", "12 件", "3 項目 非表示") + 操作 UI (Boolean トグル or シェブロン)

### アコーディオン (折りたたみ)

行内コンテンツが**3 行以上 or chip 5 個以上**になる項目は **accordion 化** する:

- header 行は Boolean 行と同じ高さ・同じ右側構成 (状態サマリ + 回転シェブロン)
- click で展開、展開中は header 直下に `border-t border-hairline-soft bg-canvas-soft/60` の panel
- **1 つだけ展開する単選アコーディオン** がデフォルト (state は `expandedSettingKey: ref<string | null>`)
- 複数同時展開が必要な場合のみ Set 管理に切り替える

実装例: `image_tag_presets` (chip list + 追加入力)、`commission_item_visibility` (23 項目のトグル一覧)。

### 削除確認

「タグ削除」「設定リセット」など**取り消せない操作**は `ConfirmModal variant="danger"` を経由させる。クリック即削除は禁止。

### 押下フィードバック

「追加」「保存」などの能動操作ボタンは:
- 常時: `active:scale-95` で押下感
- 成功直後の 400ms: `bg-primary scale-95 shadow-inner` + ラベルに `✓` を一時表示

---

## Known Gaps

- CursorGothic is a licensed typeface; Inter is the substitute.
- Animation timings (timeline pill entrance, IDE pane reveal) out of scope.
- In-app surfaces (code editor, chat panel, agent timeline) only partially captured via marketing IDE mockups.
- Form validation states beyond focus not visible on captured surfaces.
