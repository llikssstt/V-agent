<template>
  <main class="app-shell">
    <section class="stage">
      <StatusPanel :status="status" />
    </section>

    <section class="workspace">
      <ChatBox :messages="messages" :loading="loading" @send="handleSend" />
    </section>

    <aside class="side-panels">
      <EvolutionPanel
        :logs="evolutionLogs"
        :skills="evolutionSkills"
        @refresh="loadPanels"
        @rollback="handleRollbackEvolution"
      />
      <MemoryPanel
        :items="memories"
        @refresh="loadPanels"
        @delete="handleDeleteMemory"
        @create="handleCreateMemory"
      />
      <TodoPanel :items="todos" @refresh="loadPanels" />
    </aside>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  createMemory,
  deleteMemory,
  fetchEvolutionLogs,
  fetchEvolutionSkills,
  fetchMemory,
  fetchTodos,
  rollbackEvolution,
  sendChat
} from './api/chat'
import ChatBox from './components/ChatBox.vue'
import EvolutionPanel from './components/EvolutionPanel.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import StatusPanel from './components/StatusPanel.vue'
import TodoPanel from './components/TodoPanel.vue'

const messages = ref([
  {
    role: 'assistant',
    content: '我是 LunaClaw，网页里的常驻陪伴 Agent。你可以先问我是谁，或者让我帮你安排今晚两小时。',
    retrieved_memories: [],
    evolution_events: [],
    active_skills: [],
    evolution_summary: ''
  }
])
const memories = ref([])
const todos = ref([])
const evolutionLogs = ref([])
const evolutionSkills = ref([])
const loading = ref(false)
const status = reactive({
  emotion: 'neutral',
  tool_used: 'none',
  memory_action: 'none',
  skills_used: ['persona_skill'],
  active_skills: [],
  evolution_count: 0
})

async function handleSend(text) {
  messages.value.push({ role: 'user', content: text, retrieved_memories: [], evolution_events: [], active_skills: [], evolution_summary: '' })
  loading.value = true
  try {
    const result = await sendChat(text)
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      retrieved_memories: result.retrieved_memories || [],
      evolution_events: result.evolution_events || [],
      active_skills: result.active_skills || [],
      evolution_summary: result.evolution_summary || ''
    })
    Object.assign(status, {
      ...result,
      active_skills: result.active_skills || [],
      evolution_count: result.evolution_count || 0
    })
    await loadPanels()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '后端暂时没接上。先确认 FastAPI 是否在 http://127.0.0.1:8000 运行。',
      retrieved_memories: [],
      evolution_events: [],
      active_skills: [],
      evolution_summary: ''
    })
    Object.assign(status, {
      emotion: 'thinking',
      tool_used: 'none',
      memory_action: 'none',
      skills_used: ['frontend_fallback'],
      active_skills: [],
      evolution_count: 0
    })
  } finally {
    loading.value = false
  }
}

async function loadPanels() {
  try {
    const [memoryData, todoData, logData, skillData] = await Promise.all([
      fetchMemory(),
      fetchTodos(),
      fetchEvolutionLogs(),
      fetchEvolutionSkills()
    ])
    memories.value = memoryData
    todos.value = todoData
    evolutionLogs.value = logData
    evolutionSkills.value = skillData
  } catch {
    memories.value = memories.value
    todos.value = todos.value
    evolutionLogs.value = evolutionLogs.value
    evolutionSkills.value = evolutionSkills.value
  }
}

async function handleDeleteMemory(memoryId) {
  await deleteMemory(memoryId)
  await loadPanels()
}

async function handleCreateMemory(payload) {
  await createMemory(payload)
  await loadPanels()
}

async function handleRollbackEvolution(operationId) {
  await rollbackEvolution(operationId)
  await loadPanels()
}

onMounted(loadPanels)
</script>
