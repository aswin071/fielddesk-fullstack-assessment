# Cross-component Tests

Backend tests live beside Django modules and frontend tests live beside frontend features. This directory is reserved for Docker Compose smoke tests and end-to-end workflows spanning multiple components.

The current automated matrix contains 98 PostgreSQL-backed backend tests and one frontend Dispatcher workflow integration test. The release gate also runs Ruff, frontend lint, TypeScript/Vite production compilation, Django's production deployment check, dependency audits, migration drift checks and live Docker Compose smoke tests.
