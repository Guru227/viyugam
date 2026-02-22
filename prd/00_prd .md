0.  Product Requirements Document (PRD)

Project Name: Viyugam (வியூகம்)
Version: 1.0
Status: Approved
Classification: Personal Resource Planning System (Life OS)

1. Executive Summary

Viyugam is a hybrid "Life Operating System" that applies Enterprise Resource Planning (ERP) and Agile Product Management principles to personal life. It treats "Life as a Product," enabling the user to align daily execution (L1) with long-term strategic vision (L5) through a cascading 5-layer architecture.

Unlike standard to-do lists, Viyugam integrates Finance and Energy as equal constraints alongside Time. It utilizes a "Boardroom" of AI Agents (CEO, CFO, COO, etc.) to negotiate trade-offs and a "Chairman" agent to optimize daily schedules.

2. Problem Statement

The Alignment Gap: High-level goals (L5) rarely translate effectively into daily tasks (L1).

Resource Blindness: Standard tools track time but ignore financial liquidity and cognitive energy, leading to burnout or overspending.

Maintenance Tax: High-friction data entry causes system abandonment.

Resilience Failure: Missing a few days creates a "Wall of Red" (overdue tasks), causing psychological rejection of the tool.

3. Core Philosophy: The 5-Layer Stack

The system operates on a bi-directional flow of information.

Layer

Name

Function

Time Horizon

Key Agent

L5

Strategic View

Vision, Themes, Values

1-3 Years

The Boardroom (CEO)

L4

Strategic Interface

Quarterly Planning & Budget Allocation

1-3 Months

The CFO/CPO

L3

Tactical View

Projects & Milestones (Golden Triangle)

Weeks

The Project Manager

L2

Tactical Interface

Weekly/Daily Dispatch & Energy mgmt

Days

The Chairman (Lite)

L1

Daily View

Execution & Feedback

Hours

The User

4. Functional Requirements

4.1. The Resource Engine (The Constraints)

Multi-Parameter Optimization: Every entity (Task/Project) must be weighed against three costs:

Time: (Hours/Minutes).

Energy: (Cognitive Load 1-10).

Finance: (Monetary Cost).

Seasonality Config: The system must accept a "Season" configuration (e.g., "Health First" or "Revenue Sprint") that weights these parameters differently for conflict resolution.

4.2. The Agentic Architecture

The Boardroom (L3-L5): A multi-agent debate simulation where persona-based agents (CEO, CFO, COO, CLO, CHO) discuss trade-offs for major decisions.

The Chairman Lite (L2): A low-latency heuristic agent that resolves daily scheduling conflicts (Time vs. Energy) without user intervention.

The Feedback Loop:

L1 Shutdown: Daily capture of Energy/Mood/Completion.

L3 Retro: Monthly analysis of process/budget.

L5 Summit: Yearly value alignment.

4.3. Feature Modules

The Inbox (Capture): A high-speed, friction-free staging area for raw thoughts (via Mobile PWA) to be processed later by agents.

The Financial Controller:

Must track "Budgets" vs "Actuals."

Must distinguish between OPEX (Spending) and CAPEX/Allocation (Investing).

Must block L3 Projects if liquidity is insufficient.

Resilience Protocol ("Bankruptcy"): A specific workflow to handle system neglect. If inactive > 5 days, automatically archive overdue tasks to the "Backlog" and reset streaks to prevent user demoralization.

5. User Interfaces (Hybrid Model)

Primary (CLI): typer-based terminal interface for deep work, planning, coding, and "Hacker Mode" interaction.

Secondary (PWA): Mobile-first React/Next.js web app for "Quick Capture," "Daily Read-Only View," and "Financial Logging" on the go.

6. Non-Functional Requirements

Privacy & Redaction: PII (Personally Identifiable Information) middleware must redact sensitive financial numbers or names before sending prompts to the LLM.

Latency: CLI interactions (L1/L2) must feel instant (<500ms for local logic, <3s for Chairman decisions).

Offline Capability: The PWA must support offline capture (sync to server when online).

Memory Persistence: The system must utilize a Vector Database (Episodic Memory) to learn from past feedback (e.g., "User hates meetings after 4 PM").

7. Success Metrics

Alignment Score: % of completed L1 tasks that map directly to an active L5 Goal.

Resilience Rate: Time required to recover from a 7-day hiatus (Target: < 5 minutes).

Friction Index: Time spent managing the tool vs. doing the work (Target: < 5% of total time).
