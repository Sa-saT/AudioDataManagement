<script setup lang="ts">
interface Props {
  signal: 'green' | 'yellow' | 'red'
  size?: number
}
const props = withDefaults(defineProps<Props>(), { size: 10 })

const colorMap = {
  green:  { fill: '#2ecc71', glow: '#2ecc7144' },
  yellow: { fill: '#f0a840', glow: '#f0a84044' },
  red:    { fill: '#e74c3c', glow: '#e74c3c44' },
} as const
</script>

<template>
  <span
    class="inline-block rounded-full"
    :style="{
      width: props.size + 'px',
      height: props.size + 'px',
      background: colorMap[props.signal].fill,
      boxShadow: `0 0 6px ${colorMap[props.signal].glow}`,
    }"
    :title="`signal: ${props.signal}`"
  />
</template>
