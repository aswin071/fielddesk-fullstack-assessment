# Authentication Module

## Purpose

Provides secure sessions for Owner, Dispatcher and Technician accounts.

## API

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

## Flow

Login validates normalized email/password, verifies both User and OrganisationUser are active, issues a short-lived access token and sets a rotating refresh token in a secure HttpOnly cookie. The response returns user display data, role and organisation display data, not authority fields accepted on later requests.

Logout blacklists the presented refresh token and clears its cookie. Existing access tokens expire naturally after a short lifetime.

Implemented endpoints use the `fielddesk_refresh` HttpOnly, SameSite=Strict cookie scoped to `/api/v1/auth/`. The cookie is Secure outside local development. Access tokens are returned in the response body and never persisted by the backend.

## Security

- Django password hashing and password validation.
- Generic invalid-credentials response.
- Throttle by normalized identity and source address.
- Secure, HttpOnly, SameSite cookie configuration by environment.
- No secrets, tokens or passwords in logs.
- JWT authentication is deny-by-default across DRF.

## Tests

- Successful and failed login, inactive account, throttling, refresh rotation and logout revocation.
- Tokens cannot be used to select another organisation or elevate role.
