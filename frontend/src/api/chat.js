const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
}

export function sendChat(message, sessionId = 'default') {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId })
  })
}

export function fetchMemory() {
  return request('/memory')
}

export function deleteMemory(memoryId) {
  return request(`/memory/${memoryId}`, { method: 'DELETE' })
}

export function fetchTodos() {
  return request('/todos')
}

