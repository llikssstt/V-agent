<template>
  <div class="panel status-panel">
    <h2>状态面板</h2>
    <dl>
      <div>
        <dt>emotion</dt>
        <dd>{{ status.emotion }}</dd>
      </div>
      <div>
        <dt>tool_used</dt>
        <dd>{{ status.tool_used }}</dd>
      </div>
      <div>
        <dt>memory_action</dt>
        <dd>{{ status.memory_action }}</dd>
      </div>
      <div>
        <dt>skills_used</dt>
        <dd>{{ status.skills_used.join(', ') }}</dd>
      </div>
      <div>
        <dt>active_skills</dt>
        <dd>{{ (status.active_skills || []).map((skill) => skill.name || skill.skill_id).join(', ') || 'none' }}</dd>
      </div>
      <div>
        <dt>evolution_count</dt>
        <dd>{{ status.evolution_count || 0 }}</dd>
      </div>
    </dl>
  </div>
</template>

<script setup>
defineProps({
  status: { type: Object, required: true }
})
</script>
