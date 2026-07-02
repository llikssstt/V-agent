# V-Agent Real API Eval Report

- Generated at: `2026-06-29T08:17:13.149070+00:00`
- Cases: `4`
- Real API only: `True`
- Fallback count: `0`

## Metrics

- `route_accuracy`: `0.75`
- `tool_accuracy`: `0.75`
- `skill_hit_rate`: `0.5`
- `resource_hit_rate`: `0.0`
- `memory_hit_rate`: `1.0`
- `task_created_rate`: `1.0`
- `trace_completeness`: `1.0`

## Cases

### calculator_step_tool

- Question: What is 2 + 3?
- Reply: The result of 2 + 3 is 5.
- Expected route/tool: `execute_tool` / `calculator`
- Actual route/tool: `execute_tool` / `calculator`
- Skill/resource/memory/task/trace: `False` / `False` / `False` / `True` / `True`

### code_review_skill

- Question: 请帮我做一次 code review，重点找潜在 bug 和缺失测试。
- Reply: 要执行 code review，我需要看到具体的代码或 diff。请提供相关的文件内容或变更。
- Expected route/tool: `response` / `none`
- Actual route/tool: `response` / `none`
- Skill/resource/memory/task/trace: `True` / `False` / `False` / `True` / `True`

### memory_retrieval

- Question: 还记得我的 eval 偏好吗？
- Reply: 是的，我记得您的 eval 偏好：使用真实 API 并记录指标报告。
- Expected route/tool: `response` / `none`
- Actual route/tool: `response` / `none`
- Skill/resource/memory/task/trace: `False` / `False` / `True` / `True` / `True`

### skill_resource_reader

- Question: 根据 web research skill 的资源说明，帮我规划一次网页资料调研。
- Reply: 目前尚未读取到 web research skill 的资源说明，因为 Skill Resource Agent 未加载任何资源。建议先使用 web_research 技能的工具读取其资源文件（如 imported/nature_skills.md 等），以便我能根据资源内容为您规划调研。
- Expected route/tool: `response` / `none`
- Actual route/tool: `execute_tool` / `list_skills`
- Skill/resource/memory/task/trace: `False` / `False` / `True` / `True` / `True`

