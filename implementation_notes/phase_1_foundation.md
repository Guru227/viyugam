# Phase 1: The Foundation - Implementation Notes

## Objective

Establish the core infrastructure for Viyugam, moving from zero to a reliable backend capable of running AI agents.

## Key Decisions

- **Monorepo**: chosen structure with `backend/` (Python/FastAPI) and `web/` (Next.js).
- **Database**: `mongodb` + `beanie` ODM. Used `mongomock-motor` for robust local dev without external deps.
- **Auth**: `Clerk` selected. Implemented `auth.py` with mock Fallback for CLI initially, then transition to Real JWT verification.
- **CLI**: Built `app/cli.py` for quick interaction (Capture, List).

## Challenges & Solutions

- **DB Connection**: Initial issues with empty default ENV vars. Solved by updating `config.py` to robustly handle `.env` loading and adding explicit keys.
- **Port Conflicts**: Running multiple agents caused conflicts on 8000. Solved in Phase 2 with `dev.py`.
