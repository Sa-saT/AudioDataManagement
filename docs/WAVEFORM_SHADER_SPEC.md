# Waveform Shader 仕様

wavesurfer.js を廃止し、自前の **WebGL Fragment Shader** で波形を描画する。
同時にサーバ側 peaks を **DAW 品質** (max / min / RMS の3チャンネル) に拡張する。

> 最終更新: 2026-05-30 (策定)  
> 実装状態: **未実装** (Phase 3 残スコープに追加)

---

## 1. 目的

| # | 目的 | 効果 |
|---|---|---|
| G-01 | 「Max張り付き」の解消 | 現在 peaks は単一ピーク + 線形 → 圧縮音源で平坦に見える問題を解消 |
| G-02 | DAW 品質の表示 | RMS 中央濃色帯 + Peak 外側 = Logic / Pro Tools 風 |
| G-03 | バンドル削減 | wavesurfer.js (~90KB) を撤去 |
| G-04 | ブランド差別化 | washi / turquoise / tomato を活かしたシェーダー演出 |
| G-05 | プロ向け信頼性 | 「ちゃんと波形が見える」= ADM の "Professional" 訴求と整合 |

---

## 2. 現状と問題

### 2.1 現状

| レイヤ | 実装 |
|---|---|
| Server | `compute_peaks(path, num_points=200)` → `list[float]` (max ピークのみ、線形正規化) |
| DB | `audios.peaks JSONB` (number[] 200 要素) |
| Client | `WaveformPlayer.vue` が wavesurfer.js で描画 |
| 描画式 | 線形 (peak そのまま 0..1 → 高さに反映) |

### 2.2 「Max張り付き」の原因

1. **マスタリング圧縮**: 現代音源はリミッターで -1dB 近辺に張り付く → peaks がほぼ 0.95-1.0
2. **線形スケール**: 人間の聴覚は対数。線形ではダイナミックレンジが潰れる
3. **単一値**: RMS (実効エネルギー) を持たないので、内部の凹凸が見えない
4. **粗い解像度**: 200 ポイントでは bucket あたりサンプル数が多く、max が常に大きい

---

## 3. データレイヤ仕様 (server)

### 3.1 新 peaks フォーマット (v2)

```json
{
  "n": 1000,
  "max": [0.95, 0.87, ...],
  "min": [-0.93, -0.85, ...],
  "rms": [0.42, 0.38, ...]
}
```

| フィールド | 型 | 範囲 | 用途 |
|---|---|---|---|
| `n` | int | 1000 (固定) | 配列長 |
| `max` | float[n] | 0..1 | bucket あたりの最大値 (上端) |
| `min` | float[n] | -1..0 | bucket あたりの最小値 (下端) |
| `rms` | float[n] | 0..1 | bucket あたりの RMS (中央濃色帯) |

**設計判断:**

- **オブジェクト形** (3つの並列配列) を採用。array-of-triples (`[[max,min,rms],...]`) より JSON 可読性◎ + 将来フィールド追加が容易
- **n=1000** に増加 (現状 200)。1000なら 1px ごとに 1 bucket レベルの解像度 (480px 表示で十分)
- **DC オフセット保持** のため min も別に記録 (mirror で代用しない)
- **正規化**: ファイル単位の絶対 max ではなく **per-bucket** で計算後、ファイル全体の peak max に対して正規化 (現状と同じ思想だが、min/RMS も並行に持つ)

### 3.2 後方互換

`audios.peaks` の JSONB は型が動的なので **スキーマ変更不要**。判定:

```python
if isinstance(audio.peaks, dict) and "max" in audio.peaks:
    # v2 形式
else:
    # v1 (number[]) - migration で消滅予定
```

### 3.3 計算アルゴリズム (`compute_peaks_v2`)

