<template>
  <main class="app-shell">
    <section class="stage">
      <StatusPanel :status="status" />
    </section>

    <section class="workspace">
      <ChatBox :messages="messages" :loading="loading" @send="handleSend" />
    </section>

    <aside class="side-panels">
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
import { createMemory, deleteMemory, fetchMemory, fetchTodos, sendChat } from './api/chat'
import ChatBox from './components/ChatBox.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import StatusPanel from './components/StatusPanel.vue'
import TodoPanel from './components/TodoPanel.vue'

const messages = ref([
  {
    role: 'assistant',
    content: '我是 LunaClaw，网页里的常驻陪伴 Agent。你可以先问我是谁，或者让我帮你安排今晚两小时。',
    retrieved_memories: []
  }
])
const memories = ref([])
const todos = ref([])
const loading = ref(false)
const status = reactive({
  emotion: 'neutral',
  tool_used: 'none',
  memory_action: 'none',
  skills_used: ['persona_skill']
})

async function handleSend(text) {
  messages.value.push({ role: 'user', content: text, retrieved_memories: [] })
  loading.value = true
  try {
    const result = await sendChat(text)
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      retrieved_memories: result.retrieved_memories || []
    })
    Object.assign(status, result)
    await loadPanels()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '后端暂时没接上。先确认 FastAPI 是否在 http://127.0.0.1:8000 运行。',
      retrieved_memories: []
    })
    Object.assign(status, {
      emotion: 'thinking',
      tool_used: 'none',
      memory_action: 'none',
      skills_used: ['frontend_fallback']
    })
  } finally {
    loading.value = false
  }
}

async function loadPanels() {
  try {
    const [memoryData, todoData] = await Promise.all([fetchMemory(), fetchTodos()])
    memories.value = memoryData
    todos.value = todoData
  } catch {
    memories.value = memories.value
    todos.value = todos.value
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

onMounted(loadPanels)
</script>
