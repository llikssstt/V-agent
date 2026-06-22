def generate_study_plan(goal, duration):
    goal_text = str(goal or "完成当前任务").strip()
    duration_text = str(duration or "一段时间").strip()
    steps = [
        f"先用 10 分钟把“{goal_text}”拆成 3 个小块。",
        "选择最容易开始的一块，先完成一个可见的小结果。",
        "中途留 5 分钟缓冲，避免计划直接变成精神内耗。",
        "最后 10 分钟检查成果，记录下一步。",
    ]
    return {
        "ok": True,
        "goal": goal_text,
        "duration": duration_text,
        "steps": steps,
        "plan": f"围绕“{goal_text}”，把 {duration_text} 分成启动、推进、收尾三段来做。",
    }

