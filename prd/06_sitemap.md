6.  Frontend Sitemap & Route Structure (PWA)

Project Name: Viyugam
Version: 1.0
Architect: Anti-Gravity Architect

1. Route Map (Next.js App Router)

Public Routes

/login - Clerk Authentication Page (Social Login / Email).

/manifest.json - PWA Manifest.

Authenticated Routes (Protected by Middleware)

1.1. Core Workflow

/ (Dashboard)

View: "The Daily Briefing."

Content:

Top Widget: "Season" Focus & Streak Counter.

Main List: Timeline of Today's Tasks.

Bottom Widget: Resource Gauges (Remaining Budget / Energy).

/inbox (Capture & Process)

View: Split View.

Tab 1: Capture: Big text input for quick thoughts.

Tab 2: Process: List of unprocessed items with Agent suggestions ("Approve this classification?").

1.2. The Resource Centers

/finance (The CFO's Office)

View: Dashboard.

Content:

Big Number: "Safe to Spend" (Daily/Weekly).

List: Recent Transactions.

Action: "Log Expense" (Modal).

/projects (Tactical View)

View: List of L3 Projects.

Content: Progress bars, Deadlines, Status (Active/Paused).

Detail View: /projects/[id] - Shows linked tasks and financial spend.

1.3. Strategy & Review

/strategy (L5 Vision)

View: Read-only Vision Board.

Content: L5 Themes, Values, 2026 Goals.

/review (Journaling)

View: Calendar / Log.

Action: "Daily Shutdown" (Wizard flow: Energy -> Mood -> Wins).

1.4. System

/settings

Content: Theme Toggle, Notification Settings, Bankruptcy Sensitivity.

/rescue (Bankruptcy Protocol)

Note: Hidden route, auto-redirected here if SystemState == BANKRUPTCY.

2. Component Hierarchy (Page Level)

A. Dashboard (/page.tsx)

<DashboardLayout>
  <Header user={user} season={season} />
  <ResilienceBanner /> {/* Shows only if streaks broken */}
  
  <Timeline>
    {tasks.map(task => (
      <TaskRow 
        time={task.time} 
        energy={task.energy} 
        onSwipe={() => completeTask(task.id)} 
      />
    ))}
  </Timeline>
  
  <FloatingActionButton onClick={() => router.push('/inbox')} />
</DashboardLayout>

B. Inbox (/inbox/page.tsx)

<InboxLayout>
  <Tabs>
    <Tab value="capture">
      <AutoResizeTextarea placeholder="Dump your brain..." />
      <Button variant="magic" onClick={sendToAgent}>Process with AI</Button>
    </Tab>
    
    <Tab value="review">
      <AgentSuggestionList>
        {suggestions.map(s => (
          <ReviewCard 
            original={s.text} 
            aiProposal={s.taskData} 
            onApprove={approve} 
            onEdit={edit} 
          />
        ))}
      </AgentSuggestionList>
    </Tab>
  </Tabs>
</InboxLayout>

C. Financial Log (/finance/page.tsx)

<FinanceLayout>
  <MetricCard label="Daily Budget Left" value={remaining} trend="down" />
  
  <TransactionList transactions={recent} />
  
  <DrawerTrigger>Log Expense</DrawerTrigger>
  <DrawerContent>
    <ExpenseForm 
      categories={categories} 
      onSubmit={logTransaction} 
    />
  </DrawerContent>
</FinanceLayout>
