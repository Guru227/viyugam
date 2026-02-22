1.  Technology Stack & Dependencies

Project Name: Viyugam
Version: 1.1
Architect: Anti-Gravity Architect

1. Core Infrastructure (Cloud & Hosting)

Compute (Backend): Google Cloud Run (Serverless Container).

Why: Scales to zero, handles Python/FastAPI efficiently, low cost for personal use.

Database: MongoDB Atlas (Serverless Instance).

Why: Flexible schema for complex nested objects (like Agent logs and Boardroom transcripts), native JSON support, and built-in vector search.

Authentication: Clerk.

Why: Handles complex auth (Device flows for CLI, Social login for PWA) out of the box.

2. Backend (The "Brain")

Language: Python 3.11+

Framework: FastAPI

Why: Native Pydantic integration, high performance, auto-generated OpenAPI docs for the CLI client.

ODM (Object Document Mapper): Beanie (built on Motor).

Role: Async ODM that bridges MongoDB and Pydantic v2. Allows strict schema validation within a NoSQL environment.

AI/LLM Interface: google-generativeai (Google Gen AI SDK).

Model: Gemini 2.0 Flash (High-speed tasks, L2 Chairman), Gemini 2.0 Pro (Reasoning, Boardroom simulations).

Vector Search: MongoDB Atlas Vector Search.

Role: Native vector indexing on the journals and tasks collections. Eliminates the need for a separate vector DB.

Task Scheduling: APScheduler (Python).

Role: Runs the "Bankruptcy" checks and nightly "Resilience" protocols.

3. Client A: The Terminal (CLI)

Framework: typer

Role: Command-line argument parsing.

UI/Formatting: rich

Role: Dashboards, tables, markdown rendering in terminal, spinners for AI waiting states.

Config Management: python-dotenv + PyYAML (for Constitution/Seasonality).

Network: httpx

Role: Async HTTP client to communicate with the FastAPI backend.

4. Client B: The Mobile PWA (Web)

Framework: Next.js 14 (App Router).

Why: Robust routing, server actions, easy PWA configuration.

Language: TypeScript.

PWA Enabler: next-pwa.

UI System: Tailwind CSS + Shadcn/UI.

Why: Fast, accessible, aesthetic components (Skeleton loaders, Dialogs).

State Management: zustand.

Role: Lightweight client state for the "Inbox" capture flow.

Icons: lucide-react.

5. Development & DevOps Tools

Package Manager: poetry (Python) / pnpm (Node).

Linting/Formatting: ruff (Python) / biome or eslint (TS).

Containerization: Docker (Dockerfile for FastAPI backend).

Version Control: Git (GitHub).

Env Management: .env (Local) / Google Secret Manager (Production).

6. External APIs

Google Gemini API: Core Intelligence.

Clerk API: User Management.

Optional: plaid-python (Future scope: Bank sync automation).
