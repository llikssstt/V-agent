<template>
  <div class="panel">
    <div class="panel-title">
      <h2>待办</h2>
      <button type="button" @click="$emit('refresh')">刷新</button>
    </div>
    <ul v-if="items.length" class="compact-list">
      <li v-for="item in items" :key="item.todo_id">
        <p>{{ item.content }}</p>
        <small>{{ item.done ? 'done' : 'open' }}</small>
      </li>
    </ul>
    <p v-else class="empty">暂无待办</p>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] }
})

defineEmits(['refresh'])
</script>

