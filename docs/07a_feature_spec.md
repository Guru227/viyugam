7.  Feature Spec: Agent Intelligence (The Brain)

Project Name: Viyugam
Version: 1.1
Component: Backend / Gemini Integration

1. Overview

The Intelligence Layer is driven by Google Gemini 2.0. It is split into two distinct runtime modes to balance latency, cost, and reasoning depth.

Agent

Model

Latency Target

Context Window

Role

The Chairman

gemini-2.0-flash

< 3s

Small (Today's Context)

Tactical Dispatch, Inbox Triage, Conflict Resolution.

The Boardroom

gemini-2.0-pro

~15s

Large (Full Constitution, Financials)

Strategic Planning, Project Approval, Debate Simulation.

2. The Chairman (L2 Tactical Agent)

2.1. Responsibility: The Inbox Triage

Trigger: User runs viyugam process or PWA requests "Auto-Process".

Logic Flow:

Fetch: Unprocessed items from inbox collection.

Prompt Construction:

System: "You are an elite Executive Assistant. Classify inputs into Tasks (L1), Projects (L3), or Notes. Estimate costs."

Input: List of raw text strings.

Output Structure (JSON Mode):

[
{
"original_text": "Buy milk",
"type": "task",
"action": "create",
"task_data": {
"title": "Buy Milk",
"energy_cost": 2,
"estimated_minutes": 15,
"context": "errand"
}
},
{
"original_text": "Launch SaaS",
"type": "project",
"action": "draft_project",
"project_data": { "title": "Launch SaaS" }
}
]

2.2. Responsibility: The Daily Scheduler

Trigger: User runs viyugam plan day or 4:00 AM Cron Job.

Inputs:

List of Active Tasks (Todo).

User Settings (Work Hours Cap).

Calendar Hard Constraints (Sleep: 23:00-07:00).

Current Energy Level (from L1 Journal).

Algorithm (The "Constraint Solver"):

Hard Filter: Remove tasks where financial_cost > remaining_budget.

Soft Filter: If current_energy is "Low", remove tasks with energy_cost > 7.

Time Blocking:

Fill "Deep Work" slots (09:00-12:00) with High Energy/High Priority tasks.

Fill "Shallow Work" slots (14:00-17:00) with Low Energy tasks.

Mandatory: Insert 15m break after every 90m of work.

Overflow: If sum(task_time) > available_time, move lowest priority tasks to backlog.

3. The Boardroom (L3-L5 Strategic Agent)

3.1. Responsibility: The Project Greenlight Debate

Trigger: User creates a Project with High Cost or High Effort.

System Prompt Strategy (Multi-Persona):
We do not use multiple API calls. We use a single Multi-Turn Chat Session with instructions to simulate a dialogue.

Prompt Template:

"You are simulating a Board Meeting for Guru Inc.

The Board Members:

CEO (Vision): Focus on L5 Alignment: {current_l5_theme}.

CFO (Money): Focus on Budget: {budget_status}. Risk-averse.

COO (Time/Energy): Focus on Burnout. Protected Hours: {work_cap}.

The Proposal: '{user_project_proposal}'

Task:

Each member must speak once, analyzing the proposal based on their metric.

They must vote (YES/NO/CONDITIONAL).

The Chairman (You) must summarize the consensus."

3.2. Responsibility: The Seasonal Review (L5)

Trigger: Monthly/Yearly Review.

Logic:

Ingest: All journal entries for the period (Vector Search).

Cluster: Find recurring negative sentiments (e.g., "Tired", "Broke").

Pivot:

If "Tired" cluster is dominant -> Suggest shifting Season to "Health First".

If "Broke" cluster is dominant -> Suggest shifting Season to "Wealth Building".

4. Privacy & Safety Layer

4.1. The PII Middleware

Location: backend/app/core/middleware/pii_redaction.py

Rules:

Regex Match: \b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b (Email).

Regex Match: \d{10} (Phone).

Currency Match: (₹|\$)\s?(\d{1,3}(,\d{3})\*(\.\d+)?).

Process:

Inbound (User -> LLM):

"Pay Suresh ₹50,000" -> "Pay <NAME_1> <AMT_HIGH>"

Outbound (LLM -> User):

"Approved payment of <AMT_HIGH>" -> "Approved payment of ₹50,000"

4.2. Hallucination Guardrails

JSON Mode: All Agents MUST output strict JSON.

Schema Validation: Python Pydantic models validate the LLM output immediately. If validation fails, trigger a retry with the error message.
