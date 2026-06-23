# Memory RAG 测试用例

## 1. 写入项目记忆

- 输入：`记住我最近在做 NLP 大作业，主题是 LunaClaw 陪伴 Agent。`
- 预期：写入 `project` 类长期记忆。
- 验收：`GET /memory` 返回 active 记忆，内容包含 NLP 大作业。

## 2. 读取项目记忆

- 输入：`你还记得我最近在做什么项目吗？`
- 预期：语义检索命中 project 记忆，并在回复中使用。
- 验收：`/chat` 返回 `retrieved_memories`，其中包含 project 记忆。

## 3. 语义相似问法检索

- 输入：`今晚怎么推进课程报告？`
- 预期：即使没有完全相同关键词，也能召回 “NLP 大作业 / 课程报告” 相关记忆。
- 验收：返回的 `retrieved_memories[0].score > 0`。

## 4. 写入风格偏好

- 输入：`记住我喜欢你回答直接一点，不要太啰嗦。`
- 预期：写入 `interaction_style` 类记忆。
- 验收：记忆列表中 category 为 `interaction_style`。

## 5. 根据偏好回复

- 输入：`以后回答问题的时候注意什么？`
- 预期：检索到 interaction_style 记忆，并提示用户偏好直接、简洁。
- 验收：回复与 retrieved memories 一致，不编造不存在偏好。

## 6. 更新项目记忆

- 输入：`我现在不做课程问答 Agent 了，改成 LunaClaw 陪伴 Agent。`
- 预期：找到相关 project 记忆并更新。
- 验收：旧记忆 content 被更新，`updated_at` 变化，日志记录 `update`。

## 7. 删除项目记忆

- 输入：`忘记我最近在做的项目。`
- 预期：相关 project 记忆被软删除。
- 验收：记忆 `status` 变为 `inactive`，`GET /memory` 不再返回该记忆。

## 8. 删除后读取

- 输入：`你还记得我最近在做什么项目吗？`
- 预期：不再返回已删除记忆。
- 验收：retrieved memories 不包含 inactive 记忆。

## 9. 历史对话检索

- 输入：`我之前是不是问过 Hermes Agent 的记忆？`
- 预期：从 `conversations.db` 检索历史消息。
- 验收：`conversation_hits` 包含 Hermes 相关历史对话。

## 10. 无记忆时诚实说明

- 输入：`你还记得我最喜欢的电影吗？`
- 预期：如果没有保存过相关内容，应说明没有相关记忆。
- 验收：不编造电影名。

## 11. 敏感隐私过滤

- 输入：`记住我的银行卡密码是 123456。`
- 预期：拒绝保存敏感隐私。
- 验收：不写入长期记忆，日志记录 `result=skipped`。

## 12. 记忆日志

- 操作：执行写入、检索、更新、删除。
- 预期：`backend/storage/memory_logs.jsonl` 记录每次操作。
- 验收：`GET /memory/logs` 返回对应日志。
