<template>
  <div class="chat-box">
    <header>
      <div>
        <h1>LunaClaw 陪伴 Agent</h1>
        <p>两阶段 LLM 决策、语义记忆、工具调用与可解释自我优化</p>
      </div>
    </header>
    <MessageList :messages="messages" :loading="loading" />
    <InputBox :disabled="loading" @send="$emit('send', $event)" />
  </div>
</template>

<script setup>
import InputBox from './InputBox.vue'
import MessageList from './MessageList.vue'

defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})

defineEmits(['send'])
</script>
