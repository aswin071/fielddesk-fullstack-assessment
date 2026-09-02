# Requirements Traceability

This matrix ensures every section of the assessment brief has an owning specification and planned automated evidence.

| Requirement | Owning specification | Primary evidence |
|---|---|---|
| Authentication, roles, isolation | authentication; users-and-roles; security | auth, role and two-organisation API tests |
| Work-order management/dashboard | work-orders | CRUD, list behavior and count tests |
| Concurrent scheduling | scheduling | real PostgreSQL concurrency test |
| Progress-event API | progress-events | validation, idempotency and rollback tests |
| Attachments and quotas | attachments | upload/access/quota tests |
| Background processing | notifications | retry, classification and deduplication tests |
| Real-time updates | realtime | authenticated two-organisation stream tests |
| Audit history | audit-history | immutable action/rollback tests |
| Frontend | frontend | Dispatcher workflow and UI state tests |
| CSV reporting | reporting | isolation, injection and streaming tests |
| API/operational quality | API standards; operations-and-testing | contract, health, logging and configuration checks |
| Automated testing | operations-and-testing | complete test suite |
| Local operation/documentation | architecture; operations-and-testing | Docker Compose smoke test and README |

## Definition of done for each module

1. Specification and acceptance criteria are current.
2. Models and migrations include required constraints/indexes.
3. API behavior follows shared response/error standards.
4. Backend authorization and organisation isolation are tested.
5. Transaction and side-effect boundaries are tested where applicable.
6. Module documentation and operational commands are accurate.
7. Known gaps are recorded in `candidate-submission/TECHNICAL_NOTES.md`.
