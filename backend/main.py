from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agent_core import AgentCore
from agent.memory import MemoryStore
from tools.todo_tool import TodoStore


app = FastAPI(title="Xiao Xi Virtual Companion Agent")

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
    return MemoryStore().list_memories()


@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: str):
    deleted = MemoryStore().delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"ok": True}


@app.get("/todos")
def list_todos():
    return TodoStore().list()

