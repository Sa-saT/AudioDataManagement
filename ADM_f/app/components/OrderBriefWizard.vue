<script setup lang="ts">
import { ref, computed } from 'vue'

export interface OrderBrief {
  // Step 1
  sound_type: 'bgm' | 'se' | 'both' | ''
  purpose: 'game' | 'video' | 'podcast' | 'other' | ''
  purpose_note: string
  length_sec: number | null
  // Step 2 — BGM
  bgm_scenes: string[]
  bgm_loop: boolean
  bgm_note: string
  // Step 2 — SE
  se_trigger: string
  se_functions: string[]
  // Step 3 — Emotional
  emotions_target: string[]
  emotions_avoid: string[]
  memory_impression: string
  // Step 4 — Texture (3-way: 'a' | 'mid' | 'b' | '')
  tx_organic_electronic: 'organic' | 'mid' | 'electronic' | ''
  tx_melody_rhythm: 'melody' | 'mid' | 'rhythm' | ''
  tx_warm_cold: 'warm' | 'mid' | 'cold' | ''
  tx_sparse_dense: 'sparse' | 'mid' | 'dense' | ''
  tx_static_dynamic: 'static' | 'mid' | 'dynamic' | ''
  // Step 5 — Reference
  reference_urls: string
  reference_elements: string[]
  reference_avoid: string
  // Step 6 — Technical
  delivery_format: 'wav48k24b' | 'wav44k16b' | 'any' | ''
  deadline: string
  budget_range: '5000' | '10000' | 'negotiable' | ''
  note: string
}

const emit = defineEmits<{
  (e: 'submit', payload: { title: string; token_cost: number; brief: OrderBrief }): void
  (e: 'cancel'): void
}>()

const TOTAL_STEPS = 6
const step = ref(1)
const title = ref('')
const token_cost = ref(100)

const brief = ref<OrderBrief>({
  sound_type: '',
  purpose: '',
  purpose_note: '',
  length_sec: null,
  bgm_scenes: [],
  bgm_loop: false,
  bgm_note: '',
  se_trigger: '',
  se_functions: [],
  emotions_target: [],
  emotions_avoid: [],
  memory_impression: '',
  tx_organic_electronic: '',
  tx_melody_rhythm: '',
  tx_warm_cold: '',
  tx_sparse_dense: '',
  tx_static_dynamic: '',
  reference_urls: '',
  reference_elements: [],
  reference_avoid: '',
  delivery_format: '',
  deadline: '',
  budget_range: '',
  note: '',
})

// ─── Validation ───────────────────────────────────────
const errors = ref<Record<string, string>>({})

function clearErrors() { errors.value = {} }

function validateStep1(): boolean {
  clearErrors()
  if (!title.value.trim()) errors.value.title = 'タイトルを入力してください'
  if (!brief.value.sound_type) errors.value.sound_type = 'サウンドタイプを選択してください'
  if (!brief.value.purpose) errors.value.purpose = '用途を選択してください'
  if (!brief.value.length_sec || brief.value.length_sec <= 0) errors.value.length = '長さを入力してください (1秒以上)'
  return Object.keys(errors.value).length === 0
}

function validateStep2(): boolean {
  clearErrors()
  const t = brief.value.sound_type
  if ((t === 'bgm' || t === 'both') && brief.value.bgm_scenes.length === 0) {
    errors.value.bgm_scenes = 'シーンを1つ以上選択してください'
  }
  if ((t === 'se' || t === 'both') && !brief.value.se_trigger.trim()) {
    errors.value.se_trigger = 'SEのトリガーとなるアクションを入力してください'
  }
  return Object.keys(errors.value).length === 0
}

function validateStep3(): boolean {
  clearErrors()
  if (brief.value.emotions_target.length === 0) {
    errors.value.emotions_target = '狙う感情を1つ以上選択してください'
  }
  return Object.keys(errors.value).length === 0
}

// ─── Navigation ───────────────────────────────────────
function next() {
  if (step.value === 1 && !validateStep1()) return
  if (step.value === 2 && !validateStep2()) return
  if (step.value === 3 && !validateStep3()) return
  clearErrors()
  step.value++
}

