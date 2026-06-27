import re
from pathlib import Path


DEFAULT_STATIC_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
DEFAULT_GENERATED_SKILLS_DIR = Path(__file__).resolve().parents[1] / "generated_skills"


class SkillRegistry:
    def __init__(self, static_dir=DEFAULT_STATIC_SKILLS_DIR, generated_dir=DEFAULT_GENERATED_SKILLS_DIR):
        self.static_dir = Path(static_dir or DEFAULT_STATIC_SKILLS_DIR)
        self.generated_dir = Path(generated_dir or DEFAULT_GENERATED_SKILLS_DIR)

    def load_skills(self):
        skills = []
        for directory in [self.static_dir, self.generated_dir]:
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*.md")):
                skill = self._load_skill(path)
                if skill:
                    skills.append(skill)
        return skills

    def match(self, message, limit=5):
        text = str(message or "").lower()
        matches = []
        for skill in self.load_skills():
            if skill.get("enabled") is False:
                continue
            triggers = [str(item).lower() for item in skill.get("triggers", []) + skill.get("trigger_examples", [])]
            if any(trigger and trigger in text for trigger in triggers):
                matches.append(skill)
        return matches[:limit]

    def build_context(self, skills):
        if not skills:
            return ""
        lines = ["【匹配到的 Skill】"]
        for skill in skills[:5]:
            lines.append(f"## {skill.get('name') or skill.get('skill_id')}")
            if skill.get("description"):
                lines.append(f"Description: {skill['description']}")
            triggers = skill.get("triggers") or []
            if triggers:
                lines.append("Triggers: " + ", ".join(triggers[:8]))
            instructions = skill.get("instructions") or skill.get("summary") or ""
            if instructions:
                lines.append("Instructions:")
                lines.append(instructions)
        return "\n".join(lines)

    def _load_skill(self, path):
        text = path.read_text(encoding="utf-8")
        meta, body = self._split_frontmatter(text)
        name = meta.get("name") or meta.get("skill_id") or path.stem
        triggers = self._list_value(meta.get("triggers"))
        trigger_examples = self._list_value(meta.get("trigger_examples"))
        if not triggers:
            triggers = self._extract_inline_list(body, "Triggers")
        if not trigger_examples:
            trigger_examples = self._extract_inline_list(body, "Trigger Examples")
        return {
            "skill_id": meta.get("skill_id") or path.stem,
            "name": name,
            "description": meta.get("description", ""),
            "scenario": meta.get("scenario", ""),
            "enabled": str(meta.get("enabled", "true")).lower() != "false",
            "triggers": triggers,
            "trigger_examples": trigger_examples,
            "path": str(path),
            "summary": self._summary(body),
            "instructions": self._instructions(body),
        }

    def _split_frontmatter(self, text):
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta = {}
        current_key = None
        for raw in parts[1].splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            if line.startswith("  - ") and current_key:
                meta.setdefault(current_key, []).append(line[4:].strip())
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                current_key = key.strip()
                value = value.strip()
                meta[current_key] = value if value else []
        return meta, parts[2]

    def _list_value(self, value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    def _extract_inline_list(self, body, heading):
        pattern = rf"## {re.escape(heading)}\s*(.*?)(?:\n## |\Z)"
        match = re.search(pattern, body, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return []
        return [line[2:].strip() for line in match.group(1).splitlines() if line.strip().startswith("- ")]

    def _summary(self, body):
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:160]
        return ""

    def _instructions(self, body):
        items = self._extract_inline_list(body, "Instructions")
        if items:
            return "\n".join(f"- {item}" for item in items[:8])
        lines = []
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
            if len(" ".join(lines)) >= 400:
                break
        return "\n".join(lines)[:600]
