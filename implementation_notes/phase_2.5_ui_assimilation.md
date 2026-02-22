# Phase 2.5: UI Assimilation - Implementation Plan

## Goal Description

Migrate the high-value UI assets from the legacy `homeflow` project into the new `web` application. This accelerates development by reusing the "5-Layer Stack" visualization logic.

## Prerequisites

- `homeflow` directory exists.
- `web` directory is initialized with Shadcn/UI.

## Proposed Changes

### 1. Dependencies [web/package.json]

- Install libraries used in `homeflow` but missing in `web`:
  - `recharts` (Charts/Graphs)
  - `framer-motion` (Animations)
  - `date-fns` (Date formatting)

### 2. Data Models [web/src/types]

- Copy `homeflow/src/types.ts` to `web/src/types/domain.ts`.
- Ensure compatibility with existing backend models (Tasks).

### 3. Components Migration [web/src/components/views]

Port the core views from `homeflow/src/views/` to Next.js components:

- **StrategyView**: "The Boardroom" (Domains, Scores).
- **TacticalView**: "The Manager" (Projects, Milestones).
- **ExecutionView**: "The Field" (Focus mode).
- **DailyView**: "The Day" (Timeline).

_Note: These will be ported as UI components first, likely using mock data initially, matching the `homeflow` prototype state._

### 4. Integration [web/src/app]

- Create new routes/tabs in the main layout to navigate these views.
- Update `web/src/app/page.tsx` to include the `DailyView` or a comprehensive Dashboard.

## Verification Plan

- **Build**: Ensure `npm run build` passes with new Typescript files.
- **Visual**: Navigate to each new View in the browser and verify it renders correctly (Charts, Layouts).
