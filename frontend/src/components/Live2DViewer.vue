<template>
  <div class="live2d-panel" :style="{ '--accent': meta.color }">
    <div class="viewer-header">
      <span>小熙</span>
      <small>Live2DViewer placeholder</small>
    </div>
    <div class="avatar-orbit">
      <div class="avatar-face">{{ meta.face }}</div>
    </div>
    <div class="viewer-state">
      <strong>{{ meta.label }}</strong>
      <span>{{ meta.tone }}</span>
    </div>
    <code>{{ modelPath }}</code>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getEmotionMeta } from '../utils/emotionMap'

const props = defineProps({
  emotion: { type: String, default: 'neutral' },
  modelPath: { type: String, default: '' }
})

const meta = computed(() => getEmotionMeta(props.emotion))
</script>

