<template>
  <main class="app-shell">
    <section class="stage">
      <Live2DViewer :emotion="status.emotion" model-path="/models/xiaoxi.model3.json" />
      <StatusPanel :status="status" />
    </section>

    <section class="workspace">
      <ChatBox
        :messages="messages"
        :loading="loading"
        @send="handleSend"
      />
    </section>

    <aside class="side-panels">
      <MemoryPanel :items="memories" @refresh="loadPanels" @delete="handleDeleteMemory" />
      <TodoPanel :items="todos" @refresh="loadPanels" />
    </aside>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { deleteMemory, fetchMemory, fetchTodos, sendChat } from './api/chat'
import ChatBox from './components/ChatBox.vue'
import Live2DViewer from './components/Live2DViewer.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import StatusPanel from './components/StatusPanel.vue'
import TodoPanel from './components/TodoPanel.vue'

const messages = ref([
  {
    role: 'assistant',
    content: '我是小熙，屏幕里的常驻嘉宾。你可以先问我是谁，或者让我帮你安排今晚两小时。'
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
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  try {
    const result = await sendChat(text)
    messages.value.push({ role: 'assistant', content: result.reply })
    Object.assign(status, result)
    await loadPanels()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '后端暂时没接上。先确认 FastAPI 是否在 http://127.0.0.1:8000 运行。'
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

onMounted(loadPanels)
</script>

