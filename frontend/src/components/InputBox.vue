<template>
  <form class="input-box" @submit.prevent="submit">
    <textarea
      v-model="text"
      :disabled="disabled"
      rows="2"
      placeholder="和 LunaClaw 说点什么，比如：记住我最近在做 NLP 课程陪伴 Agent"
    />
    <button type="submit" :disabled="disabled || !text.trim()">发送</button>
  </form>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['send'])
const text = ref('')

function submit() {
  const value = text.value.trim()
  if (!value) return
  emit('send', value)
  text.value = ''
}
</script>
