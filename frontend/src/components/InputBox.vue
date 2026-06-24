<template>
  <form class="input-box" @submit.prevent="submit">
    <textarea
      v-model="text"
      :disabled="disabled"
      rows="2"
      placeholder="和 LunaClaw 说点什么，比如：我压力好大，今晚不想学了"
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
