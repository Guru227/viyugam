7.  Feature Spec: Resilience Protocol ("The Bankruptcy System")

Project Name: Viyugam
Version: 1.0
Component: Backend / Scheduler

1. The Core Concept

The Problem: Productivity systems fail when "Life Happens." A user misses 5 days due to illness, returns to 50 overdue tasks ("The Wall of Red"), feels overwhelmed, and abandons the tool.
The Solution: Viyugam treats consistency as a "Streak." When the streak is broken significantly, the system detects a "State of Chaos" and offers a "Bankruptcy Settlement"—wiping the debt (overdue tasks) to allow a fresh start.

2. Logic & Triggers

2.1. State Definition

The User Account moves between three states:

FLOW (Active): last_login < 48 hours. Standard operation.

DRIFT (Warning): 48 hours < last_login < 5 days. Agents suggest "Catch-up" plans.

BANKRUPTCY (Critical): last_login > 5 days. System lock-down.

2.2. The Bankruptcy Trigger

Mechanism: APScheduler job runs nightly at 00:00 UTC.
Check:

if (now - user.last_login_at).days > 5:
user.state = "BANKRUPTCY"
notification.send("System Paused. Resilience Protocol Active.")

3. The Recovery Workflow (UI Interaction)

Step 1: The Gate (PWA/CLI)

When a user in BANKRUPTCY state logs in, they are redirected to /rescue.

Visual: Dark screen, calming animation (particle dust).

Message: "Welcome back, Guru. You've been away for 7 days. The Boardroom has paused operations to protect your focus."

Step 2: The Settlement (Backend Logic)

When user clicks "Fresh Start":

The Purge (L1 Tasks):

Identify all tasks with status != 'done' AND scheduled_date < TODAY.

Action: Bulk update status = 'backlog', scheduled_date = NULL, is_overdue = False.

Note: We do not delete them. We move them to the "Icebox."

The Freeze (L3 Projects):

Identify all Active Projects.

Action: Update status = 'paused'.

Reason: You cannot have 5 active projects on your first day back.

The Reset (Metrics):

Set current_streak = 0.

Set energy_score_prediction = LOW (Assume recovery mode).

Step 3: The Morning After

The Chairman generates a specific "Recovery Schedule":

Constraint: Max 4 hours work (vs standard 8).

Focus: 1 "Easy Win" Task + 1 "Critical Fire" Task.

Mantra: "Zero pressure today. Just momentum."

4. Technical Implementation

4.1. Scheduler Job (backend/app/services/resilience.py)

async def nightly_resilience_check(): # 1. Find inactive users
threshold = datetime.now() - timedelta(days=5)
users = await User.find(User.last_login_at < threshold).to_list()

    for user in users:
        # 2. Flag them
        user.resilience_status = "BANKRUPTCY"
        await user.save()

        # 3. Optional: Send Email via Clerk/SendGrid
        # "Viyugam is paused. Come back when you are ready."

4.2. The Reset Endpoint (POST /system/bankruptcy)

@router.post("/bankruptcy")
async def declare_bankruptcy(user: User = Depends(get_current_user)): # 1. Archive Tasks
result = await Task.find(
Task.user_id == user.id,
Task.scheduled_date < date.today(),
Task.status != TaskStatus.DONE
).update({"$set": {"status": TaskStatus.BACKLOG, "scheduled_date": None}})

    # 2. Pause Projects
    await Project.find(
        Project.user_id == user.id,
        Project.status == ProjectStatus.ACTIVE
    ).update({"$set": {"status": ProjectStatus.PAUSED}})

    # 3. Restore User State
    user.resilience_status = "FLOW"
    user.last_login_at = datetime.now()
    await user.save()

    return {"cleared_count": result.modified_count, "message": "Slate Cleaned"}
