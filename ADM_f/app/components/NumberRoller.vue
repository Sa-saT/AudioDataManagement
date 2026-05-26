<script setup lang="ts">
/**
 * vue-bits Counter の仕組みを依存なしで実装。
 * 各桁ごとに 0-9 を縦に並べ、value に応じて translateY するだけ。
 * 任意の桁数に対応 (digits prop)。
 */
interface Props {
  value: number
  digits?: number      // 表示する桁数
  fontSize?: number    // px
  textColor?: string
  fontWeight?: string | number
  durationMs?: number  // アニメーション時間
}

const props = withDefaults(defineProps<Props>(), {
  digits: 2,
  fontSize: 14,
  textColor: 'currentColor',
  fontWeight: 600,
  durationMs: 450,
})

const digitHeight = computed(() => Math.round(props.fontSize * 1.2))

const places = computed(() =>
  Array.from({ length: props.digits }, (_, i) =>
    Math.pow(10, props.digits - 1 - i),
  ),
)

const currentDigits = computed(() =>
  places.value.map((p) => Math.floor(Math.abs(props.value) / p) % 10),
)
</script>

<template>
  <div
    class="inline-flex tabular-nums leading-none"
    :style="{ fontSize: `${fontSize}px`, color: textColor, fontWeight }"
  >
    <div
      v-for="(_, i) in places"
      :key="i"
      class="relative overflow-hidden"
      :style="{ width: '1ch', height: `${digitHeight}px` }"
    >
      <div
        class="ease-[cubic-bezier(0.34,1.56,0.64,1)]"
        :style="{
          transform: `translateY(-${currentDigits[i] * digitHeight}px)`,
          transition: `transform ${durationMs}ms cubic-bezier(0.34,1.56,0.64,1)`,
        }"
      >
        <div
          v-for="n in 10"
          :key="n - 1"
          class="flex items-center justify-center"
          :style="{ height: `${digitHeight}px` }"
        >{{ n - 1 }}</div>
      </div>
    </div>
  </div>
</template>
