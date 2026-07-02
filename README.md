# V-Agent

V-Agent is a general FastAPI + Vue agent system. The default `/chat` runtime is `GraphCore`, a LangGraph-based multi-agent flow that combines memory retrieval, Skill matching, Skill Pack resource reading, tool execution traces, image input, and final response generation.

The legacy `AgentCore` is still available with `AGENT_RUNTIME=legacy`.

## Features

- LangGraph `GraphCore` runtime with Agent Flow tracing.
- Memory RAG through `MemoryCore` and `/memory` APIs.
- Skill Pack installation, lifecycle management, and resource viewing.
- Skill Resource Reader for safe text resource search/read inside a Skill root.
- Tool Store and Permission Review for approved tool installation.
- Tool Trace, Sources, Active Skills, Skill Trace, and Agent Flow in chat output.
- Image upload with `file_id` attachments; server paths are stored only in `uploads_index.json`.
- Task Runtime with durable task plans, per-step `tool_intent`, artifacts, logs, pause/resume/cancel, retry, and scheduler controls.
- Planner Node that asks the LLM for structured task steps and validates selected tools before execution.
- TaskPanel in the frontend for inspecting task status, per-step tools, artifacts, and scheduler state.
- Mock LLM mode when no `LLM_API_KEY` is configured.

## Run

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Runtime

Default:

```powershell
$env:AGENT_RUNTIME="graph"
```

Legacy:

```powershell
$env:AGENT_RUNTIME="legacy"
```

LLM settings:

```powershell
$env:LLM_API_KEY="..."
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
```

## Task Runtime

GraphCore creates a tracked task for each `/chat` request. The Planner Node returns a durable plan:

```json
{
  "task_title": "Short title",
  "route": "response | execute_tool | tool_search | multimodal",
  "reason": "why this route was chosen",
  "steps": [
    {
      "title": "Run calculator",
      "tool_intent": {
        "name": "calculator",
        "arguments": {
          "expression": "2 + 3"
        }
      }
    }
  ],
  "tool_intent": {
    "name": "calculator",
    "arguments": {
      "expression": "2 + 3"
    }
  }
}
```

Each step stores its own `tool_intent`. Task execution prefers the step-level tool and falls back to the task-level tool only for older stored tasks. Tool execution artifacts record `step_id`, `step_title`, `step_tool_intent`, and the structured `tool_result`.

Task APIs:

```text
GET  /tasks
GET  /tasks/{task_id}
POST /tasks/{task_id}/run-next
POST /tasks/{task_id}/run-until-idle
POST /tasks/{task_id}/pause
POST /tasks/{task_id}/resume
POST /tasks/{task_id}/cancel
POST /tasks/{task_id}/steps/{step_id}/retry
```

Scheduler APIs:

```text
GET  /tasks/scheduler
POST /tasks/scheduler/start
POST /tasks/scheduler/stop
POST /tasks/scheduler/tick
```

The frontend TaskPanel shows task status, step status, attempts, last errors, artifacts, scheduler state, and each step's `tool_intent`.

## Demo Flow

1. Ask V-Agent to install a web reading tool.
2. Review permissions in Permission Review and approve.
3. Confirm `web_reader` appears in Tool Store.
4. Ask: `use web_reader to summarize this page: https://example.com`.
5. Inspect Tool Trace, Sources, and Agent Flow.
6. Install or view a Skill Pack, then ask a query matching its triggers.
7. Inspect Active Skills, Skill Trace, and Skill resource results.
8. Upload an image and ask V-Agent to analyze it.

## Safety Notes

- Unknown downloaded scripts are not executed.
- MCP is not connected in this phase.
- Tool execution is limited to approved demo tools.
- Skill resources are searched/read as text only and constrained to their Skill root.
- Runtime files are ignored: uploads, installed tool registry, approvals, installed packages, generated Skills, and logs.

## Test

```powershell
python -m pytest backend\tests -q
```

```powershell
cd frontend
npm run build
```

If Vite/esbuild fails in a sandbox with `spawn EPERM`, run the same build command outside the sandbox.

## Real API Eval

The eval suite uses the real model configured in `backend/.env` or the current environment. It fails if `LLM_API_KEY` is missing or if the model call falls back to mock output.

```powershell
python backend\tests\run_eval.py
```

Reports are written to:

```text
backend/tests/reports/eval_report.json
backend/tests/reports/eval_report.md
```

Metrics:

- `route_accuracy`: planner route matches the expected route.
- `tool_accuracy`: `tool_intent` / `tool_used` matches the expected tool.
- `skill_hit_rate`: expected Skill cases load `active_skills`.
- `resource_hit_rate`: expected resource cases load `skill_resource_results`.
- `memory_hit_rate`: expected memory cases load `retrieved_memories`.
- `task_created_rate`: expected task cases create a tracked task.
- `trace_completeness`: `agent_flow`, `tool_trace`, and `skill_trace` fields are present.
