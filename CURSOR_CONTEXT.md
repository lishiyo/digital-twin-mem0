# Cursor Context

## 2025-04-17 14:50 PST

**Current Guide Section:** 
- Finished Task 2 (Minimal Infra Bootstrap) from `v0-tasks-backend.md`.
- Preparing to start Task 3 or Task 4.

**What's Working:**
- Local development environment setup (devcontainer/local Python).
- Docker Compose setup for Postgres, Redis, Neo4j.
- Basic FastAPI application (`app/main.py`) runs.
- Configuration loading (`app/core/config.py`) from `.env` works.
- Alembic is configured and initial migrations are applied.
- Database models (User, ChatMessage, Proposal, Vote) are created.
- Graphiti service (`app/services/graph/__init__.py`) connects to Neo4j and can add episodes.
- Test fixtures (`app/tests/conftest.py`) are set up.

**What's Broken/Incomplete:**
- `MemoryService` (`app/services/memory/__init__.py`) is a stub implementation.
- `GraphitiService` search functionality is basic.
- No actual Mem0 integration yet.
- Pre-commit hooks are currently disabled.

**Current Blockers:**
- None.

**Database/Model State:**
- PostgreSQL database `digitaltwin-mem0` exists.
- Tables created via Alembic for User, ChatMessage, Proposal, Vote models.
- Neo4j database is running and initialized with Graphiti indices/constraints.

**Pending Tasks:**
- Decide whether to proceed with Task 3 (Mem0 Wrapper) or Task 4 (Graphiti Wrapper refinement).
- Implement actual Mem0 client logic.
- Implement more advanced Graphiti service functions.
- Re-enable and fix pre-commit hook issues. 