<template>
  <div class="message-list">
    <article v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
      <span>{{ message.role === 'user' ? '你' : '小熙' }}</span>
      <p>{{ message.content }}</p>
    </article>
    <article v-if="loading" class="message assistant">
      <span>小熙</span>
      <p>思考中，正在把这条消息拆成能处理的小块...</p>
    </article>
  </div>
</template>

<script setup>
defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})
</script>

