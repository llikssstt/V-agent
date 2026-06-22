<template>
  <div class="panel">
    <div class="panel-title">
      <h2>长期记忆</h2>
      <button type="button" @click="$emit('refresh')">刷新</button>
    </div>
    <ul v-if="items.length" class="compact-list">
      <li v-for="item in items" :key="item.memory_id">
        <p>{{ item.content }}</p>
        <small>{{ item.category }} / {{ item.importance }}</small>
        <button type="button" @click="$emit('delete', item.memory_id)">删除</button>
      </li>
    </ul>
    <p v-else class="empty">暂无记忆</p>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] }
})

defineEmits(['refresh', 'delete'])
</script>

