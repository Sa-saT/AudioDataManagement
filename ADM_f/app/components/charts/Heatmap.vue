<script setup lang="ts">
import { computed } from 'vue'

interface Cell { weekday: number; hour: number; count: number }
interface Props {
  data: Cell[]
  color?: string
}
const props = withDefaults(defineProps<Props>(), { color: '#20b2aa' })

const WEEKDAY_L = ['月', '火', '水', '木', '金', '土', '日']
const CELL = 12
const GAP = 1
const LABEL_W = 18
const LABEL_H = 14
const GRID_W = 24 * (CELL + GAP)
const GRID_H = 7 * (CELL + GAP)
const W = LABEL_W + GRID_W
const H = LABEL_H + GRID_H

const max = computed(() => Math.max(1, ...props.data.map(c => c.count)))
const map = computed(() => {
  const m = new Map<string, number>()
  for (const c of props.data) m.set(`${c.weekday}-${c.hour}`, c.count)
  return m
})

function cellColor(weekday: number, hour: number): string {
  const v = map.value.get(`${weekday}-${hour}`) ?? 0
  if (v === 0) return '#0001'
  const alpha = 0.15 + 0.85 * (v / max.value)
  return `${props.color}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`
}

const HOURS_LABEL = [0, 6, 12, 18]
</script>

<template>
  <svg
    :viewBox="`0 0 ${W} ${H}`"
    width="100%"
    :height="H"
    preserveAspectRatio="xMidYMid meet"
    class="block"
  >
    <!-- Hour axis -->
    <g>
      <text
        v-for="h in HOURS_LABEL"
        :key="h"
        :x="LABEL_W + h * (CELL + GAP)"
        :y="LABEL_H - 4"
        font-family="ui-monospace, monospace"
        font-size="8"
        fill="#0006"
      >{{ h }}h</text>
    </g>
    <!-- Weekday labels + cells -->
    <g v-for="(_, wd) in WEEKDAY_L" :key="wd">
      <text
        :x="0"
        :y="LABEL_H + wd * (CELL + GAP) + CELL - 2"
        font-family="ui-monospace, monospace"
        font-size="9"
        fill="#0007"
      >{{ WEEKDAY_L[wd] }}</text>
      <rect
        v-for="h in 24"
        :key="`${wd}-${h - 1}`"
        :x="LABEL_W + (h - 1) * (CELL + GAP)"
        :y="LABEL_H + wd * (CELL + GAP)"
        :width="CELL"
        :height="CELL"
        :fill="cellColor(wd, h - 1)"
        rx="2"
      >
        <title>{{ WEEKDAY_L[wd] }} {{ h - 1 }}時: {{ map.get(`${wd}-${h - 1}`) ?? 0 }}回</title>
      </rect>
    </g>
  </svg>
</template>
