# Web Companion Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable FastAPI + Vue 3 MVP for the LunaClaw companion Agent.

**Architecture:** FastAPI owns Agent orchestration, LLM/mock decisions, memory, tools, and validation. Vue renders chat, status, memory, and todo panels from backend responses.

**Tech Stack:** Python FastAPI, pytest, httpx-compatible TestClient, Vue 3, Vite, plain CSS, JSON file storage.

---

## File Structure

- Create backend app files under `backend/`.
- Create frontend app files under `frontend/`.
- Create project docs under `docs/`.
- Keep the root `index.html` untouched and ignored.

## Tasks

### Task 1: Backend Tests First

**Files:**
- Create: `backend/tests/test_agent_mvp.py`
- Create: `backend/tests/conftest.py`

- [ ] Write pytest tests for health, mock chat JSON shape, memory write/read/delete, calculator safety, todo add/list, and study plan generation.
- [ ] Run `python -m pytest backend/tests -q` and verify tests fail because implementation files do not exist.

### Task 2: Backend Implementation

**Files:**
- Create: `backend/main.py`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/agent/*.py`
- Create: `backend/tools/*.py`
- Create: `backend/storage/*.json`

- [ ] Implement storage helpers, memory store, tools, parser, prompt builder, LLM/mock client, and Agent core.
- [ ] Implement FastAPI routes `/health`, `/chat`, `/memory`, `DELETE /memory/{memory_id}`, and `/todos`.
- [ ] Run `python -m pytest backend/tests -q` and verify all backend tests pass.

### Task 3: Frontend Implementation

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/src/**/*`

- [ ] Implement Vue components for chat, input, status, memory, and todo panels.
- [ ] Implement `src/api/chat.js` and emotion rendering map.
- [ ] Run `npm install` in `frontend/`.
- [ ] Run `npm run build` in `frontend/` and verify the production build succeeds.

### Task 4: Documentation

**Files:**
- Create: `README.md`
- Create: `docs/test_cases.md`
- Create: `docs/demo_script.md`

- [ ] Document project intro, stack, startup, environment variables, mock mode, API routes, tests, and future work.
- [ ] Write course-style test cases and one-minute demo script.

### Task 5: Final Verification

- [ ] Run backend tests.
- [ ] Run frontend build.
- [ ] Start backend, call `/health`, and call `/chat` in mock mode.
- [ ] Report exact startup commands and API-key configuration steps.
