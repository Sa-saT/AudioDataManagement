<script setup lang="ts">
import { computed } from 'vue'

interface Bucket { date: string; value: number }
interface Props {
  data: Bucket[]
  label?: string
  color?: string
  height?: number
}
const props = withDefaults(defineProps<Props>(), {
  label: '',
  color: '#20b2aa',
  height: 120,
})

const W = 480  // viewBox 幅。CSS で実幅は親に追従
const padL = 6, padR = 6, padT = 8, padB = 18

const max = computed(() => Math.max(1, ...props.data.map(d => d.value)))
const innerW = computed(() => W - padL - padR)
const innerH = computed(() => props.height - padT - padB)
const gap = 2
const barW = computed(() =>
  Math.max(1, (innerW.value - gap * Math.max(0, props.data.length - 1)) / props.data.length)
)

function barX(i: number): number {
  return padL + i * (barW.value + gap)
}
function barY(v: number): number {
  return padT + innerH.value - (v / max.value) * innerH.value
}
function barH(v: number): number {
  return (v / max.value) * innerH.value
}

// X-axis labels: 表示する日付インデックス (最初・中央・末尾 + 適度な間隔)
const labelIdx = computed(() => {
  const n = props.data.length
  if (n <= 6) return Array.from({ length: n }, (_, i) => i)
  const step = Math.ceil(n / 5)
  const ids: number[] = []
  for (let i = 0; i < n; i += step) ids.push(i)
  if (ids[ids.length - 1] !== n - 1) ids.push(n - 1)
  return ids
})

function shortDate(s: string): string {
  // "2026-05-29" → "5/29"
  const parts = s.split('-')
  if (parts.length === 3) return `${Number(parts[1])}/${Number(parts[2])}`
  return s
}
</script>

<template>
  <svg
    :viewBox="`0 0 ${W} ${props.height}`"
    :height="props.height"
    width="100%"
    preserveAspectRatio="none"
    class="block"
  >
    <!-- Bars -->
    <g>
      <rect
        v-for="(d, i) in props.data"
        :key="d.date"
        :x="barX(i)"
        :y="barY(d.value)"
        :width="barW"
        :height="barH(d.value)"
        :fill="props.color"
        rx="1"
      >
        <title>{{ d.date }}: {{ d.value }}</title>
      </rect>
    </g>
    <!-- Baseline -->
    <line
      :x1="padL" :x2="W - padR"
      :y1="padT + innerH"
      :y2="padT + innerH"
      stroke="#0001" stroke-width="0.5"
    />
    <!-- X-axis labels -->
    <g>
      <text
        v-for="i in labelIdx"
        :key="`l-${i}`"
        :x="barX(i) + barW / 2"
        :y="props.height - 4"
        text-anchor="middle"
        font-family="ui-monospace, monospace"
        font-size="9"
        fill="#0006"
      >{{ shortDate(props.data[i]?.date ?? '') }}</text>
    </g>
  </svg>
</template>
