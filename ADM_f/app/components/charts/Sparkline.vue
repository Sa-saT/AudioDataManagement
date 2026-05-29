<script setup lang="ts">
import { computed } from 'vue'

interface Bucket { date: string; value: number }
interface Props {
  data: Bucket[]
  width?: number
  height?: number
  color?: string
  showAxis?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  width: 120,
  height: 30,
  color: 'currentColor',
  showAxis: false,
})

const maxV = computed(() => Math.max(1, ...props.data.map(d => d.value)))
const path = computed(() => {
  if (props.data.length === 0) return ''
  const W = props.width, H = props.height
  const step = W / Math.max(1, props.data.length - 1)
  return props.data.map((d, i) => {
    const x = i * step
    const y = H - (d.value / maxV.value) * (H - 2) - 1
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
})
const fillPath = computed(() => {
  if (!path.value) return ''
  return `${path.value} L ${props.width} ${props.height} L 0 ${props.height} Z`
})
const lastVal = computed(() => props.data[props.data.length - 1]?.value ?? 0)
const lastX = computed(() => props.data.length > 1 ? props.width : 0)
const lastY = computed(() =>
  props.height - (lastVal.value / maxV.value) * (props.height - 2) - 1
)
</script>

<template>
  <svg
    :width="props.width"
    :height="props.height"
    :viewBox="`0 0 ${props.width} ${props.height}`"
    class="overflow-visible"
  >
    <path :d="fillPath" :fill="props.color" fill-opacity="0.12" />
    <path :d="path" :stroke="props.color" stroke-width="1.2" fill="none" />
    <circle
      v-if="data.length > 0"
      :cx="lastX"
      :cy="lastY"
      r="1.8"
      :fill="props.color"
    />
  </svg>
</template>
