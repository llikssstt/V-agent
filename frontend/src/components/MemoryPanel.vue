<template>
  <div class="panel">
    <div class="panel-title">
      <h2>长期记忆</h2>
      <button type="button" @click="$emit('refresh')">刷新</button>
    </div>

    <form class="memory-form" @submit.prevent="submit">
      <textarea v-model="content" rows="2" placeholder="手动写入一条记忆，例如：用户正在准备 NLP 课程报告" />
      <select v-model="category">
        <option value="project">project</option>
        <option value="interaction_style">interaction_style</option>
        <option value="learning_goal">learning_goal</option>
        <option value="preference">preference</option>
        <option value="todo">todo</option>
        <option value="user_profile">user_profile</option>
      </select>
      <button type="submit" :disabled="!content.trim()">写入</button>
    </form>

    <ul v-if="items.length" class="compact-list">
      <li v-for="item in items" :key="item.memory_id">
        <p>{{ item.content }}</p>
        <small>{{ item.category }} / {{ item.importance }} / {{ item.memory_id }}</small>
        <button type="button" @click="$emit('delete', item.memory_id)">删除</button>
      </li>
    </ul>
    <p v-else class="empty">暂无记忆</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  items: { type: Array, default: () => [] }
})

const emit = defineEmits(['refresh', 'delete', 'create'])
const content = ref('')
const category = ref('project')

function submit() {
  const value = content.value.trim()
  if (!value) return
  emit('create', {
    content: value,
    category: category.value,
    importance: 0.8,
    source: 'manual'
  })
  content.value = ''
}
</script>
