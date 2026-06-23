<template>
  <div class="message-list">
    <article v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
      <span>{{ message.role === 'user' ? '你' : 'LunaClaw' }}</span>
      <p>{{ message.content }}</p>
      <div v-if="message.retrieved_memories && message.retrieved_memories.length" class="memory-used">
        <small>本次使用记忆</small>
        <small v-for="memory in message.retrieved_memories" :key="memory.memory_id">
          {{ memory.category }} / {{ memory.memory_id }}
        </small>
      </div>
    </article>
    <article v-if="loading" class="message assistant">
      <span>LunaClaw</span>
      <p>思考中，正在检索相关记忆并组织回复...</p>
    </article>
  </div>
</template>

<script setup>
defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})
</script>
