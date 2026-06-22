ALLOWED_EMOTIONS = {"neutral", "happy", "sad", "thinking", "surprised", "serious"}
ALLOWED_TOOLS = {"none", "time", "calculator", "todo", "study_plan"}
ALLOWED_MEMORY_ACTIONS = {"none", "read", "write", "delete"}


def normalize_emotion(value):
    return value if value in ALLOWED_EMOTIONS else "neutral"


def normalize_tool(value):
    return value if value in ALLOWED_TOOLS else "none"


def normalize_memory_action(value):
    return value if value in ALLOWED_MEMORY_ACTIONS else "none"

