8.  Implementation Roadmap (Phased Rollout)

Project Name: Viyugam
Version: 1.0
Architect: Anti-Gravity Architect

Phase 1: The Foundation (Days 1-3)

Goal: A working API that stores Tasks and runs the Basic L2 Chairman logic.

[ ] 1.1. Setup Repo: Monorepo with poetry (Backend) and pnpm (Web).

[ ] 1.2. Database: Init MongoDB Atlas. Implement Beanie models for User, Task, Inbox.

[ ] 1.3. Auth: Configure Clerk. Integrate JWT validation middleware in FastAPI.

[ ] 1.4. Agent V1: Build the "L2 Chairman" prompt. Implement POST /agents/process-inbox using Gemini 2.0 Flash.

[ ] 1.5. CLI V1: Build viyugam login, viyugam capture, and viyugam list.

Phase 2: The Field Companion (Days 4-7)

Goal: A Mobile PWA that allows capturing thoughts and viewing the plan.

[ ] 2.1. PWA Scaffold: Next.js + Shadcn/UI + Tailwind.

[ ] 2.2. Auth UI: Clerk Login page.

[ ] 2.3. Inbox Feature: "Quick Capture" UI -> POST /inbox.

[ ] 2.4. Dashboard: Read-only view of GET /tasks.

[ ] 2.5. Deployment: Deploy Backend to Cloud Run, Frontend to Vercel.

Phase 3: The Boardroom (Days 8-12)

Goal: Implement Strategy (L5), Projects (L3), and Financial Constraints.

[ ] 3.1. DB Update: Add Theme, Project, Budget, Transaction models.

[ ] 3.2. Agent V2: Build "L3 Boardroom" prompt (Multi-persona debate).

[ ] 3.3. Finance Logic: Implement the "Safe to Spend" calculator.

[ ] 3.4. CLI V2: Add viyugam strategy and viyugam finance.

Phase 4: Resilience & Memory (Days 13-15)

Goal: Make the system anti-fragile and personalized.

[ ] 4.1. Vector Search: Enable Atlas Vector Search. Implement Embeddings for Journals.

[ ] 4.2. Bankruptcy Protocol: Implement the "Resilience Watcher" (APScheduler) and the Reset Endpoint.

[ ] 4.3. Privacy: Implement the PII Redaction Middleware.

[ ] 4.4. Testing: UAT of the full loop (Capture -> Plan -> Execute -> Review).

Critical Milestones

Milestone A (The "Brain" Alive): You can curl the API and Gemini organizes your raw text into JSON tasks.

Milestone B (The Pocket Companion): You can add a task from your phone while walking.

Milestone C (The Board Meeting): You propose a project, and the CLI prints a debate transcript between the CEO and CFO.
