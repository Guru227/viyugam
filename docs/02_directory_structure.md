02a. Directory Structure (Monorepo)

Project Name: Viyugam
Version: 1.1
Architect: Anti-Gravity Architect

1. Top-Level Overview

The project is structured as a Monorepo containing three distinct packages: the Brain (Backend), the Hacker Console (CLI), and the Field Companion (Web).

viyugam-monorepo/
├── backend/ # FastAPI + Gemini Agents (The Brain)
├── cli/ # Typer Application (Desktop Client)
├── web/ # Next.js PWA (Mobile Client)
├── docker-compose.yml # Local development orchestration
├── README.md
└── .gitignore

2. Backend Structure (/backend)

Technique: Domain-Driven Design (Lightweight)

backend/
├── app/
│ ├── **init**.py
│ ├── main.py # FastAPI Entry Point
│ │
│ ├── agents/ # The Intelligence Layer
│ │ ├── **init**.py
│ │ ├── base.py # Base Agent Class (Gemini Wrapper)
│ │ ├── chairman.py # L2 Logic (Scheduler/Optimizer)
│ │ ├── boardroom.py # L3-L5 Multi-Agent Simulation
│ │ └── prompts/ # System Prompts (The "Constitution")
│ │ ├── system_chairman.md
│ │ ├── system_cfo.md
│ │ └── ...
│ │
│ ├── core/ # Infrastructure
│ │ ├── config.py # Pydantic Settings (Env Vars)
│ │ ├── security.py # Clerk JWT Validation
│ │ └── middleware/
│ │ └── pii_redaction.py # The Privacy Shield (Regex/Tokenization)
│ │
│ ├── models/ # Beanie (MongoDB) Schemas
│ │ ├── **init**.py
│ │ ├── user.py # User Settings & Seasonality
│ │ ├── tasks.py # L1 Tasks & L3 Projects
│ │ ├── finance.py # Budgets & Transactions
│ │ └── journal.py # Feedback & Inbox
│ │
│ ├── routers/ # API Endpoints
│ │ ├── v1/
│ │ │ ├── tasks.py
│ │ │ ├── finance.py
│ │ │ ├── agents.py # Triggering the AI
│ │ │ └── inbox.py
│ │ └── api.py # Router aggregator
│ │
│ └── services/ # Business Logic (Non-AI)
│ ├── resilience.py # Bankruptcy Protocol Logic
│ └── finance_calc.py # Pure Python Math (Budget checks)
│
├── tests/ # Pytest Suite
├── Dockerfile # Cloud Run Config
├── pyproject.toml # Poetry Dependencies
└── .env.example

3. CLI Structure (/cli)

Technique: Command-Pattern

cli/
├── viyugam/
│ ├── **init**.py
│ ├── main.py # Typer App Entry Point
│ ├── config.py # Local Auth Token Storage
│ │
│ ├── commands/ # The Verbs
│ │ ├── plan.py # `viyugam plan` (Day/Week)
│ │ ├── do.py # `viyugam do` (Agent Assist)
│ │ ├── review.py # `viyugam review` (Journals)
│ │ ├── finance.py # `viyugam finance`
│ │ └── system.py # `viyugam rescue` / `login`
│ │
│ ├── api_client/ # HTTP Layer
│ │ ├── client.py # httpx wrapper with Auth headers
│ │ └── endpoints.py # URL mapping
│ │
│ └── ui/ # Rich Components
│ ├── dashboard.py # The Daily View Layout
│ ├── spinners.py # "Chairman is thinking..."
│ └── tables.py # Task/Budget Tables
│
├── pyproject.toml
└── README.md

4. Web Structure (/web)

Technique: Next.js App Router (Mobile First)

web/
├── public/ # Icons, Manifest.json
├── src/
│ ├── app/ # App Router
│ │ ├── layout.tsx # ClerkProvider / ThemeProvider
│ │ ├── page.tsx # Dashboard (Daily View)
│ │ ├── inbox/ # Quick Capture Page
│ │ │ └── page.tsx
│ │ ├── finance/ # Quick Log Page
│ │ │ └── page.tsx
│ │ └── login/
│ │ └── page.tsx
│ │
│ ├── components/
│ │ ├── ui/ # Shadcn Components (Button, Card...)
│ │ ├── layouts/ # Mobile Nav, Bottom Bar
│ │ └── features/ # Domain Components
│ │ ├── InboxInput.tsx
│ │ └── TaskList.tsx
│ │
│ ├── lib/
│ │ ├── api.ts # Fetch wrapper for Backend
│ │ ├── store.ts # Zustand Store (Offline state)
│ │ └── utils.ts # Tailwind Merge
│ │
│ └── types/ # TypeScript Interfaces (Mirroring Python Models)
│ └── index.ts
│
├── next.config.js # PWA Config
├── tailwind.config.ts
├── package.json
└── tsconfig.json
