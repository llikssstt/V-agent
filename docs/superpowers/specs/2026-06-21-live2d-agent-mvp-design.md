# Live2D Agent MVP Design

## Goal

Build a runnable course MVP for an original virtual companion Agent named Xiao Xi. The system must run without an API key through mock mode, while keeping a clear path to replace mock LLM calls and the placeholder Live2D view later.

## Scope

The MVP includes a FastAPI backend, a Vue 3 + Vite frontend, JSON-file storage, four executable tools, long-term memory operations, and documentation for testing and a one-minute demo. It does not implement real Live2D animation, ASR, TTS, lip sync, vector search, live-stream chat, or multi-agent collaboration.

The existing root `index.html` is ignored. New application files live under `backend/`, `frontend/`, and `docs/`.

## Architecture

The backend owns all Agent decisions and side effects. `/chat` receives a user message, appends short-term context, runs a Planner stage, executes the requested memory/tool actions, runs a Responder stage, validates the result, stores the assistant reply, and returns a stable JSON response.

The LLM client has two modes:

- Real mode uses OpenAI-compatible chat completions configured by `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`.
- Mock mode is used when `LLM_API_KEY` is missing. It returns legal structured JSON and demonstrates chat, emotions, memory read/write/delete, time, calculator, todo, and study-plan tool calls.

The frontend is a single-page Vue app. It never decides emotion, tool usage, or memory action; it renders backend output only.

## Backend Components

- `backend/main.py`: FastAPI app and REST routes.
- `backend/agent/agent_core.py`: two-stage Agent orchestration.
- `backend/agent/llm_client.py`: OpenAI-compatible client plus mock planner/responder.
- `backend/agent/prompt_builder.py`: planner and responder prompt construction.
- `backend/agent/response_parser.py`: JSON parsing, enum validation, fallback handling.
- `backend/agent/memory.py`: JSON-file memory store.
- `backend/tools/*.py`: time, calculator, todo, study-plan tools and dispatcher.
- `backend/storage/*.json`: memory, todos, and conversations.

## Frontend Components

- `frontend/src/App.vue`: page layout and shared state.
- `Live2DViewer.vue`: replaceable character display with `modelPath` prop and emotion-driven placeholder state.
- `ChatBox.vue`, `MessageList.vue`, `InputBox.vue`: chat workflow.
- `StatusPanel.vue`: current `emotion`, `tool_used`, `memory_action`, `skills_used`.
- `MemoryPanel.vue`, `TodoPanel.vue`: demo support panels.
- `src/api/chat.js`: backend REST calls.
- `src/utils/emotionMap.js`: rendering map for allowed emotion values.

## Data Flow

1. User sends a message in the frontend.
2. Frontend posts `{ message, session_id }` to `/chat`.
3. Backend stores the user message in `conversations.json`.
4. Planner returns structured JSON.
5. Backend validates planner fields and executes requested memory/tool actions.
6. Responder returns final structured JSON.
7. Backend validates response, stores assistant message, and returns JSON to frontend.
8. Frontend displays the reply and updates character/status panels from returned fields.

## Error Handling

Invalid LLM JSON or illegal enum values fall back to a safe response. Unknown tools or invalid tool arguments return a tool error object that the responder can explain. Calculator execution avoids direct `eval` and only permits numeric arithmetic AST nodes.

## Testing

Backend pytest coverage verifies `/health`, mock `/chat`, calculator safety, memory operations, todo operations, and study-plan tool execution. Frontend verification uses `npm run build`. Final smoke verification starts the backend and calls `/health` and `/chat`.

