import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[1] / "generated_skills"
SKILL_THRESHOLD = 3
CONFIDENCE_THRESHOLD = 0.75
SENSITIVE_HINTS = ["身份证", "护照", "银行卡", "信用卡", "密码", "验证码", "token", "api key", "apikey", "secret", "私钥"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def slugify(value):
    text = str(value or "skill").lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text).strip("_")
    return text[:48] or "skill"


def is_sensitive(value):
    text = json.dumps(value, ensure_ascii=False).lower() if not isinstance(value, str) else value.lower()
    return any(hint in text for hint in SENSITIVE_HINTS)


def load_json_text(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


class SelfEvolutionCore:
    def __init__(self, storage_dir=DEFAULT_STORAGE_DIR, skills_dir=DEFAULT_SKILLS_DIR, llm_client=None, memory_core=None):
        self.storage_dir = Path(storage_dir)
        self.skills_dir = Path(skills_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.storage_dir / "evolution_state.json"
        self.log_path = self.storage_dir / "evolution_log.jsonl"
        self.llm = llm_client
        self.memory_core = memory_core
        self._init_files()

    def _init_files(self):
        if not self.state_path.exists():
            self._write_state(
                {
                    "preferences": {},
                    "scenario_counts": {},
                    "skills": {},
                    "rollback_index": {},
                    "updated_at": "",
                }
            )
        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")

    def read_state(self):
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"preferences": {}, "scenario_counts": {}, "skills": {}, "rollback_index": {}, "updated_at": ""}

    def _write_state(self, state):
        state["updated_at"] = now_iso()
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _append_log(self, entry):
        payload = {"timestamp": now_iso(), **entry}
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return payload

    def list_logs(self, limit=100):
        if not self.log_path.exists():
            return []
        logs = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines()[-limit:]:
            if not line.strip():
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return logs

    def list_skills(self):
        state = self.read_state()
        return sorted(state.get("skills", {}).values(), key=lambda item: item.get("updated_at", ""), reverse=True)

    def load_active_skills(self, message, limit=3):
        text = str(message or "").lower()
        matches = []
        for skill in self.list_skills():
            if not skill.get("enabled"):
                continue
            haystack = " ".join(
                [
                    str(skill.get("scenario", "")),
                    str(skill.get("strategy_summary", "")),
                    " ".join(skill.get("trigger_examples", []) or []),
                ]
            ).lower()
            if any(token and token in text for token in haystack.split()) or any(token in text for token in ["压力", "摆烂", "不想学", "拖延"]):
                matches.append(skill)
        return matches[:limit]

    def build_skill_context(self, skills):
        if not skills:
            return ""
        lines = ["【本轮加载的自我优化 Skill】"]
        for skill in skills[:3]:
            lines.append(f"* {skill['name']}：{skill.get('strategy_summary') or skill.get('description', '')}")
        return "\n".join(lines)

    def reflect_after_turn(self, user_message, assistant_reply, retrieved_memories=None, active_skills=None):
        if not self.llm:
            return {"evolution_events": [], "evolution_summary": "", "active_skills": active_skills or []}
        try:
            raw = self.llm.complete_json(
                self._build_reflection_prompt(user_message, assistant_reply, retrieved_memories or [], active_skills or []),
                "evolution_reflection",
                {
                    "message": user_message,
                    "assistant_reply": assistant_reply,
                    "retrieved_memories": retrieved_memories or [],
                    "active_skills": active_skills or [],
                },
            )
            reflection = self._normalize_reflection(load_json_text(raw))
            return self._apply_reflection(reflection)
        except Exception as exc:
            self._append_log(
                {
                    "operation_id": f"evo_{uuid.uuid4().hex[:12]}",
                    "operation": "reflect",
                    "target_type": "reflection",
                    "target_id": "",
                    "reason": str(exc),
                    "result": "failed",
                    "before": None,
                    "after": None,
                }
            )
            return {"evolution_events": [], "evolution_summary": "", "active_skills": active_skills or []}

    def _build_reflection_prompt(self, user_message, assistant_reply, retrieved_memories, active_skills):
        return f"""
你是 LunaClaw 的 Self-Evolution 反思模块。你没有自我意识，只做可解释的行为优化记录。
请只返回 JSON，不要输出解释文字。

用户输入：{user_message}
LunaClaw 回复：{assistant_reply}
已检索记忆：{json.dumps(retrieved_memories, ensure_ascii=False)}
本轮已加载 Skill：{json.dumps(active_skills, ensure_ascii=False)}

返回格式：
{{
  "events": [{{"type": "preference_learned | memory_update | strategy_observed | skill_candidate", "summary": "", "target_type": "preference | memory | skill | state"}}],
  "preference_updates": {{}},
  "memory_updates": [{{"content": "", "category": "interaction_style", "importance": 0.8}}],
  "scenario": "拖延 | 学习压力 | 想摆烂 | 需要计划 | 其他",
  "strategy_summary": "",
  "skill_candidate": {{"name": "", "description": "", "trigger_examples": [], "instructions": []}},
  "confidence": 0.0,
  "reason": ""
}}
"""

    def _normalize_reflection(self, data):
        if not isinstance(data, dict):
            data = {}
        events = data.get("events") if isinstance(data.get("events"), list) else []
        preference_updates = data.get("preference_updates") if isinstance(data.get("preference_updates"), dict) else {}
        memory_updates = data.get("memory_updates") if isinstance(data.get("memory_updates"), list) else []
        skill_candidate = data.get("skill_candidate") if isinstance(data.get("skill_candidate"), dict) else {}
        try:
            confidence = float(data.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "events": events,
            "preference_updates": preference_updates,
            "memory_updates": memory_updates,
            "scenario": str(data.get("scenario") or "").strip(),
            "strategy_summary": str(data.get("strategy_summary") or "").strip(),
            "skill_candidate": skill_candidate,
            "confidence": max(0.0, min(confidence, 1.0)),
            "reason": str(data.get("reason") or "").strip(),
        }

    def _apply_reflection(self, reflection):
        if reflection["confidence"] < CONFIDENCE_THRESHOLD or is_sensitive(reflection):
            self._append_log(
                {
                    "operation_id": f"evo_{uuid.uuid4().hex[:12]}",
                    "operation": "reflect",
                    "target_type": "reflection",
                    "target_id": "",
                    "reason": reflection.get("reason") or "low confidence or sensitive content",
                    "result": "skipped",
                    "before": None,
                    "after": reflection,
                }
            )
            return {"evolution_events": [], "evolution_summary": "", "active_skills": self.load_active_skills(reflection.get("scenario", ""))}

        state = self.read_state()
        events = []
        if reflection["preference_updates"]:
            before = dict(state.get("preferences", {}))
            state.setdefault("preferences", {}).update(reflection["preference_updates"])
            events.append(self._log_success("preference_update", "preference", "preferences", reflection["reason"], before, state["preferences"]))

        for item in reflection["memory_updates"]:
            content = str(item.get("content", "")).strip() if isinstance(item, dict) else ""
            if not content or is_sensitive(content) or not self.memory_core:
                continue
            memory = self.memory_core.write_memory(
                content,
                item.get("category", "interaction_style"),
                item.get("importance", 0.8),
                "self_evolution",
            )
            events.append(self._log_success("memory_update", "memory", memory["memory_id"], reflection["reason"], None, memory))

        scenario_key = ""
        if reflection["scenario"] and reflection["strategy_summary"]:
            scenario_key = f"{reflection['scenario']}::{reflection['strategy_summary']}"
            before_counts = dict(state.get("scenario_counts", {}))
            state.setdefault("scenario_counts", {})[scenario_key] = state.setdefault("scenario_counts", {}).get(scenario_key, 0) + 1
            events.append(self._log_success("scenario_observed", "state", scenario_key, reflection["reason"], before_counts, state["scenario_counts"]))

        skill_event = self._maybe_upsert_skill(state, reflection, scenario_key)
        if skill_event:
            events.append(skill_event)

        self._write_state(state)
        summary = f"{reflection['scenario']}：{reflection['strategy_summary']}" if reflection["scenario"] and reflection["strategy_summary"] else ""
        return {
            "evolution_events": [event for event in events if event.get("result") == "success"],
            "evolution_summary": summary,
            "active_skills": self.load_active_skills(reflection["scenario"]),
        }

    def _log_success(self, operation, target_type, target_id, reason, before, after):
        operation_id = f"evo_{uuid.uuid4().hex[:12]}"
        entry = {
            "operation_id": operation_id,
            "operation": operation,
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "result": "success",
            "before": before,
            "after": after,
        }
        return self._append_log(entry)

    def _maybe_upsert_skill(self, state, reflection, scenario_key):
        candidate = reflection["skill_candidate"]
        if not scenario_key or not candidate or state["scenario_counts"].get(scenario_key, 0) < SKILL_THRESHOLD:
            return None
        if is_sensitive(candidate):
            return self._append_log(
                {
                    "operation_id": f"evo_{uuid.uuid4().hex[:12]}",
                    "operation": "skill_update",
                    "target_type": "skill",
                    "target_id": "",
                    "reason": "sensitive skill candidate",
                    "result": "skipped",
                    "before": None,
                    "after": candidate,
                }
            )

        name = slugify(candidate.get("name") or reflection["scenario"])
        skill_id = f"skill_{name}"
        before = state.setdefault("skills", {}).get(skill_id)
        version = int((before or {}).get("version", 0)) + 1
        skill = {
            "skill_id": skill_id,
            "name": candidate.get("name") or name,
            "description": candidate.get("description") or reflection["strategy_summary"],
            "scenario": reflection["scenario"],
            "strategy_summary": reflection["strategy_summary"],
            "trigger_examples": candidate.get("trigger_examples") if isinstance(candidate.get("trigger_examples"), list) else [],
            "instructions": candidate.get("instructions") if isinstance(candidate.get("instructions"), list) else [],
            "enabled": True,
            "version": version,
            "evidence_count": state["scenario_counts"][scenario_key],
            "created_at": (before or {}).get("created_at") or now_iso(),
            "updated_at": now_iso(),
            "path": str(self.skills_dir / f"{skill_id}.md"),
        }
        state["skills"][skill_id] = skill
        self._write_skill_file(skill)
        return self._log_success("skill_update", "skill", skill_id, reflection["reason"], before, skill)

    def _write_skill_file(self, skill):
        frontmatter = [
            "---",
            f"skill_id: {skill['skill_id']}",
            f"scenario: {skill['scenario']}",
            f"version: {skill['version']}",
            f"enabled: {str(skill['enabled']).lower()}",
            f"created_at: {skill['created_at']}",
            f"updated_at: {skill['updated_at']}",
            f"evidence_count: {skill['evidence_count']}",
            "---",
        ]
        body = [
            f"# {skill['name']}",
            "",
            skill.get("description", ""),
            "",
            "## Trigger Examples",
            *[f"- {item}" for item in skill.get("trigger_examples", [])],
            "",
            "## Instructions",
            *[f"- {item}" for item in skill.get("instructions", [])],
            "",
        ]
        path = Path(skill["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(frontmatter + body), encoding="utf-8")

    def rollback(self, operation_id):
        logs = self.list_logs(limit=1000)
        entry = next((item for item in reversed(logs) if item.get("operation_id") == operation_id), None)
        if not entry:
            raise KeyError(operation_id)
        state = self.read_state()
        target_type = entry.get("target_type")
        target_id = entry.get("target_id")
        before = entry.get("before")
        if target_type == "skill":
            current = state.setdefault("skills", {}).get(target_id)
            if before:
                state["skills"][target_id] = before
                self._write_skill_file(before)
            elif current:
                current["enabled"] = False
                current["updated_at"] = now_iso()
                state["skills"][target_id] = current
                self._write_skill_file(current)
        elif target_type == "preference":
            state["preferences"] = before or {}
        elif target_type == "state" and target_id:
            state["scenario_counts"] = before or {}
        else:
            raise ValueError(f"rollback not supported for {target_type}")
        self._write_state(state)
        return self._append_log(
            {
                "operation_id": f"evo_{uuid.uuid4().hex[:12]}",
                "operation": "rollback",
                "target_type": target_type,
                "target_id": target_id,
                "reason": f"rollback {operation_id}",
                "result": "success",
                "before": entry.get("after"),
                "after": before,
            }
        )