function prev() {
  clearErrors()
  step.value--
}

function skip() {
  clearErrors()
  step.value++
}

function handleSubmit() {
  emit('submit', { title: title.value.trim(), token_cost: token_cost.value, brief: brief.value })
}

// ─── Toggle helpers ────────────────────────────────────
function toggleArr(arr: string[], val: string) {
  const idx = arr.indexOf(val)
  if (idx === -1) arr.push(val)
  else arr.splice(idx, 1)
}

// ─── Display data ──────────────────────────────────────
const BGM_SCENES = [
  { v: 'battle', l: 'バトル / 戦闘' },
  { v: 'boss', l: 'ボス戦' },
  { v: 'explore', l: '探索 / フィールド' },
  { v: 'menu', l: 'メニュー / UI' },
  { v: 'title', l: 'タイトル画面' },
  { v: 'event', l: 'イベント / ムービー' },
  { v: 'ending', l: 'エンディング' },
  { v: 'ambient', l: 'アンビエント / 環境音' },
  { v: 'other', l: 'その他' },
]

const SE_FUNCTIONS = [
  { v: 'success', l: '成功 / 達成通知' },
  { v: 'danger', l: '危険 / 警告' },
  { v: 'ui', l: 'UI操作 / 確認' },
  { v: 'operation', l: '操作の手応え' },
  { v: 'immersion', l: '没入 / 演出' },
  { v: 'character', l: 'キャラクター感情' },
]

// 狙う感情 / 避ける感情で共有
const EMOTIONS = [
  { v: 'excitement', l: '高揚感 / 興奮' },
  { v: 'tension', l: '緊張感' },
  { v: 'fear', l: '恐怖 / 不安' },
  { v: 'relief', l: '安らぎ / 安心' },
  { v: 'loneliness', l: '孤独感' },
  { v: 'grandeur', l: '壮大さ / 圧倒感' },
  { v: 'speed', l: '疾走感' },
  { v: 'sadness', l: '哀愁 / 切なさ' },
  { v: 'mystery', l: '神秘 / 異世界感' },
  { v: 'achievement', l: '達成感 / 充足感' },
  { v: 'heaviness', l: '重厚感 / 威圧感' },
  { v: 'comfort', l: '心地よさ / まったり感' },
  { v: 'euphoria', l: '爽快感' },
  { v: 'dread', l: 'じわじわとした恐怖' },
  { v: 'wonder', l: '驚き / 発見の喜び' },
]

const REFERENCE_ELEMENTS = [
  { v: 'atmosphere', l: '全体の空気感 / 雰囲気' },
  { v: 'bass', l: '低音 / ベース感' },
  { v: 'progression', l: '展開 / 構成' },
  { v: 'tempo', l: 'テンポ / グルーヴ' },
  { v: 'timbre', l: '音色 / サウンドデザイン' },
  { v: 'melody', l: 'メロディライン' },
  { v: 'rhythm', l: 'リズムパターン' },
  { v: 'density', l: '音の密度 / 空間感' },
]

// ─── Texture axis helper ───────────────────────────────
type TxKey = keyof Pick<OrderBrief,
  'tx_organic_electronic' | 'tx_melody_rhythm' |
  'tx_warm_cold' | 'tx_sparse_dense' | 'tx_static_dynamic'>

const TEXTURE_AXES: Array<{ key: TxKey; a: string; aVal: string; b: string; bVal: string; mid: string }> = [
  { key: 'tx_organic_electronic', a: '有機的 / 生楽器', aVal: 'organic', b: '電子的 / シンセ', bVal: 'electronic', mid: 'どちらでも' },
  { key: 'tx_melody_rhythm',      a: 'メロディ重視',   aVal: 'melody',   b: 'リズム重視',    bVal: 'rhythm',     mid: 'どちらでも' },
  { key: 'tx_warm_cold',          a: '温かい / 柔らかい', aVal: 'warm',   b: '冷たい / 無機質', bVal: 'cold',      mid: 'どちらでも' },
  { key: 'tx_sparse_dense',       a: 'シンプル / 余白',  aVal: 'sparse', b: '重厚 / 音が多い',  bVal: 'dense',    mid: 'どちらでも' },
  { key: 'tx_static_dynamic',     a: '静的 / 落ち着いた', aVal: 'static', b: '激しい / 展開多い', bVal: 'dynamic', mid: 'どちらでも' },
]

