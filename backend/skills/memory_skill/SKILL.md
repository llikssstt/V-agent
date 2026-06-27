---
name: memory_skill
description: Use when the user asks LunaClaw to remember, recall, update, or delete information.
triggers:
  - 记住
  - 你还记得
  - 忘记
  - 改成
---

# Memory Skill

Use this skill for memory operations in LunaClaw.

## Rules

1. When the user explicitly says "记住", write a long-term memory.
2. When the user asks "你还记得", retrieve long-term memory and conversation history.
3. When the user says "忘记", soft-delete the matching memory.
4. When the user says "改成", update the matching memory.
5. Do not store sensitive private information.
6. Do not store meaningless casual chat.
7. Memory replies must match LunaClaw's persona.
8. Never pretend to remember. Memory must be persisted.
9. If no relevant memory is found, say so honestly.