```python
def compute_peaks_v2(path: Path, *, num_points: int = 1000) -> dict:
    data, _ = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)  # ステレオを mono に
    n = len(mono)
    chunk = max(1, n // num_points)

    out_max: list[float] = []
    out_min: list[float] = []
    out_rms: list[float] = []
    for i in range(0, n, chunk):
        seg = mono[i:i + chunk]
        if len(seg) == 0:
            continue
        out_max.append(float(seg.max()))
        out_min.append(float(seg.min()))
        out_rms.append(float(np.sqrt((seg ** 2).mean())))

    # ピーク値で正規化 (mirror 対称性は保つ)
    peak = max(max(out_max), -min(out_min)) or 1.0
    return {
        "n": len(out_max[:num_points]),
        "max": [round(v / peak, 4) for v in out_max[:num_points]],
        "min": [round(v / peak, 4) for v in out_min[:num_points]],
        "rms": [round(v / peak, 4) for v in out_rms[:num_points]],
    }
```

### 3.4 Migration (既存 audio の peaks 再計算)

Alembic migration `0011_peaks_v2_backfill`:

```python
def upgrade():
    # 既存 audios を全件読み込み、原本 wav から peaks v2 を再生成
    conn = op.get_bind()
    audio_ids = conn.execute("SELECT id FROM audios").fetchall()
    for (audio_id,) in audio_ids:
        path = Path(STORAGE_DIR) / f"{audio_id}.wav"
        if not path.exists():
            continue
        new_peaks = compute_peaks_v2(path)
        conn.execute(
            "UPDATE audios SET peaks = :p WHERE id = :id",
            {"p": json.dumps(new_peaks), "id": audio_id},
        )
```

**注意:** バックフィルが重いので、本番では別 CLI スクリプト推奨。ローカルなら migration で OK。

---

## 4. 描画レイヤ仕様 (client / Shader)

### 4.1 アーキテクチャ

```
┌────────────────── Vue Component ──────────────────┐
│ WaveformPlayer.vue                                │
│  ├─ <canvas> (WebGL2)                              │
│  ├─ uPeaksTexture: GPU 上の RGB テクスチャ          │
│  │    R = max, G = -min (positive), B = rms        │
│  ├─ uPlayPos: 0..1 (再生位置)                       │
│  ├─ uHoverPos: 0..1 / -1 (マウス位置)               │
│  └─ requestAnimationFrame ループ (再生中のみ)        │
└─────────────────────────────────────────────────────┘
```

### 4.2 WebGL 設定

| 項目 | 値 |
|---|---|
| Context | `webgl2` (フォールバック: `webgl`) |
| Precision | `highp float` |
| ジオメトリ | フルスクリーン三角形2枚 (quad) |
| テクスチャ形式 | `gl.RGB` / `gl.UNSIGNED_BYTE` (8bit = 256階調、見た目には十分) |
| テクスチャサイズ | `1000 × 1` (peaks.n × 1) |
| ループ | `cancelAnimationFrame` で停止可能。再生中・ホバー中のみ動作 |

### 4.3 Vertex Shader

```glsl
#version 300 es
in vec2 aPos;
out vec2 vUv;
void main() {
    vUv = aPos * 0.5 + 0.5;     // [-1,1] → [0,1]
    gl_Position = vec4(aPos, 0.0, 1.0);
}
```

### 4.4 Fragment Shader

```glsl
#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

uniform sampler2D uPeaks;       // R=max, G=|min|, B=rms
uniform float uPlayPos;         // 0..1
uniform float uHoverPos;        // 0..1 or -1
uniform float uTime;            // sec, for animation
uniform float uGamma;           // ガンマ補正係数 (default 0.4)
uniform vec3 uWaveColor;        // 未再生側 (#807d72 washi)
uniform vec3 uProgressColor;    // 再生済側 (#40e0d0 turquoise)
uniform vec3 uRmsColor;         // RMS 帯 (#20b2aa darker turquoise)
uniform vec3 uHoverGlow;        // ホバー時の発光色

void main() {
    float x = vUv.x;
    float y = vUv.y * 2.0 - 1.0;     // -1..+1 (中央が0)

    // sampler2D の sampling (1D テクスチャを縦中央でサンプル)
    vec3 p = texture(uPeaks, vec2(x, 0.5)).rgb;
    float pMax = p.r;
    float pMin = -p.g;            // ストア時に |min| → 負に戻す
    float pRms = p.b;

    // 補正カーブ
    float corrMax = pow(pMax, uGamma);
    float corrMin = -pow(-pMin, uGamma);
    float corrRms = pow(pRms, uGamma);

    // bipolar envelope: y が [corrMin, corrMax] の範囲なら描画
    float envelope = step(corrMin, y) * step(y, corrMax);

    // RMS band: y が [-corrRms, +corrRms] なら濃色
    float rmsBand = step(-corrRms, y) * step(y, corrRms);

    // 色: 再生位置を境にグラデ
    vec3 baseColor = mix(uProgressColor, uWaveColor,
                         smoothstep(uPlayPos - 0.002, uPlayPos + 0.002, x));
    vec3 color = mix(baseColor, uRmsColor, rmsBand * 0.7);

    // ホバーグロー (パルス)
    if (uHoverPos >= 0.0) {
        float d = abs(x - uHoverPos);
        float pulse = (1.0 - smoothstep(0.0, 0.06, d))
                     * (0.6 + 0.4 * sin(uTime * 6.2832));  // 1Hz
        color += uHoverGlow * pulse * 0.4;
    }

    // 再生位置に細い縦カーソル
    float cursor = 1.0 - smoothstep(0.0, 0.0015, abs(x - uPlayPos));
    color = mix(color, vec3(1.0), cursor * 0.6);

    fragColor = vec4(color * envelope, envelope);
}
```