function setTx(key: TxKey, val: string) {
  const b = brief.value as Record<string, unknown>
  b[key] = b[key] === val ? '' : val
}

// ─── Progress ─────────────────────────────────────────
const progressPercent = computed(() => (step.value / TOTAL_STEPS) * 100)

// ─── Summary helpers ──────────────────────────────────
const SOUND_TYPE_L: Record<string, string> = { bgm: 'BGM', se: 'SE', both: 'BGM + SE' }
const PURPOSE_L: Record<string, string> = { game: 'ゲーム', video: '映像', podcast: 'ポッドキャスト', other: 'その他' }
const TX_L: Record<string, string> = {
  organic: '有機的', melody: 'メロディ重視', warm: '温かい', sparse: 'シンプル', static: '静的',
  mid: '—',
  electronic: '電子的', rhythm: 'リズム重視', cold: '冷たい', dense: '重厚', dynamic: '激しい',
}
const FORMAT_L: Record<string, string> = { wav48k24b: '48kHz/24bit', wav44k16b: '44.1kHz/16bit', any: 'どちらでも可' }
const BUDGET_L: Record<string, string> = { '5000': '〜¥5,000', '10000': '〜¥10,000', negotiable: '要相談' }

function emotionLabel(v: string) { return EMOTIONS.find(e => e.v === v)?.l ?? v }
function bgmSceneLabel(v: string) { return BGM_SCENES.find(s => s.v === v)?.l ?? v }
function seFunctionLabel(v: string) { return SE_FUNCTIONS.find(f => f.v === v)?.l ?? v }
function refElemLabel(v: string) { return REFERENCE_ELEMENTS.find(r => r.v === v)?.l ?? v }
</script>

