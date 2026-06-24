<template>
  <div class="panel evolution-panel">
    <div class="panel-title">
      <h2>自我优化</h2>
      <button type="button" @click="$emit('refresh')">刷新</button>
    </div>

    <section>
      <h3>已启用 Skill</h3>
      <ul v-if="skills.length" class="compact-list">
        <li v-for="skill in skills" :key="skill.skill_id">
          <p>{{ skill.name }}</p>
          <small>{{ skill.scenario }} / v{{ skill.version }} / 证据 {{ skill.evidence_count }}</small>
        </li>
      </ul>
      <p v-else class="empty">暂无自动沉淀 Skill</p>
    </section>

    <section>
      <h3>进化日志</h3>
      <ul v-if="logs.length" class="compact-list">
        <li v-for="entry in logs.slice().reverse().slice(0, 8)" :key="entry.operation_id">
          <p>{{ entry.operation }} / {{ entry.target_type }}</p>
          <small>{{ entry.reason || '无说明' }}</small>
          <button
            v-if="entry.result === 'success' && entry.operation !== 'rollback' && canRollback(entry)"
            type="button"
            @click="$emit('rollback', entry.operation_id)"
          >
            回滚
          </button>
        </li>
      </ul>
      <p v-else class="empty">暂无进化日志</p>
    </section>
  </div>
</template>

<script setup>
defineProps({
  logs: { type: Array, default: () => [] },
  skills: { type: Array, default: () => [] }
})

defineEmits(['refresh', 'rollback'])

function canRollback(entry) {
  return ['skill', 'preference', 'state'].includes(entry.target_type)
}
</script>
