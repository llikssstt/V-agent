# Memory RAG 设计说明

## 目标

Memory RAG 的目标是让 LunaClaw 能跨会话记住用户事实、回忆历史对话，并在回复时只使用检索到的相关记忆。当前实现不依赖外部向量服务，直接使用本地 embedding 模型：

```text
C:\Users\Likssstt\Documents\Playground\course_rag_system\data\models\bge-small-zh-v1.5
```

## 记忆结构

### 短期上下文

`AgentCore` 保留最近若干轮对话，负责当前会话内的连贯性。

### 长期结构化记忆

长期记忆保存在：

```text
backend/storage/memory.json
```

每条记忆包含 `memory_id`、`content`、`category`、`importance`、`created_at`、`updated_at`、`source`、`status`。删除采用软删除：`status=inactive`。

### 历史对话与向量索引

运行时 SQLite 文件：

```text
backend/storage/conversations.db
```

包含三类表：

- `conversations`：历史消息
- `conversations_fts`：历史消息全文检索
- `memory_vectors`：长期记忆的 embedding 向量

`conversations.db` 和 `memory_logs.jsonl` 是运行时产物，已加入 `.gitignore`，首次启动时会自动创建。

## 后端模块

```text
backend/agent/memory_core.py
backend/agent/memory_router.py
backend/agent/memory_retriever.py
backend/agent/memory_writer.py
backend/agent/memory_prompt_builder.py
backend/agent/memory_logger.py
backend/skills/memory_skill/SKILL.md
```

## 工作流

1. `/chat` 收到用户输入后，将用户消息写入 `conversations.db`。
2. `memory_router.py` 判断意图：`retrieve`、`write`、`update`、`delete` 或 `none`。
3. 需要检索时，`memory_retriever.py` 使用本地 bge 模型计算 query embedding。
4. 检索器对长期记忆计算语义相似度，并叠加 importance、少量文本重合度和 recency。
5. `memory_prompt_builder.py` 把用户画像、长期记忆、历史对话压缩成 prompt 上下文。
6. `AgentCore` 把记忆上下文注入 Planner / Responder。
7. 写入、更新、删除和检索操作写入 `memory_logs.jsonl`。
8. `/chat` 返回 `retrieved_memories`，前端在助手消息下展示本轮使用的记忆。

## API

- `GET /memory`
- `POST /memory`
- `PUT /memory/{memory_id}`
- `DELETE /memory/{memory_id}`
- `GET /memory/search?query=xxx`
- `GET /memory/logs`

## 安全策略

`MemoryCore.write_memory()` 和 `MemoryCore.update_memory()` 会拒绝明显敏感信息，例如身份证、银行卡、密码、验证码、token、API key、secret、私钥等。被拒绝的写入会记录为 `result=skipped`，不会进入长期记忆。

## 前端展示

前端已支持：

- 展示长期记忆列表
- 手动写入记忆
- 删除记忆
- 在聊天回复下展示本轮检索到的 `memory_id`、`category` 和分数

## 验证结果

- `python -m pytest backend\tests -q`：17 passed
- 本地 bge 烟测：查询“今晚怎么推进 NLP 大作业？”命中“用户正在准备自然语言处理课程报告，主题是 LunaClaw 陪伴 Agent”，score 为 `0.5686`
- `npm run build` 在当前 Codex 沙箱内仍触发 Vite/esbuild 的 `Cannot read directory "../../.."` 权限限制；这和之前系统更新后的沙箱限制一致，不是前端源码编译错误。脱沙箱重跑请求被当前用量限制拦截，未能完成二次验证。

## 当前限制

- 记忆写入仍是规则提取，不是 LLM fact extraction。
- 历史对话检索主要使用 SQLite LIKE / FTS，长期记忆检索已经是本地 embedding 语义检索。
- 没有 cross-encoder reranker。
- 没有多用户隔离。
- 没有记忆重要性衰减和冲突合并。

## 后续方向

1. 用 LLM 从对话中抽取稳定长期事实。
2. 加入 cross-encoder reranker 提升排序质量。
3. 增加记忆冲突检测和合并策略。
4. 增加前端编辑记忆能力。
5. 增加多用户隔离。
6. 增加会话结束自动总结。
7. 把当前 Memory RAG 抽象为 provider，接近 Hermes Agent 的可替换记忆后端设计。
