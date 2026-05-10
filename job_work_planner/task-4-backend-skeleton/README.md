# Backend — Job Work Planner

## Overview
This is the Python backend for the Job Work Planner project. It uses FastAPI, Alembic for migrations, and follows a modular structure.

## Structure
- `app/` — Main application code
  - `core/` — Core services and utilities
  - `db/` — Database-related code
  - `routes/` — API route definitions
  - `schemas/` — Pydantic schemas
  - `services/` — Business logic/services
- `alembic/` — Database migrations
- `scripts/` — Utility scripts

## Setup
1. Create a virtual environment and activate it.
2. Install dependencies: `pip install -r requirements.txt`
3. Set up your `.env` file (see `.env.example` if available).
4. Run migrations: `alembic upgrade head`
5. Start the server: `uvicorn app.main:app --reload`

## Notes
- Do not commit `.env`, `__pycache__`, or database files.
- See the root `README.md` for more info.
