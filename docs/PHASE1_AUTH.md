# Phase 1 — Register, approve, authenticate

Prime theme: **pharmacists self-register; an administrator must approve before clinical access.**

## Seed accounts (dev)

| Username | Password | Role |
|----------|----------|------|
| `admin` | `ChangeMeAdmin!234` | administrator |
| `pharmacist` | `ChangeMePharm!234` | pharmacist (already active) |
| `reviewer` | `ChangeMeReview!234` | reviewer |

UI: http://127.0.0.1:8080 · API: http://127.0.0.1:8000

## Demo checklist (register → approve gate)

1. **Register** — open `/register`, complete Account → PIS → Consent → Review with a new username and a strong password (12+ chars; at least 3 of lower/upper/digit/symbol).
2. **Pending status** — after submit you are signed in as `pending` and land on Registration status. Clinical features stay locked.
3. **Blocked Analyzer** — try `/analyzer` (redirects to registration status). API calls to prescriptions/OCR/catalog return **403**.
4. **Admin queue** — sign in as `admin`, open **Registration requests**, filter **Pending**, **Approve** the new pharmacist (confirm dialog).
5. **Refresh** — as the pending pharmacist, click **Refresh status** (or re-login). Status becomes `active`; home and Analyzer unlock.
6. **Optional reject** — register another user; admin **Reject** with an optional reason; that account cannot sign in for clinical use (`inactive`).
7. **Quick bypass** — seed `pharmacist` is already active for Analyzer demos without registration.

## Security features in Phase 1

- Argon2id password hashing
- JWT access tokens + refresh token rotation (reuse detection revokes family)
- Login rate limiting and lockout after repeated failures
- Generic login error messages
- Pharmacist registration ID stored encrypted (Fernet)
- PIS + 18 mandatory consent statements before registration completes
- RBAC: `administrator` / `pharmacist` / `reviewer`; clinical APIs require **active** pharmacist
- Forced password change for seed accounts (`must_change_password`)
- Self-service forgot password (`/forgot-password`) issues a one-time temporary password in the UI (no email in this prototype), then forces change on next login

## Out of scope (later)

Email-based reset delivery, admin user CRUD for reviewers, session revoke UI.
