5.  Design System & UI Tokens

Project Name: Viyugam
Version: 1.0
Architect: Anti-Gravity Architect

1. Design Philosophy

"Tactical Calm"
Viyugam is a tool for high-performance individuals. The interface should feel like a cockpit: high data density, dark mode by default, and minimal distractions. It splits into two distinct visual languages:

The Hacker Console (CLI): Text-heavy, keyboard-driven, green-screen retro futurism.

The Field Companion (PWA): Touch-optimized, card-based, fluid animations.

2. Core Tokens (Tailwind Config)

2.1. Color Palette (Dark Mode First)

Backgrounds:

bg-background: #09090b (Zinc 950 - Deep Void)

bg-card: #18181b (Zinc 900)

bg-muted: #27272a (Zinc 800)

Primary (The "Strategy" Color):

text-primary: #2dd4bf (Teal 400 - Clarity/Vision)

bg-primary: #14b8a6 (Teal 500)

Semantic Colors (The Resources):

Energy (Vitality): #f472b6 (Pink 400) -> #db2777 (Pink 600)

Finance (Wealth): #fbbf24 (Amber 400) -> #d97706 (Amber 600)

Time (Urgency): #60a5fa (Blue 400) -> #2563eb (Blue 600)

Risk/Overdue: #f87171 (Red 400)

2.2. Typography

Font Family (Web): Geist Sans (UI) + Geist Mono (Data/Code).

Font Family (CLI): User's Terminal Font (Recommended: JetBrains Mono or Fira Code).

3. CLI Design System (rich Library)

The CLI uses the rich library to create a TUI (Text User Interface).

Dashboard Layout: Grid-based.

Top Left: Daily Schedule (Time blocked).

Top Right: Resource Meters (Energy/Money bars).

Bottom: Agent Logs (Streaming text).

Agent Avatars (Text):

[bold red]CEO >[/bold red]

[bold gold]CFO >[/bold gold]

[bold green]COO >[/bold green]

Spinners:

Use status.spinner("dots", color="teal") for "Chairman is thinking".

Use progress_bar for Task Completion and Budget Burn.

4. PWA Design System (Shadcn/UI)

4.1. Mobile Layout Structure

Top Bar: "Season" Indicator (e.g., "Health First" Badge) + User Avatar.

Main Content: Scrollable Feed.

Bottom Bar: \* Home (Dashboard)

Inbox (Center, highlighted)

Finance (Quick Log)

4.2. Key Components

A. The Inbox Card

Input: Auto-expanding text area.

Trigger: Large Floating Action Button (FAB) or Bottom Bar center icon.

Animation: Smooth slide-up drawer (Vaul).

B. The Task Card (Daily View)

Visual: Minimalist row.

Left: Time block (09:00).

Center: Title + Energy Dot (Color coded).

Right: Checkbox (Circle).

Interaction: Swipe right to Complete, Swipe left to Reschedule (Chairman Trigger).

C. The "Bankruptcy" Modal

Trigger: 5+ days inactivity.

Visual: Full-screen overlay.

Content: "Welcome Back. 42 Tasks Overdue."

Action: Single button: "Clean Slate" (Triggers particle effect animation, clears screen).

D. The Boardroom Chat

Visual: Chat interface (bubble style).

Avatars: Distinct icons for CEO/CFO/COO.

Typing Indicator: "The Board is debating..."

5. Iconography (Lucide React)

Strategy (L5): Telescope / Mountain

Tactics (L3): Map / Swords

Tasks (L1): CheckCircle2

Inbox: Sparkles (Because AI processes it)

Finance: Coins / Scale

Energy: Zap / Battery

Resilience: ShieldCheck
