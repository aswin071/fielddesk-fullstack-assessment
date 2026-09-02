# AI usage disclosure

AI-assisted development tools were used during this assessment. I remain responsible for reviewing, testing, understanding and explaining the submitted implementation.

## Usage summary

| Tool and model, if known | Files, features or sections affected | Purpose of use | Nature of the output | How I reviewed or tested it |
| --- | --- | --- | --- | --- |
| OpenAI Codex (GPT-5) | `docs/` and architectural decisions | Requirement analysis and specification-driven design | Initial architecture, security, data-model and module specifications | Compared the specifications with `docs/ASSESSMENT.md` and traced requirements to implementation and tests |
| OpenAI Codex (GPT-5) | `backend/`, `database/` and `worker/` | Backend implementation and review | Django models, serializers, views, transactional services, migrations, Celery tasks and tests | Ran Django checks, migration drift checks, Ruff and the PostgreSQL-backed test suite; manually tested role and tenant boundaries |
| OpenAI Codex (GPT-5) | Scheduling and progress-event modules | Concurrent scheduling and idempotent offline-event handling | Row-lock, advisory-lock, constraint, state-transition and error-handling logic | Ran overlap, boundary, simultaneous scheduling, sequential duplicate and concurrent duplicate tests |
| OpenAI Codex (GPT-5) | Attachments, audit, reporting, notifications and realtime modules | Security and operational workflow implementation | Upload validation, quota locking, immutable history, CSV safety, Celery retry and authenticated SSE logic | Ran permission, tenant-isolation, file-spoofing, quota, rollback, retry, reconnect and failure-tolerance tests |
| OpenAI Codex (GPT-5) | `frontend/` | ERP interface implementation and review | React screens, role-aware navigation, typed API client, TanStack Query state and realtime invalidation | Manually tested Owner, Dispatcher and Technician workflows and ran Vitest, ESLint and the TypeScript/Vite build |
| OpenAI Codex (GPT-5) | Root configuration, runbooks and `candidate-submission/` | Container setup, production review and submission preparation | Docker configuration, security recommendations, verification guidance and documentation drafts | Started the full Compose stack, checked readiness and logs, reviewed generated text and corrected it against actual behaviour |

## Details

### 1. What I asked the tool to help with

I first read the assessment and identified the main business flow. I then asked Codex to help analyse an earlier modular Django architecture and adapt the same overall approach to FieldDesk. I used it to break the work into specifications and phases, implement the modules, review security and concurrency, create tests, troubleshoot failures and prepare operational documentation.

### 2. What was generated or substantially modified

AI materially assisted with the SDD documents and with most application areas: Django models and APIs, authentication, organisation scoping, scheduling, progress events, attachments, audit history, reporting, notifications, realtime updates, the React frontend, Docker configuration and automated tests. It also assisted with the technical-notes draft and recording checklist.

### 3. What I changed after receiving the output

I reviewed the domain terminology and used OrganisationUser instead of the less clear membership name. I confirmed Dispatcher as the operational supervisor role, adjusted role behaviour and frontend wording, checked model relationships and refined validation, configuration and documentation where the generated output did not match the assessment or the final repository layout.

### 4. How I verified correctness, security and compatibility

I ran the application through Docker Compose and manually tested the main Owner, Dispatcher and Technician workflows using both seeded organisations. I checked cross-organisation access, scheduling conflicts, progress updates, attachment permissions, realtime refresh and notification outcomes. I ran the PostgreSQL-backed backend tests, frontend workflow test, migration checks, Django checks, Ruff, ESLint and the TypeScript/Vite production build. I also reviewed the transaction boundaries, organisation-scoped selectors, permission classes and sensitive-data handling.

### 5. Output I rejected or corrected

I did not accept output that conflicted with the assessment, used unclear terminology, weakened organisation isolation or did not match the existing repository templates. I corrected command formatting, preserved the official Gatlier documents, removed generated caches and build output, and revised documentation that was incomplete, duplicated or inconsistent with the implemented behaviour.

## Candidate confirmation

- [x] I have disclosed all AI-assisted work in this submission.
- [x] I personally reviewed every submitted file.
- [x] I can explain and modify every part of the implementation.
- [x] I independently ran the documented tests and checks.
- [x] I did not submit confidential or proprietary third-party material.

Candidate name: Aswin K

Date: 2026-09-03
