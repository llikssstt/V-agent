# Self-Evolution 设计说明

Self-Evolution 是 LunaClaw 的可解释优化机制，不表示 Agent 具备自我意识。它通过每轮对话后的结构化反思，把用户偏好、常见场景和有效策略记录下来，并在证据足够时沉淀为可回滚的 Skill。

## 工作流

1. `/chat` 开始时根据用户输入加载已启用 Skill。
2. Planner / Responder prompt 注入相关 Skill 摘要。
3. 回复生成后执行 `evolution_reflection`。
4. LLM 只输出 JSON，后端做 schema 校验、敏感过滤和置信度判断。
5. 可信反思会更新偏好、长期记忆、场景计数和进化日志。
6. 同一 `scenario + strategy_summary` 达到 3 次且置信度不低于 0.75 时自动生成 Skill。
7. 每条成功操作都有 `operation_id`，支持回滚。

## 运行时文件

```text
backend/storage/evolution_log.jsonl
backend/storage/evolution_state.json
backend/generated_skills/*.md
```

这些文件是运行时数据，已加入 `.gitignore`。

## API

- `GET /evolution/logs`
- `GET /evolution/skills`
- `POST /evolution/rollback/{operation_id}`

`/chat` 新增返回字段：

- `evolution_events`
- `active_skills`
- `evolution_summary`
- `evolution_count`

## 前端

前端在助手消息下展示本轮优化摘要、进化事件和加载的 Skill。右侧 `EvolutionPanel` 展示历史日志、已启用 Skill 和回滚按钮。
