# ADR-0001: Frontend Platform - Next.js + React + Shadcn on Vercel

**Status:** Accepted  
**Date:** 2026-02-26

## Context

1. Employee-facing application runs at `my.bebang.ph`.
2. Workspace and architecture docs identify a separate `bei-tasks` frontend repo.
3. Current frontend stack is documented in architecture references and package metadata.

## Decision

Use `Next.js + React + Tailwind/Shadcn` in `bei-tasks`, deployed through Vercel production workflow for `my.bebang.ph`.

## Consequences

1. Frontend changes follow Vercel deployment and cache-bust verification workflow.
2. API interactions remain proxy-first through Next.js handlers into Frappe endpoints.
3. RBAC governance remains defined in frontend role matrix (`bei-tasks/lib/roles.ts`).

## Evidence

1. `docs/00_START_HERE.md`
2. `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md`
3. `docs/architecture/SOLUTION_ARCHITECTURE_DOCUMENT.md`
4. `.claude/rules/deployment.md`

