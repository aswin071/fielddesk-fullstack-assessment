# Worker

The independently runnable Celery worker imports FieldDesk's Django domain code from `backend/`. Notification tasks and provider behavior are implemented in the backend `notifications` app; this directory owns worker container/runtime concerns only.

