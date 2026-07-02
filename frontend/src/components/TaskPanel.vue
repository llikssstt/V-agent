<template>
  <section class="panel task-panel">
    <div class="panel-title">
      <div>
        <h2>Tasks</h2>
        <small>{{ tasks.length }} tracked - scheduler {{ scheduler.running ? 'running' : 'stopped' }}</small>
      </div>
      <button @click="$emit('refresh')">Refresh</button>
    </div>

    <div class="skill-actions">
      <button v-if="scheduler.running" @click="$emit('scheduler-stop')">Stop Scheduler</button>
      <button v-else @click="$emit('scheduler-start')">Start Scheduler</button>
      <button :disabled="!scheduler.running" @click="$emit('scheduler-tick')">Tick</button>
    </div>
    <small v-if="scheduler.last_tick">Last tick {{ scheduler.last_tick }}</small>

    <ul v-if="tasks.length" class="compact-list">
      <li v-for="task in tasks" :key="task.task_id">
        <strong>{{ task.title }}</strong>
        <small>{{ task.status }} - {{ task.task_id }}</small>
        <small>{{ completedSteps(task) }}/{{ task.steps?.length || 0 }} steps - {{ task.artifacts?.length || 0 }} artifacts</small>
        <ol v-if="task.steps && task.steps.length" class="mini-steps">
          <li v-for="step in task.steps.slice(0, 4)" :key="step.step_id">
            <span>{{ step.status }}</span>
            <small>{{ step.title }}<template v-if="step.attempts"> - try {{ step.attempts }}</template></small>
            <small class="tool-intent">tool: {{ toolIntentLabel(step.tool_intent) }}</small>
            <small v-if="step.last_error">{{ step.last_error }}</small>
            <button v-if="step.status === 'failed'" @click="$emit('retry-step', { task, step })">Retry</button>
          </li>
        </ol>
        <div class="skill-actions">
          <button :disabled="!isRunnable(task)" @click="$emit('run-next', task)">Run Next</button>
          <button :disabled="!isRunnable(task)" @click="$emit('run-loop', task)">Run Loop</button>
          <button v-if="task.status === 'paused'" @click="$emit('resume', task)">Resume</button>
          <button v-else :disabled="!canPause(task)" @click="$emit('pause', task)">Pause</button>
          <button :disabled="isTerminal(task)" @click="$emit('cancel', task)">Cancel</button>
        </div>
      </li>
    </ul>
    <p v-else class="empty">No tasks yet.</p>
  </section>
</template>

<script setup>
defineProps({
  tasks: { type: Array, default: () => [] },
  scheduler: { type: Object, default: () => ({ running: false, max_steps_per_tick: 1, last_tick: null }) }
})

defineEmits([
  'refresh',
  'scheduler-start',
  'scheduler-stop',
  'scheduler-tick',
  'run-next',
  'run-loop',
  'pause',
  'resume',
  'cancel',
  'retry-step'
])

function completedSteps(task) {
  return (task.steps || []).filter((step) => step.status === 'completed').length
}

function isRunnable(task) {
  return ['created', 'running'].includes(task.status)
}

function canPause(task) {
  return ['created', 'running'].includes(task.status)
}

function isTerminal(task) {
  return ['completed', 'failed', 'cancelled'].includes(task.status)
}

function toolIntentLabel(toolIntent) {
  const intent = toolIntent || { name: 'none', arguments: {} }
  const name = intent.name || 'none'
  const args = intent.arguments && Object.keys(intent.arguments).length
    ? ` ${JSON.stringify(intent.arguments)}`
    : ''
  return `${name}${args}`
}
</script>