### 4.5 JS 側のテクスチャ生成

```ts
function uploadPeaks(gl: WebGL2RenderingContext, peaks: { max: number[]; min: number[]; rms: number[] }, tex: WebGLTexture) {
  const n = peaks.max.length
  const data = new Uint8Array(n * 3)
  for (let i = 0; i < n; i++) {
    data[i * 3]     = Math.round(Math.max(0, peaks.max[i]) * 255)
    data[i * 3 + 1] = Math.round(Math.max(0, -peaks.min[i]) * 255)
    data[i * 3 + 2] = Math.round(Math.max(0, peaks.rms[i]) * 255)
  }
  gl.bindTexture(gl.TEXTURE_2D, tex)
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, n, 1, 0, gl.RGB, gl.UNSIGNED_BYTE, data)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
}
```

---

## 5. コンポーネント API

### 5.1 Props (現状互換 + 拡張)

```ts
defineProps<{
  audioId: string
  peaks: PeaksV1 | PeaksV2     // 後方互換: number[] も受ける
  durationSec: number
  // 改修で追加:
  gamma?: number               // default 0.4
  showRms?: boolean            // default true
  paused?: boolean             // 外部制御用
}>()

type PeaksV1 = number[]
type PeaksV2 = { n: number; max: number[]; min: number[]; rms: number[] }
```

### 5.2 Events / Exposed

```ts
defineEmits<{
  (e: 'seek', sec: number): void
}>()
defineExpose({
  isPlaying: ComputedRef<boolean>
  toggle(): Promise<void>
})
```

### 5.3 v1 形式の互換ラッパー

```ts
function toPeaksV2(p: PeaksV1 | PeaksV2): PeaksV2 {
  if (Array.isArray(p)) {
    // v1 単一値配列 → max にコピー、min は対称、rms は半分の値で代用
    return {
      n: p.length,
      max: p,
      min: p.map(v => -v),
      rms: p.map(v => v * 0.5),
    }
  }
  return p
}
```

→ migration 完了前でも壊れない。

---

## 6. インタラクション

| 操作 | 振る舞い |
|---|---|
| クリック | `seekTo(x * durationSec)`。`uPlayPos` を即時更新 |
| ホバー | `uHoverPos = x`。離脱時 `uHoverPos = -1` |
| 再生中 | `requestAnimationFrame` で `uPlayPos` + `uTime` 更新 |
| 停止中・ホバーなし | フレームループ停止 (省電力) |
| `prefers-reduced-motion` | パルス・cursor アニメーション無効化 |

---

## 7. パフォーマンス

| 項目 | 見積もり |
|---|---|
| テクスチャアップロード | 一度だけ (mount 時)。1000×1×3 = 3KB |
| Fragment shader 計算 | ピクセル数 × 数十命令。480×48 = ~23k pixels → 60fps 余裕 |
| GPU メモリ | 数KB / Canvas |
| CPU | 再生中の `uPlayPos` 更新のみ。アイドル時 0% |
| バンドルサイズ | wavesurfer.js -90KB / 新規 ~6KB (生 GLSL + WebGL ラッパー) |

---

## 8. フォールバック

