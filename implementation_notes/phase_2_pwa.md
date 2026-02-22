# Phase 2: The Field Companion (PWA) - Implementation Notes

## Objective

Build the Mobile-First PWA interface for capturing thoughts and viewing tasks.

## Key Decisions

- **Tech Stack**: Next.js 14, TailwindCSS, Shadcn/UI.
- **State Management**: React Query (`@tanstack/react-query`) for API data caching.
- **DevEx**: Created `dev.py` to auto-assign ports (Backend: 8000+, Web: 3000+) and link them via `NEXT_PUBLIC_API_URL`.

## Features

- **Auth**: Integrated Clerk Login/Signup pages.
- **Inbox**: "Quick Capture" text area connected to `POST /agents/process-inbox`.
- **Dashboard**: Simple list of tasks fetched from `GET /tasks`.

## Migration Note

During restructuring, local fonts broke. Switched to `next/font/google` (Inter) for stability.
