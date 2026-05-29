<script setup lang="ts">
import { computed } from 'vue'

interface Axis { key: string; label: string; max: number }
interface Props {
  axes: Axis[]
  values: Record<string, number>
  medians?: Record<string, number>  // ランク中央値 (点線)
  size?: number
  color?: string
}
const props = withDefaults(defineProps<Props>(), {
  medians: () => ({}),
  size: 220,
  color: '#20b2aa',
})

const cx = computed(() => props.size / 2)
const cy = computed(() => props.size / 2)
const r = computed(() => props.size / 2 - 30)

function angle(i: number): number {
  return -Math.PI / 2 + (2 * Math.PI * i) / props.axes.length
}

function pointAt(i: number, ratio: number): [number, number] {
  const a = angle(i)
  return [
    cx.value + Math.cos(a) * r.value * ratio,
    cy.value + Math.sin(a) * r.value * ratio,
  ]
}

const gridPolygons = computed(() =>
  [0.25, 0.5, 0.75, 1].map(scale =>
    props.axes.map((_, i) => pointAt(i, scale).join(',')).join(' ')
  )
)

const valuePath = computed(() =>
  props.axes.map((ax, i) => {
    const v = Math.min((props.values[ax.key] ?? 0) / Math.max(ax.max, 1e-9), 1)
    return pointAt(i, v).join(',')
  }).join(' ')
)

const medianPath = computed(() => {
  if (Object.keys(props.medians).length === 0) return ''
  return props.axes.map((ax, i) => {
    const v = Math.min((props.medians[ax.key] ?? 0) / Math.max(ax.max, 1e-9), 1)
    return pointAt(i, v).join(',')
  }).join(' ')
})

function labelPos(i: number): [number, number] {
  const a = angle(i)
  return [
    cx.value + Math.cos(a) * (r.value + 14),
    cy.value + Math.sin(a) * (r.value + 14),
  ]
}
</script>

<template>
  <svg
    :viewBox="`0 0 ${props.size} ${props.size}`"
    :width="props.size"
    :height="props.size"
    class="block"
  >
    <!-- Grid -->
    <polygon
      v-for="(pts, idx) in gridPolygons"
      :key="`g-${idx}`"
      :points="pts"
      fill="none"
      stroke="#0001"
      stroke-width="0.7"
    />
    <!-- Axes -->
    <line
      v-for="(ax, i) in axes"
      :key="`ax-${ax.key}`"
      :x1="cx" :y1="cy"
      :x2="pointAt(i, 1)[0]" :y2="pointAt(i, 1)[1]"
      stroke="#0001"
      stroke-width="0.7"
    />
    <!-- Median (rank reference) -->
    <polygon
      v-if="medianPath"
      :points="medianPath"
      fill="none"
      stroke="#aaa"
      stroke-width="1"
      stroke-dasharray="3 3"
    />
    <!-- Value -->
    <polygon
      :points="valuePath"
      :fill="props.color"
      fill-opacity="0.18"
      :stroke="props.color"
      stroke-width="1.5"
    />
    <!-- Labels -->
    <text
      v-for="(ax, i) in axes"
      :key="`l-${ax.key}`"
      :x="labelPos(i)[0]"
      :y="labelPos(i)[1]"
      text-anchor="middle"
      dominant-baseline="middle"
      font-family="ui-sans-serif, system-ui, sans-serif"
      font-size="9.5"
      fill="#0008"
    >{{ ax.label }}</text>
  </svg>
</template>
