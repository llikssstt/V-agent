# 基于大语言模型的生活陪伴型网页 Agent

这是一个《自然语言处理》课程大作业 MVP。项目实现了原创网页陪伴 Agent“LunaClaw”，支持多轮文字聊天、两阶段 LLM 决策、emotion 状态输出、长期记忆和工具调用。

项目默认支持 mock 模式。没有 API Key 时也能启动、聊天和演示完整主链路。

## 功能列表

- 原创网页陪伴 Agent“LunaClaw”人格设定
- FastAPI REST 后端
- Vue 3 + Vite 前端
- Planner + Responder 两阶段 Agent 流程
- OpenAI 兼容格式 LLM 调用
- 无 API Key 的 mock 模式
- JSON 文件长期记忆
- 时间、计算器、待办、学习计划四类工具
- emotion 驱动的角色状态展示
- 状态面板展示 emotion、工具和记忆动作
- 测试用例和 1 分钟演示脚本

## 技术栈

- 后端：Python, FastAPI, Uvicorn, pytest
- 前端：Vue 3, Vite, CSS
- 存储：JSON 文件
- LLM：OpenAI 兼容 Chat Completions API

## 项目结构

```text
backend/
  main.py
  requirements.txt
  .env.example
  agent/
  tools/
  storage/
  tests/
frontend/
  package.json
  index.html
  vite.config.js
  src/
docs/
  test_cases.md
  demo_script.md
  superpowers/
```

## 启动后端

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 启动前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

## 环境变量配置

复制 `backend/.env.example`，或在终端设置：

```powershell
$env:LLM_API_KEY="你的 API Key"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
```

后端会读取：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

## Mock 模式说明

如果没有设置 `LLM_API_KEY`，后端自动进入 mock 模式。mock 模式仍然返回合法 JSON，并能演示：

- 基础聊天
- emotion 切换
- 记忆写入和读取
- 时间工具
- 安全计算器
- 待办工具
- 学习计划工具

真实 API 配置应写入 `backend/.env`，不要写入 `.env.example`。`.env.example` 只保留空模板。

## Memory RAG 模块

项目现在包含本地语义 Memory RAG。后端使用本地 embedding 模型：

```text
C:\Users\Likssstt\Documents\Playground\course_rag_system\data\models\bge-small-zh-v1.5
```

记忆系统包含：

- `backend/storage/memory.json`：长期结构化记忆
- `backend/storage/user_profile.json`：用户画像
- `backend/storage/conversations.db`：历史对话和记忆向量
- `backend/storage/memory_logs.jsonl`：记忆操作日志

主要接口：

- `GET /memory`
- `POST /memory`
- `PUT /memory/{memory_id}`
- `DELETE /memory/{memory_id}`
- `GET /memory/search?query=xxx`
- `GET /memory/logs`

聊天接口 `/chat` 会自动保存历史对话、检索相关记忆，并返回 `retrieved_memories` 供前端展示。

## API 接口

### GET `/health`

返回：

```json
{ "status": "ok" }
```

### POST `/chat`

请求：

```json
{
  "message": "你好呀，你是谁？",
  "session_id": "default"
}
```

响应：

```json
{
  "reply": "Agent 回复",
  "emotion": "happy",
  "tool_used": "none",
  "skills_used": ["persona_skill", "chat_skill"],
  "memory_action": "none"
}
```

### GET `/memory`

返回当前长期记忆列表。

### DELETE `/memory/{memory_id}`

删除指定记忆。

### GET `/todos`

返回当前待办列表。

## 测试

后端测试：

```powershell
python -m pytest backend/tests -q
```

前端构建：

```powershell
cd frontend
npm run build
```

## 后续优化方向

- 增加 TTS
- 增加 ASR
- 增加口型同步
- 使用向量数据库优化记忆检索
- 增加更丰富的工具系统
- 接入直播弹幕互动
- 增加人格一致性评估
