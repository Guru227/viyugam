4.  API Contracts (FastAPI/OpenAPI)

Project Name: Viyugam
Version: 1.1
Architect: Anti-Gravity Architect

1. Authentication & Base URL

Base URL: https://api.viyugam.app/v1 (Cloud Run URL)

Auth Header: Authorization: Bearer <CLERK_JWT_TOKEN>

2. Core Endpoints

2.1. Inbox (Capture Flow)

POST /inbox

Purpose: Quick capture from PWA.

Payload:

{ "content": "Buy milk and plan Q3 strategy", "source": "mobile" }

Response: 201 Created { "id": "..." }

GET /inbox

Purpose: Fetch unprocessed items for CLI processing.

Response: 200 OK [ { "id": "...", "content": "..." } ]

2.2. Tasks (Execution Flow)

GET /tasks

Query Params: ?date=2026-01-11&status=todo

Response:

[
{
"id": "...",
"title": "Write API Specs",
"scheduled_time_block": "09:00-11:00",
"energy_cost": 8,
"project_title": "Viyugam MVP"
}
]

POST /tasks

Purpose: Create a fully defined task.

Payload: { "title": "...", "project_id": "...", "estimated_minutes": 60, "energy_cost": 5 }

PATCH /tasks/{id}

Purpose: Update status or reschedule.

Payload: { "status": "done" } or { "scheduled_date": "2026-01-12" }

2.3. Agents (The Intelligence Layer)

POST /agents/process-inbox

Purpose: Triggers Gemini (Chairman) to analyze specific inbox items.

Payload: { "inbox_item_ids": ["..."] }

Response:

{
"suggestions": [
{
"inbox_id": "...",
"classification": "task",
"suggested_task": {
"title": "Buy Milk",
"context": "Errand",
"energy_cost": 2
}
}
]
}

POST /agents/plan-day

Purpose: Triggers Chairman to optimize the schedule for a specific date.

Payload: { "date": "2026-01-11" }

Response:

{
"schedule": [
{ "time": "09:00", "task_id": "..." },
{ "time": "11:00", "type": "break", "duration": 15 }
],
"moved_to_backlog": ["task_id_1", "task_id_2"]
}

POST /agents/boardroom

Purpose: Triggers L3-L5 Strategic Debate.

Payload: { "proposal": "I want to buy a new Mac Studio for ₹2L" }

Response:

{
"transcript": [
{ "agent": "CFO", "text": "Reject. High OpEx impact." },
{ "agent": "CEO", "text": "Approve. Increases productivity." }
],
"consensus": "Approved with conditions",
"summary": "Buy it, but wait until next month's invoice clears."
}

2.4. Resilience (System Ops)

POST /system/bankruptcy

Purpose: Manual trigger of the Bankruptcy Protocol.

Response: { "cleared_tasks_count": 42, "message": "Slate Cleaned." }

GET /system/status

Purpose: Check streak and last login.

Response: { "streak": 5, "last_login": "2026-01-10T10:00:00Z" }

2.5. Journals (Feedback)

POST /journals

Payload:

{
"level": "day",
"date_ref": "2026-01-11",
"energy_score": 4,
"sentiment_score": 6,
"content": "Felt tired after 3pm."
}

Side Effect: Triggers background job to generate embedding and update User Vector Profile.
