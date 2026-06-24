<template>
  <div class="message-list">
    <article v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
      <span>{{ message.role === 'user' ? '你' : 'LunaClaw' }}</span>
      <p>{{ message.content }}</p>

      <div v-if="message.retrieved_memories && message.retrieved_memories.length" class="memory-used">
        <small>本轮使用记忆</small>
        <small v-for="memory in message.retrieved_memories" :key="memory.memory_id">
          {{ memory.category }} / {{ memory.memory_id }}
        </small>
      </div>

      <div v-if="message.evolution_summary || (message.evolution_events && message.evolution_events.length)" class="evolution-used">
        <small>本轮优化</small>
        <small v-if="message.evolution_summary">{{ message.evolution_summary }}</small>
        <small v-for="event in message.evolution_events" :key="event.operation_id || event.timestamp">
          {{ event.operation }} / {{ event.target_type }}
        </small>
      </div>

      <div v-if="message.active_skills && message.active_skills.length" class="skill-used">
        <small>加载 Skill</small>
        <small v-for="skill in message.active_skills" :key="skill.skill_id">{{ skill.name }}</small>
      </div>
    </article>
    <article v-if="loading" class="message assistant">
      <span>LunaClaw</span>
      <p>思考中，正在检索相关记忆、加载 Skill 并组织回复...</p>
    </article>
  </div>
</template>

<script setup>
defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})
</script>
