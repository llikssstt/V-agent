# Agent 模块测试记录

## 测试目标

本轮测试围绕以下模块展开：

- 任务规划：Planner 阶段是否能决定生成计划。
- 工具调用：Planner 是否能选择工具，Responder 是否能解释结果。
- 任务执行：后端是否真实执行工具，而不是只在回复里假装执行。
- 长期记忆：是否支持写入、检索和在后续回复中使用。
- API Key 配置：真实密钥应放在 `backend/.env`，模板文件不应包含密钥。

## 配置处理

检查时发现真实 API Key 被写在 `backend/.env.example` 中。该文件属于示例配置，可能被提交到仓库，因此不应保存真实密钥。

已处理：

1. 将当前配置复制到 `backend/.env`。
2. 将 `backend/.env.example` 恢复为不含密钥的模板：

```env
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

3. 确认 `backend/.env` 被 `.gitignore` 忽略。
4. 后端新增 `.env` 加载逻辑，`LLMClient` 会自动读取 `backend/.env` 或项目根目录 `.env`。

安全备注：如果真实密钥曾经被提交或推送到远端仓库，应在模型服务商后台轮换该密钥。

## 新增测试脚本

新增脚本：

```text
scripts/run_agent_module_checks.py
```

默认模式不访问外部 API：

```powershell
python scripts\run_agent_module_checks.py
```

真实 API 模式会读取 `backend/.env` 并向配置的模型服务发送测试 prompt：

```powershell
python scripts\run_agent_module_checks.py --real-api
```

真实 API 测试会把用户输入、人格设定、工具列表、上下文和记忆摘要发送给外部模型服务。执行前需要明确授权。

## 本地 Mock 集成测试结果

命令：

```powershell
python scripts\run_agent_module_checks.py
```

结果摘要：

| 用例 | 输入 | 关键结果 |
| --- | --- | --- |
| 任务规划 | `帮我安排今晚两小时完成课程报告。` | `tool_used=study_plan`，返回分段计划 |
| 计算器工具 | `帮我计算 2 * (3 + 4)。` | `tool_used=calculator`，结果为 `14` |
| 待办工具 | `帮我添加一个待办：完成 NLP 报告。` | `tool_used=todo`，待办写入成功 |
| 记忆写入 | `记住我最近在做 NLP 课程陪伴 Agent。` | `memory_action=write`，记忆写入成功 |
| 记忆读取 | `你还记得我最近在做什么吗？` | `memory_action=read`，回复包含已写入记忆 |

调用来源：

```text
planner: mock
responder: mock
```

## 发现的问题与修复

### 问题 1：`.env.example` 保存了真实密钥

影响：示例文件可能进入 git，导致密钥泄露。

修复：

- 复制真实配置到 `backend/.env`。
- 清空 `backend/.env.example` 中的 `LLM_API_KEY`。
- 确认 `.env` 被 git 忽略。

### 问题 2：后端不会自动读取 `.env`

影响：即使用户在 `.env` 中配置 API Key，`LLMClient` 也只会读取系统环境变量，导致仍可能进入 mock 模式。

修复：

- 新增 `backend/agent/env_loader.py`。
- `LLMClient.__init__` 中自动加载 `.env`。
- 新增单元测试覆盖 `.env` 加载。

### 问题 3：自然中文问句无法检索已写入记忆

复现：

1. 写入：`我最近在做 NLP 课程陪伴 Agent`
2. 读取：`你还记得我最近在做什么吗？`
3. 旧逻辑返回空记忆。

原因：旧检索只依赖直接包含和空格分词，不适合中文自然问句。

修复：

- 在 `retrieve_memory` 中加入中文字符交集评分。
- 对“记得 / 最近 / 做什么”等宽泛记忆问句，给高重要度记忆增加兜底分。
- 新增回归测试。

## 自动化验证

后端测试：

```text
9 passed
```

前端构建：

```text
vite build succeeded
```

## 真实 API 测试状态

真实 API 测试已在用户明确授权后执行。该测试会把测试 prompt、人格设定、工具列表、短期上下文和记忆摘要发送到 `backend/.env` 配置的外部模型服务。

命令：

```powershell
python scripts\run_agent_module_checks.py --real-api
```

配置摘要：

```text
base_url=https://api.deepseek.com
model=deepseek-v4-flash
api_key_present=true
```

真实 API 测试结果：

| 用例 | 关键结果 | 调用来源 |
| --- | --- | --- |
| 任务规划 | `tool_used=study_plan`，生成两小时报告计划 | planner=`real_api`, responder=`real_api` |
| 计算器工具 | `tool_used=calculator`，`2 * (3 + 4) = 14` | planner=`real_api`, responder=`real_api` |
| 待办工具 | `tool_used=todo`，待办写入成功；模型同时决定写入一条 todo 类记忆 | planner=`real_api`, responder=`real_api` |
| 记忆写入 | `memory_action=write`，写入“用户最近在做 NLP 课程陪伴 Agent” | planner=`real_api`, responder=`real_api` |
| 记忆读取 | `memory_action=read`，回复中正确提到 NLP 课程陪伴 Agent | planner=`real_api`, responder=`real_api` |

真实 API 测试期间发现一个脚本输出问题：

- 现象：模型回复包含 Windows GBK 控制台无法编码的字符，导致 `UnicodeEncodeError`。
- 修复：在 `scripts/run_agent_module_checks.py` 中将 `stdout` 显式设置为 UTF-8。

结论：真实 API 模式下，两阶段 Planner + Responder、工具调用、工具真实执行、记忆写入和记忆读取均已通过集成验证。
