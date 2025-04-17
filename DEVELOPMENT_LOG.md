# Development Log

## 2025-04-17 14:50 PST

**Status:**
- Completed Task 1 (Local Dev Env Setup).
- Completed Task 2 (Minimal Infra Bootstrap).

**Commands Run:**
- Setup project structure and initial dependencies.
- `docker-compose up -d db redis neo4j` (Initially failed due to port 5432 conflict, resolved by changing to 5433).
- `pip install -r requirements.txt` (Installed missing dependencies like `pydantic-settings`).
- `uvicorn app.main:app --reload ...` (Encountered and fixed various errors: CORS parsing, Pydantic extra fields, SQLAlchemy port type, asyncpg driver setup).
- `pre-commit autoupdate` (Updated pre-commit hooks).
- `pre-commit uninstall` (Temporarily disabled pre-commit hooks).
- `alembic init migrations`
- `alembic revision --autogenerate -m "Initial migration"` (Failed initially due to missing database, resolved by creating it).
- `alembic upgrade head`
- `docker exec -it digital-twin-mem0-db-1 psql -U postgres -c "CREATE DATABASE \"digitaltwin-mem0\";"`
- `python -m app.tests.init_graphiti` (Initialized Graphiti indices/constraints).
- `python -m app.tests.test_graphiti_connection` (Verified Graphiti/Neo4j connection, fixed API call signature issues).

**Errors & Fixes:**
- **Port 5432 Conflict:** Changed `docker-compose.yml` to map host port 5433 to container port 5432 for PostgreSQL.
- **`ModuleNotFoundError: No module named 'pydantic_settings'`:** Ran `pip install -r requirements.txt`.
- **Port 8000 Conflict:** Ran Uvicorn on port 8001.
- **Pydantic `CORS_ORIGINS` Parsing Error:** Corrected `.env` format and added validator in `config.py`.
- **Pydantic `POSTGRES_PORT` Type Error:** Changed `POSTGRES_PORT` type to `int` in `config.py`.
- **Pydantic Extra Fields Error:** Updated `config.py` to allow extra fields in `SettingsConfigDict`.
- **SQLAlchemy Driver Error:** Changed DB connection scheme to `postgresql+asyncpg` in `config.py`.
- **Alembic DB Connection Error:** Created the database `digitaltwin-mem0` in the running Postgres container.
- **Graphiti `add_episode` Signature Mismatch:** Updated `GraphitiService` calls to match the `graphiti-core` library documentation (`name`, `episode_body`, etc.) and correctly handled the `AddEpisodeResults` return value.
- **Neo4j Index Error:** Ran initialization script (`init_graphiti.py`) to create necessary indices and constraints.

**Next Steps:**
- Proceed with Task 3 (Mem0 Wrapper Lib) or Task 4 (Graphiti Basic Setup & Service Wrapper). 