<template>
  <div class="flex flex-col gap-0 w-full">

    <!-- Progress bar -->
    <div class="flex items-center gap-2 mb-5">
      <span class="text-[11px] text-ink/40 tabular-nums whitespace-nowrap">Step {{ step }} / {{ TOTAL_STEPS }}</span>
      <div class="flex-1 h-[3px] rounded-full bg-surface-2 overflow-hidden">
        <div
          class="h-full rounded-full bg-accent transition-all duration-300"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════
         Step 1: 基本情報
    ════════════════════════════════════════════════ -->
    <div v-if="step === 1" class="flex flex-col gap-5">
      <div>
        <p class="text-[13px] font-semibold text-ink">基本情報</p>
        <p class="text-[11px] text-ink/40 mt-0.5">まずどんなサウンドを作りたいか教えてください。</p>
      </div>

      <!-- タイトル -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">発注タイトル <span class="text-accent">*</span></label>
        <input
          v-model="title"
          type="text"
          placeholder="例: ダンジョンボス戦BGM"
          class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent"
          maxlength="100"
        />
        <p v-if="errors.title" class="mt-1 text-[11px] text-accent">{{ errors.title }}</p>
      </div>

      <!-- サウンドタイプ -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">サウンドタイプ <span class="text-accent">*</span></label>
        <div class="flex gap-2">
          <button
            v-for="opt in [{ v: 'bgm', l: 'BGM' }, { v: 'se', l: 'SE' }, { v: 'both', l: 'BGM + SE' }]"
            :key="opt.v"
            type="button"
            class="flex-1 py-2 rounded-lg text-[12px] font-medium border transition-colors"
            :class="brief.sound_type === opt.v
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            @click="brief.sound_type = opt.v as typeof brief.sound_type"
          >{{ opt.l }}</button>
        </div>
        <p v-if="errors.sound_type" class="mt-1 text-[11px] text-accent">{{ errors.sound_type }}</p>
      </div>

      <!-- 用途 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">用途 <span class="text-accent">*</span></label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="opt in [{ v: 'game', l: 'ゲーム' }, { v: 'video', l: '映像' }, { v: 'podcast', l: 'ポッドキャスト' }, { v: 'other', l: 'その他' }]"
            :key="opt.v"
            type="button"
            class="px-4 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.purpose === opt.v
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            @click="brief.purpose = opt.v as typeof brief.purpose"
          >{{ opt.l }}</button>
        </div>
        <input
          v-if="brief.purpose === 'other'"
          v-model="brief.purpose_note"
          type="text"
          placeholder="具体的な用途を入力"
          class="mt-2 w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <p v-if="errors.purpose" class="mt-1 text-[11px] text-accent">{{ errors.purpose }}</p>
      </div>

      <!-- 長さ -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">おおよその長さ (秒) <span class="text-accent">*</span></label>
        <div class="flex flex-wrap gap-2 mb-2">
          <button
            v-for="preset in [15, 30, 60, 90, 120, 180]"
            :key="preset"
            type="button"
            class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.length_sec === preset
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            @click="brief.length_sec = preset"
          >{{ preset }}s</button>
        </div>
        <div class="flex items-center gap-2">
          <input
            v-model.number="brief.length_sec"
            type="number"
            min="1"
            placeholder="カスタム"
            class="w-28 bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <span class="text-[12px] text-ink/40">秒</span>
        </div>
        <p v-if="errors.length" class="mt-1 text-[11px] text-accent">{{ errors.length }}</p>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════
         Step 2: シーン設計 (BGM) / 機能設計 (SE)
    ════════════════════════════════════════════════ -->
    <div v-else-if="step === 2" class="flex flex-col gap-5">
      <div>
        <p class="text-[13px] font-semibold text-ink">シーン / 機能設計</p>
        <p class="text-[11px] text-ink/40 mt-0.5">どんな場面で使われる音ですか？クリエイターが文脈を理解するために重要です。</p>
      </div>

      <!-- BGM section -->
      <template v-if="brief.sound_type === 'bgm' || brief.sound_type === 'both'">
        <div :class="brief.sound_type === 'both' ? 'border border-white/10 rounded-xl p-4' : ''">
          <p v-if="brief.sound_type === 'both'" class="text-[11px] font-semibold text-ink/50 tracking-widest uppercase mb-3">BGM</p>

          <!-- シーン選択 -->
          <div class="mb-4">
            <label class="block text-[12px] text-ink/60 mb-1.5">使用シーン <span class="text-accent">*</span></label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="s in BGM_SCENES"
                :key="s.v"
                type="button"
                class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
                :class="brief.bgm_scenes.includes(s.v)
                  ? 'bg-accent text-white border-accent'
                  : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
                @click="toggleArr(brief.bgm_scenes, s.v)"
              >{{ s.l }}</button>
            </div>
            <p v-if="errors.bgm_scenes" class="mt-1 text-[11px] text-accent">{{ errors.bgm_scenes }}</p>
          </div>

          <!-- ループ -->
          <div class="flex items-center gap-3 mb-4">
            <button
              type="button"
              class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
              :class="brief.bgm_loop ? 'bg-accent' : 'bg-surface-2 border border-white/20'"
              @click="brief.bgm_loop = !brief.bgm_loop"
            >
              <span
                class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                :class="brief.bgm_loop ? 'translate-x-4' : 'translate-x-0.5'"
              />
            </button>
            <span class="text-[12px] text-ink/60">ループ再生が必要</span>
            <span class="text-[11px] text-ink/40">{{ brief.bgm_loop ? 'ON' : 'OFF' }}</span>
          </div>

          <!-- 補足 -->
          <div>
            <label class="block text-[12px] text-ink/60 mb-1">シーン補足 (任意)</label>
            <textarea
              v-model="brief.bgm_note"
              rows="2"
              placeholder="例: バトル開始から30秒は緊張感を維持、その後サビへ。他シーンとの接続はフェードアウト。"
              class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
            />
          </div>
        </div>
      </template>

      <!-- SE section -->
      <template v-if="brief.sound_type === 'se' || brief.sound_type === 'both'">
        <div :class="brief.sound_type === 'both' ? 'border border-white/10 rounded-xl p-4' : ''">
          <p v-if="brief.sound_type === 'both'" class="text-[11px] font-semibold text-ink/50 tracking-widest uppercase mb-3">SE</p>

          <!-- トリガー -->
          <div class="mb-4">
            <label class="block text-[12px] text-ink/60 mb-1">何をしたときに鳴る音ですか？ <span class="text-accent">*</span></label>
            <input
              v-model="brief.se_trigger"
              type="text"
              placeholder="例: アイテムを拾ったとき / ボタンを押したとき / 敵を倒したとき"
              class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <p v-if="errors.se_trigger" class="mt-1 text-[11px] text-accent">{{ errors.se_trigger }}</p>
          </div>

          <!-- 機能 -->
          <div>
            <label class="block text-[12px] text-ink/60 mb-1.5">この音の役割 (複数可)</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="f in SE_FUNCTIONS"
                :key="f.v"
                type="button"
                class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
                :class="brief.se_functions.includes(f.v)
                  ? 'bg-accent text-white border-accent'
                  : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
                @click="toggleArr(brief.se_functions, f.v)"
              >{{ f.l }}</button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ═══════════════════════════════════════════════
         Step 3: 感情設計 (核心)
    ════════════════════════════════════════════════ -->
    <div v-else-if="step === 3" class="flex flex-col gap-5">
      <div>
        <p class="text-[13px] font-semibold text-ink">感情設計</p>
        <p class="text-[11px] text-ink/40 mt-0.5">ジャンルより感情が大切です。この音を聴いた人に何を感じさせたいですか？</p>
      </div>

      <!-- 狙う感情 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">
          狙う感情 <span class="text-accent">*</span>
          <span class="ml-2 font-normal text-ink/30">(複数可)</span>
        </label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="e in EMOTIONS"
            :key="e.v"
            type="button"
            class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.emotions_target.includes(e.v)
              ? 'bg-accent text-white border-accent'
              : brief.emotions_avoid.includes(e.v)
                ? 'opacity-30 cursor-not-allowed bg-surface-2 border-white/10'
                : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            :disabled="brief.emotions_avoid.includes(e.v)"
            @click="toggleArr(brief.emotions_target, e.v)"
          >{{ e.l }}</button>
        </div>
        <p v-if="errors.emotions_target" class="mt-1 text-[11px] text-accent">{{ errors.emotions_target }}</p>
      </div>

      <!-- 避けたい感情 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">
          避けたい感情
          <span class="ml-2 font-normal text-ink/30">(任意・複数可)</span>
        </label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="e in EMOTIONS"
            :key="e.v"
            type="button"
            class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.emotions_avoid.includes(e.v)
              ? 'bg-ink/60 text-white border-ink/60'
              : brief.emotions_target.includes(e.v)
                ? 'opacity-30 cursor-not-allowed bg-surface-2 border-white/10'
                : 'bg-surface-2 text-ink/60 border-white/10 hover:border-ink/30'"
            :disabled="brief.emotions_target.includes(e.v)"
            @click="toggleArr(brief.emotions_avoid, e.v)"
          >{{ e.l }}</button>
        </div>
      </div>

      <!-- 記憶に残したいイメージ -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1">
          聴いた後の記憶に残したいイメージ
          <span class="ml-2 font-normal text-ink/30">(任意)</span>
        </label>
        <p class="text-[11px] text-ink/30 mb-1.5">ジャンル名でなく、感覚 / 比喩 / 体験で表現してください。</p>
        <textarea
          v-model="brief.memory_impression"
          rows="3"
          placeholder="例: 「勝てる気がしない圧倒的な巨大感」「息を呑む静寂のあと一気に解放される感じ」「霧の中に光が差し込む希望」"
          class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
        />
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════
         Step 4: テクスチャ方向
    ════════════════════════════════════════════════ -->
    <div v-else-if="step === 4" class="flex flex-col gap-5">
      <div>
        <p class="text-[13px] font-semibold text-ink">サウンドテクスチャ</p>
        <p class="text-[11px] text-ink/40 mt-0.5">音の質感・方向性を5つの軸で選んでください。スキップ可能です。</p>
      </div>

      <div class="flex flex-col gap-4">
        <div v-for="axis in TEXTURE_AXES" :key="axis.key">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-[12px] text-ink/50">{{ axis.a }}</span>
            <span class="text-[12px] text-ink/50">{{ axis.b }}</span>
          </div>
          <div class="grid grid-cols-3 rounded-xl overflow-hidden border border-white/10 text-[11px]">
            <button
              type="button"
              class="py-2 text-center transition-colors"
              :class="(brief[axis.key] as string) === axis.aVal
                ? 'bg-accent text-white font-medium'
                : 'bg-surface-2 text-ink/50 hover:bg-surface-2/80'"
              @click="setTx(axis.key, axis.aVal)"
            >{{ axis.a.split(' / ')[0] }}</button>
            <button
              type="button"
              class="py-2 text-center border-x border-white/10 transition-colors"
              :class="(brief[axis.key] as string) === 'mid'
                ? 'bg-accent/30 text-ink font-medium'
                : 'bg-surface-2/50 text-ink/30 hover:bg-surface-2/70'"
              @click="setTx(axis.key, 'mid')"
            >{{ axis.mid }}</button>
            <button
              type="button"
              class="py-2 text-center transition-colors"
              :class="(brief[axis.key] as string) === axis.bVal
                ? 'bg-accent text-white font-medium'
                : 'bg-surface-2 text-ink/50 hover:bg-surface-2/80'"
              @click="setTx(axis.key, axis.bVal)"
            >{{ axis.b.split(' / ')[0] }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════
         Step 5: 参考音源
    ════════════════════════════════════════════════ -->
    <div v-else-if="step === 5" class="flex flex-col gap-5">
      <div>
        <p class="text-[13px] font-semibold text-ink">参考音源</p>
        <p class="text-[11px] text-ink/40 mt-0.5">参考曲そのものでなく「何を参考にしたいか」まで教えると、クリエイターに正確に伝わります。</p>
      </div>

      <!-- 参考URL -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1">参考音源 URL (1行に1URL)</label>
        <textarea
          v-model="brief.reference_urls"
          rows="3"
          placeholder="YouTube / SoundCloud / Spotify 等のURL"
          class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
        />
      </div>

      <!-- 参考にしたい要素 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">参考にしたい要素 (複数可)</label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="r in REFERENCE_ELEMENTS"
            :key="r.v"
            type="button"
            class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.reference_elements.includes(r.v)
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            @click="toggleArr(brief.reference_elements, r.v)"
          >{{ r.l }}</button>
        </div>
      </div>

      <!-- 避けたい要素 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1">逆に避けたい要素・表現</label>
        <textarea
          v-model="brief.reference_avoid"
          rows="2"
          placeholder="例: 明るいメジャー調は避けたい / ドラムは使わないでほしい / ボーカルなし"
          class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
        />
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════
         Step 6: 技術仕様 + 確認
    ════════════════════════════════════════════════ -->
    <div v-else-if="step === 6" class="flex flex-col gap-5">
      <div>
        <p class="text-[13px] font-semibold text-ink">技術仕様・予算</p>
        <p class="text-[11px] text-ink/40 mt-0.5">最後に納品条件と予算を確認してください。</p>
      </div>

      <!-- 納品形式 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">納品形式</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="opt in [{ v: 'wav48k24b', l: '48kHz / 24bit' }, { v: 'wav44k16b', l: '44.1kHz / 16bit' }, { v: 'any', l: 'どちらでも可' }]"
            :key="opt.v"
            type="button"
            class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.delivery_format === opt.v
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            @click="brief.delivery_format = brief.delivery_format === opt.v ? '' : opt.v as typeof brief.delivery_format"
          >{{ opt.l }}</button>
        </div>
      </div>

      <!-- 締切 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1">希望締切日</label>
        <input
          v-model="brief.deadline"
          type="date"
          class="bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </div>

      <!-- 予算感 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1.5">予算感</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="opt in [{ v: '5000', l: '〜¥5,000' }, { v: '10000', l: '〜¥10,000' }, { v: 'negotiable', l: '要相談' }]"
            :key="opt.v"
            type="button"
            class="px-3 py-1.5 rounded-full text-[12px] border transition-colors"
            :class="brief.budget_range === opt.v
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-ink/60 border-white/10 hover:border-accent/50'"
            @click="brief.budget_range = brief.budget_range === opt.v ? '' : opt.v as typeof brief.budget_range"
          >{{ opt.l }}</button>
        </div>
      </div>

      <!-- token -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1">使用 token 数 <span class="text-accent">*</span></label>
        <div class="flex items-center gap-2">
          <input
            v-model.number="token_cost"
            type="number"
            min="1"
            class="w-28 bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <span class="text-[12px] text-ink/40">tk (完了時に消費 / Admin が変更可)</span>
        </div>
      </div>

      <!-- 補足 -->
      <div>
        <label class="block text-[12px] text-ink/60 mb-1">その他補足・要望</label>
        <textarea
          v-model="brief.note"
          rows="3"
          placeholder="クリエイターへの補足、こだわり、禁止事項、ゲームエンジン (Unity/Unreal) など"
          class="w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
        />
      </div>

      <!-- Summary -->
      <div class="rounded-xl border border-white/10 bg-surface-2/40 px-4 py-3 space-y-1.5 text-[12px]">
        <p class="text-[11px] font-semibold text-ink/40 tracking-widest uppercase mb-2">確認</p>
        <p><span class="text-ink/40 w-20 inline-block">タイトル</span><span class="text-ink">{{ title }}</span></p>
        <p><span class="text-ink/40 w-20 inline-block">タイプ</span><span class="text-ink">{{ SOUND_TYPE_L[brief.sound_type] }} / {{ PURPOSE_L[brief.purpose] }}{{ brief.purpose_note ? ` (${brief.purpose_note})` : '' }}</span></p>
        <p><span class="text-ink/40 w-20 inline-block">長さ</span><span class="text-ink">{{ brief.length_sec }}秒</span></p>
        <p v-if="brief.bgm_scenes.length"><span class="text-ink/40 w-20 inline-block">シーン</span><span class="text-ink">{{ brief.bgm_scenes.map(bgmSceneLabel).join(', ') }}</span></p>
        <p v-if="brief.se_trigger"><span class="text-ink/40 w-20 inline-block">SEトリガー</span><span class="text-ink">{{ brief.se_trigger }}</span></p>
        <p v-if="brief.emotions_target.length"><span class="text-ink/40 w-20 inline-block">狙う感情</span><span class="text-ink">{{ brief.emotions_target.map(emotionLabel).join(', ') }}</span></p>
        <p v-if="brief.memory_impression"><span class="text-ink/40 w-20 inline-block">イメージ</span><span class="text-ink">{{ brief.memory_impression }}</span></p>
        <p v-if="brief.reference_elements.length"><span class="text-ink/40 w-20 inline-block">参考要素</span><span class="text-ink">{{ brief.reference_elements.map(refElemLabel).join(', ') }}</span></p>
      </div>
    </div>

    <!-- ─── Navigation ─────────────────────────────────── -->
    <div class="flex items-center justify-between mt-6 pt-4 border-t border-white/10">
      <button
        v-if="step > 1"
        type="button"
        class="px-4 py-2 text-[13px] text-ink/50 hover:text-ink transition-colors"
        @click="prev"
      >← 戻る</button>
      <button
        v-else
        type="button"
        class="px-4 py-2 text-[13px] text-ink/30 hover:text-ink/60 transition-colors"
        @click="emit('cancel')"
      >キャンセル</button>

      <div class="flex items-center gap-2">
        <!-- skip (step 4, 5 only) -->
        <button
          v-if="step === 4 || step === 5"
          type="button"
          class="px-3 py-2 text-[12px] text-ink/30 hover:text-ink/60 transition-colors"
          @click="skip"
        >スキップ</button>

        <button
          v-if="step < TOTAL_STEPS"
          type="button"
          class="px-5 py-2 bg-accent hover:bg-accent/80 text-white text-[13px] rounded-lg font-medium transition-colors"
          @click="next"
        >次へ →</button>
        <button
          v-else
          type="button"
          class="px-5 py-2 bg-accent hover:bg-accent/80 text-white text-[13px] rounded-lg font-medium transition-colors"
          @click="handleSubmit"
        >下書き保存</button>
      </div>
    </div>

  </div>
</template>
