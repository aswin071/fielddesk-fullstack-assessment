# FieldDesk Full-Stack Engineering Assessment

This practical assessment is conducted by **Gatlier** to evaluate full-stack engineering ability, with particular emphasis on backend correctness, security, database design, testing and production awareness.

FieldDesk is a fictional field-service application created solely for this assessment. Candidates are expected to build a working application, explain their technical decisions and take ownership of everything they submit.

## Start here

1. Read the complete [assessment brief](docs/ASSESSMENT.md).
2. Review the [evaluation criteria](docs/EVALUATION.md).
3. Follow the [submission instructions](docs/SUBMISSION.md).
4. Complete the [technical notes](candidate-submission/TECHNICAL_NOTES.md) and [AI usage disclosure](candidate-submission/AI_USAGE.md).
5. Raise questions or blockers through a GitHub Issue in this repository.

## Run the completed submission

Docker Desktop with Docker Compose is required. From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api python manage.py seed_fielddesk --reset-passwords
docker compose ps
Invoke-RestMethod http://localhost:8000/health/ready
```

Open the ERP frontend at `http://localhost:5173`. The API is available at `http://localhost:8000/api/v1/`. The seed command creates Northstar Maintenance and Harborview Services with Owner, Dispatcher and Technician accounts documented in [the technical notes](candidate-submission/TECHNICAL_NOTES.md).

Run the verification suite with:

```powershell
docker compose exec api python manage.py makemigrations --check --dry-run
docker compose exec api pytest -q
docker compose exec api ruff check .
docker compose exec frontend npm run test
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

The implementation architecture and module specifications are indexed in [the FieldDesk design documentation](docs/README.md).

## Required stack

- React or Next.js with TypeScript
- Node.js with TypeScript
- PostgreSQL
- Redis with a suitable job queue
- Docker Compose

Libraries and architectural patterns are the candidate's choice. Significant decisions and trade-offs should be documented.

## What to submit

- A working frontend, API and background worker
- Database migrations and seed data
- Automated tests
- Docker-based local setup
- Clear technical documentation
- Completed submission templates
- A pull request from the candidate's fork
- A 10–15 minute screen recording
- The final commit SHA

AI-assisted development tools are permitted. Every use must be disclosed clearly, including the tools used, the files or sections affected, the purpose of the assistance and how the output was verified. The candidate remains responsible for the correctness, security and maintainability of all submitted work.

There is no prescribed visual design. A clear, usable interface is sufficient; engineering quality is the main consideration.

## Communication

Use GitHub Issues for all assessment questions, assumptions and technical blockers. This keeps clarifications visible and ensures every candidate receives consistent information.

Please do not include confidential information, credentials or code from a current or previous employer.

---

**Conducted by Gatlier**
