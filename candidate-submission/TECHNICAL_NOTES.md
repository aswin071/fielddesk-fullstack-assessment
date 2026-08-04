# Technical notes

Complete this document as part of the submission.

## Candidate

- Name:
- GitHub username:
- Final commit SHA:
- Screen-recording link:

## Local setup

Document the exact commands required to configure and start the application.

## Sample accounts

List the seeded organisations, roles and sample login credentials. Use assessment-only credentials.

## Verification results

| Check | Command | Result |
| --- | --- | --- |
| Backend tests |  |  |
| Frontend tests |  |  |
| Integration tests |  |  |
| Lint |  |  |
| Build |  |  |

## Architecture

Describe the major components, their responsibilities and important dependencies.

## Database design

Explain the principal tables, relationships, constraints, indexes and migration strategy.

## Authentication, roles and organisation isolation

Explain how authentication works and where organisation and role restrictions are enforced.

## Transactions, idempotency and concurrency

Explain the transaction boundaries, duplicate-event handling and concurrent scheduling protection.

## Background jobs

Explain delivery guarantees, retries, backoff, duplicate prevention and permanent failure handling.

## Real-time updates

Explain connection authentication, organisation isolation, reconnection and degraded behaviour.

## File security and storage limits

Explain validation, authorisation, quota enforcement and the production object-storage approach.

## Security considerations

Describe relevant threats considered and the protections implemented.

## Production deployment and operations

Explain how you would deploy, scale, monitor, back up and recover the application.

## Assumptions and trade-offs

List significant assumptions and explain important trade-offs.

## Known limitations or incomplete requirements

List anything incomplete or not working. If none, state that explicitly.