WebGL2 未対応 (旧 Safari 等) のとき:

| 優先 | 方式 |
|---|---|
| 1 | WebGL2 (主) |
| 2 | WebGL1 (GLSL ES 1.00 に書換版を同梱、`texture2D` ベース) |
| 3 | Canvas 2D (peaks を直接描画。RMS 帯 + ガンマ補正だけは保持) |

クライアントは初期化時に context 取得を試し、ダメなら Canvas 2D ヘルパー (`drawWaveformFallback`) を呼ぶ。

---

## 9. デザイントークン適用

| Uniform | Tailwind/CSS 変数 | 役割 |
|---|---|---|
| `uWaveColor` | `var(--color-muted)` | 未再生側のグレージュ |
| `uProgressColor` | `var(--color-primary)` (turquoise) | 再生済側 |
| `uRmsColor` | `var(--color-primary-active)` (darker turquoise) | RMS 中央帯 |
| `uHoverGlow` | `var(--color-accent)` (tomato) | ホバー時の発光 |

→ CSS 変数を `getComputedStyle` で取り、初期化時に uniform 送出。

---

## 10. ファイル構成 (新規)

```
ADM_f/app/components/
├─ WaveformPlayer.vue              ← 全面書換 (wavesurfer 撤去)
└─ waveform/                       ← 新設ディレクトリ
   ├─ shaders/
   │  ├─ waveform.vert.glsl
   │  └─ waveform.frag.glsl
   ├─ useWaveformGL.ts             ← WebGL ラッパー Composable
   └─ fallback2d.ts                ← Canvas 2D フォールバック
```

GLSL ファイルは Vite の `?raw` インポートで文字列として取り込む:
```ts
import vertSrc from './shaders/waveform.vert.glsl?raw'
import fragSrc from './shaders/waveform.frag.glsl?raw'
```

---

## 11. 実装スコープ (順序)

| # | タスク | 優先度 |
|---|---|---|
| W-01 | `compute_peaks_v2` をサーバに実装 + アップロード時に v2 を保存 | 高 |
| W-02 | migration 0011: 既存 audios の peaks を v2 へ backfill | 高 |
| W-03 | `useWaveformGL.ts` (WebGL コンテキスト管理 / プログラム生成 / uniform 設定) | 高 |
| W-04 | `waveform.vert.glsl` / `waveform.frag.glsl` 実装 | 高 |
| W-05 | `WaveformPlayer.vue` を全面書換 (wavesurfer 撤去) | 高 |
| W-06 | `toPeaksV2` 互換ラッパー (移行期間用) | 中 |
| W-07 | `fallback2d.ts` (Canvas 2D フォールバック) | 中 |
| W-08 | `prefers-reduced-motion` 対応 | 中 |
| W-09 | wavesurfer.js を `package.json` から削除 | 低 (最終) |

---

## 12. 受け入れ基準 (検収)

| # | 条件 |
|---|---|
| AC-01 | 既存音源 (圧縮済み楽曲) で**平坦バーでなく動きのある波形**になる |
| AC-02 | RMS の濃色帯が中央に表示される |
| AC-03 | 再生位置で turquoise / washi のグラデが切替わる |
| AC-04 | クリックで再生位置にシーク (現状と同じ操作感) |
| AC-05 | ホバーで控えめなパルス発光 |
| AC-06 | wavesurfer.js が bundle から消える |
| AC-07 | WebGL2 未対応環境で Canvas 2D に自動フォールバック |
| AC-08 | 60fps 維持 (Chrome DevTools Performance タブ確認) |
| AC-09 | `prefers-reduced-motion: reduce` でアニメーション停止 |

---

## 13. 未確定事項 / 将来拡張

| # | 内容 |
|---|---|
| W-F01 | **AnalyserNode 連動**: 再生中の FFT バンドを uniform で渡し、波形に音響リアクティブ効果 (光の脈動 / 色相シフト) |
| W-F02 | **2段表示**: 上段=peak エンベロープ / 下段=RMS (DAW スタイル) |
| W-F03 | **selection / loop region** UI (将来の編集機能) |
| W-F04 | **波形ズーム** (時間軸スケール変更) |
| W-F05 | peaks v3: ステレオ別保持 (L/R 個別バー) |
