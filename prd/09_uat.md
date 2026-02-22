9.  User Acceptance Testing (UAT) Checklist

Project Name: Viyugam
Version: 1.0
Tester: Guru (The User)
Status: Draft

1. The "Hacker" Loop (CLI & Backend)

1.1. Authentication & Security

[ ] Login Flow: Run viyugam login. Does the browser open? Does the CLI receive the token successfully?

[ ] Token Expiry: If the token expires, does the CLI prompt for re-login gracefully (no stack trace)?

[ ] PII Shield (Crucial):

Input: viyugam inbox add "Transfer ₹50,000 to Suresh"

Check Logs: Verify that the prompt sent to Gemini contains <MONETARY_VALUE> or <REDACTED>, NOT "₹50,000".

Output: Verify the Task created says "Transfer ₹50,000..." (Token restoration worked).

1.2. The Chairman (L2 Agent)

[ ] Inbox Triage:

Input: "Buy milk" and "Build the SaaS backend".

Result: Agent correctly identifies "Buy milk" as Task (L1) and "Build SaaS" as Project (L3).

[ ] Constraint Solver (Time):

Input: Add 10 hours of tasks to a day with an 8-hour cap.

Result: Agent moves low-priority tasks to backlog automatically.

[ ] Constraint Solver (Energy):

Input: Set "Current Energy" to Low (3/10).

Result: Agent refuses to schedule "Deep Work" tasks, or warns the user.

1.3. The Boardroom (L3-L5 Agent)

[ ] The CFO Veto:

Scenario: Remaining Budget = ₹10k. Propose Project Cost = ₹50k.

Result: The CFO Agent explicitly votes NO in the transcript.

[ ] The CEO Alignment:

Scenario: Propose a project unrelated to any L5 Theme.

Result: CEO Agent asks: "Which strategic goal does this serve?"

2. The "Field" Loop (Mobile PWA)

2.1. Capture Speed

[ ] Load Time: Does the PWA load the "Inbox" input within 1.5 seconds on 4G?

[ ] Quick Capture: Type "Idea", hit Enter. Does the input clear immediately (optimistic UI) before the API confirms?

2.2. Visualization

[ ] Daily View: Do tasks sync from CLI to PWA instantly?

[ ] Finance Log: Log an expense on PWA (-₹500). Check CLI viyugam finance status. Is the budget reduced?

3. The "Resilience" Protocol

3.1. The Bankruptcy Trigger

[ ] Simulation: Manually set last_login_at in DB to 7 days ago.

[ ] Lockout: Attempt to use the CLI. Does it refuse commands and say "System Paused"?

[ ] Recovery:

Go to /rescue on PWA. Click "Fresh Start".

Verify: All old tasks are backlog.

Verify: Streak is 0.

Verify: CLI is unlocked.

4. Performance & Reliability

4.1. Latency

[ ] Agent Triage: Does viyugam process take < 5 seconds for 5 items? (Gemini Flash).

[ ] Boardroom Debate: Does the debate generation take < 20 seconds? (Gemini Pro).

4.2. Error Handling

[ ] API Down: Kill the Backend. Run a CLI command. Does it say "Brain disconnected" (friendly error)?

[ ] Hallucination Check: Feed the Agent nonsense ("Colorless green ideas sleep furiously"). Does it categorize it as "Note" or ask for clarification, rather than crashing?
