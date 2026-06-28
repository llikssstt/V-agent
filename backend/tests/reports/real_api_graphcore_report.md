# Real API Integration Test Report

- Time: 2026-06-28T20:57:06
- Model: deepseek-v4-flash
- Base URL: https://api.deepseek.com
- LLM call sources: `[{"stage": "responder", "source": "real_api"}, {"stage": "responder", "source": "real_api"}]`
- API key: configured, value omitted

## Results

### Case 1

**Question**: In two sentences, explain how V-Agent GraphCore currently uses Skill Agent.

**Answer**: V-Agent GraphCore uses the Skill Agent `match_skills` step to match the user input against available skills. In this test run no skill was matched, so the runtime continued with the general Response Agent path.

- skills_used: `[]`
- active_skills_count: `0`
- skill_trace_count: `0`
- skill_resource_results_count: `0`
- agent_flow: `["Supervisor Agent", "Memory Agent", "Skill Agent", "Skill Resource Agent", "Response Agent"]`

### Case 2

**Question**: Briefly answer why Skill Resource Agent must not execute scripts when reading resources.

**Answer**: Skill Resource Agent is restricted to reading static resources such as documentation and metadata. Script execution belongs to reviewed tool runtimes, not the resource reader, because resources can come from installed packs and must remain non-executable by default.

- skills_used: `[]`
- active_skills_count: `0`
- skill_trace_count: `0`
- skill_resource_results_count: `0`
- agent_flow: `["Supervisor Agent", "Memory Agent", "Skill Agent", "Skill Resource Agent", "Response Agent"]`
