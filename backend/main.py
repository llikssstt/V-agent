from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agent.agent_core import AgentCore
from agent.memory_core import MemoryCore
from agent.memory import MemoryStore
from agent.self_evolution import SelfEvolutionCore
from tools.todo_tool import TodoStore


app = FastAPI(title="LunaClaw Companion Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class MemoryCreateRequest(BaseModel):
    content: str
    category: str = "user_profile"
    importance: float = 0.7
    source: str = "manual"


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[float] = None
    status: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    return AgentCore().chat(request.message, request.session_id)


@app.get("/memory")
def list_memory():
    return MemoryCore().list_memories()


@app.post("/memory")
def create_memory(request: MemoryCreateRequest):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    try:
        return MemoryCore().write_memory(request.content, request.category, request.importance, request.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/memory/{memory_id}")
def update_memory(memory_id: str, request: MemoryUpdateRequest):
    try:
        return MemoryCore().update_memory(
            memory_id,
            content=request.content,
            category=request.category,
            importance=request.importance,
            status=request.status,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="memory not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: str):
    try:
        return MemoryCore().delete_memory(memory_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="memory not found")


@app.get("/memory/search")
def search_memory(query: str, top_k: int = 5):
    return MemoryCore().retriever.retrieve(query, top_k=top_k)


@app.get("/memory/logs")
def memory_logs(limit: int = 100):
    return MemoryCore().list_logs(limit=limit)


@app.get("/evolution/logs")
def evolution_logs(limit: int = 100):
    return SelfEvolutionCore().list_logs(limit=limit)


@app.get("/evolution/skills")
def evolution_skills():
    return SelfEvolutionCore().list_skills()


@app.post("/evolution/rollback/{operation_id}")
def rollback_evolution(operation_id: str):
    try:
        return SelfEvolutionCore().rollback(operation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evolution operation not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/todos")
def list_todos():
    return TodoStore().list()
