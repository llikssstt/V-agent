from agent.self_evolution import SelfEvolutionCore
from agent.skill_registry import SkillRegistry
from agent_graph.nodes.common import flow_step
from tools import skill_installer_tool


def skill_node(state, skill_registry=None, evolution_core=None):
    message = state.get("user_message", "")
    registry = skill_registry or SkillRegistry(
        static_dir=skill_installer_tool.DEFAULT_STATIC_SKILLS_DIR,
        generated_dir=skill_installer_tool.DEFAULT_GENERATED_SKILLS_DIR,
    )
    evolution = evolution_core or SelfEvolutionCore()

    registry_matches = registry.match(message)
    evolution_matches = evolution.load_active_skills(message)
    active_skills = _dedupe_skills(registry_matches + evolution_matches)
    registry_context = registry.build_context([skill for skill in active_skills if skill.get("path")]) if active_skills else ""
    evolved_skills = [skill for skill in active_skills if skill.get("evidence_count")]
    evolution_context = evolution.build_skill_context(evolved_skills) if hasattr(evolution, "build_skill_context") else ""
    skill_context = "\n\n".join(part for part in [registry_context, evolution_context] if part)
    skill_trace = []
    registry_ids = {_skill_key(skill) for skill in registry_matches}
    for skill in active_skills:
        source = "registry" if _skill_key(skill) in registry_ids else "self_evolution"
        skill_trace.append(
            {
                "source": source,
                "skill_id": skill.get("skill_id"),
                "name": skill.get("name"),
                "description": skill.get("description", ""),
                "triggers": skill.get("triggers", []) or skill.get("trigger_examples", []),
                "resources": skill.get("resources", []),
            }
        )

    state["active_skills"] = active_skills
    state["skills_used"] = [_skill_label(skill) for skill in active_skills]
    state["skill_context"] = skill_context
    state["skill_trace"] = skill_trace
    state.setdefault("agent_flow", []).append(
        flow_step("Skill Agent", "match_skills", reason=f"{len(active_skills)} skill(s) active")
    )
    return state


def _dedupe_skills(skills):
    seen = set()
    result = []
    for skill in skills or []:
        key = _skill_key(skill)
        if key in seen:
            continue
        seen.add(key)
        result.append(skill)
    return result


def _skill_key(skill):
    return skill.get("skill_id") or skill.get("name") or skill.get("path") or str(skill)


def _skill_label(skill):
    return skill.get("skill_id") or skill.get("name") or skill.get("path") or str(skill)
