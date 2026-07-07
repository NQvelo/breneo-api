# Frontend integration — Breneo Notifications API (Django)

Use this document when wiring the React SPA to notification features. Copy it into the frontend repo or paste it as a Cursor agent prompt.

**Storage:** All in-app notifications live in **Django (PostgreSQL)**. Do **not** use Supabase tables `notifications` or `job_notifications`.

**Not on Django (use employer BFF instead):**

- `GET /api/employer/access-state/` — **does not exist** on this API
- Employer join-request inbox / approve / reject — still on **Node employer BFF** (Supabase v1)

---

## Base URL and authentication

| Item | Value |
|------|--------|
| Base URL | Same host as other Breneo API calls (e.g. `https://<django-host>/` or `http://127.0.0.1:8000/`) |
| User endpoints auth | `Authorization: Bearer <access_token>` (same JWT as `/api/me/profile/`) |
| Content-Type | `application/json` for POST/PATCH bodies |
| Trailing slashes | **Required** on every path below |

**User id:** Django `User.id` (integer). API returns `recipient_id` as a **string** (e.g. `"42"`). Coerce in the client if needed.

---

## Notification object (response shape)

All notification endpoints return objects with these fields (**snake_case**):

| Field | Type | Notes |
|-------|------|--------|
| `id` | string | Primary key as string, e.g. `"1"` |
| `title` | string | |
| `message` | string | Human-readable body |
| `type` | string | `"info"` \| `"success"` \| `"warning"` \| `"error"` |
| `recipient_id` | string \| null | Owner user id as string; `null` = **broadcast** (visible to every authenticated user on list) |
| `is_read` | boolean | |
| `kind` | string | May be `""`; use for filtering and UI routing |
| `metadata` | object | JSON payload; see conventions below |
| `created_at` | string | ISO 8601 datetime |
| `updated_at` | string | ISO 8601 datetime |

### `kind` and `metadata` conventions

| `kind` | Who receives | `metadata` should include |
|--------|----------------|---------------------------|
| `employer_join_request` | Company admin | `request_id`, `company_id` |
| `employer_join_approved` | Requesting employer | `request_id`, `company_id` |
| `job_match` | Job seeker (self) | `job_id` |

On create, if `metadata.kind` is set and top-level `kind` is empty, Django copies `metadata.kind` → `kind`.

**Employer join approve:** Use existing **join-request API on the BFF** (`GET /api/employer/join-requests/inbox`, `POST .../approve`, etc.). The notification row is only an **alert**; link via `metadata.request_id`.

**Optional legacy message prefix** (for parsing old text):

```text
employer_join_request:{request_uuid}|{name} wants to join {company}. Open Notifications to approve.
```

Prefer `kind` + `metadata.request_id` over parsing `message`.

---

## SPA endpoints (JWT required)

### 1. List notifications

```http
GET /api/me/notifications/
Authorization: Bearer <access_token>
```

**Optional filter:**

```http
GET /api/me/notifications/?kind=employer_join_request
```

**Returns:** Notifications where `recipient_id` = current user **or** `recipient_id` is `null` (broadcast). Newest first.

**Response `200`:**

```json
{
  "results": [
    {
      "id": "1",
      "title": "New Job Match! 🎯",
      "message": "Software Engineer at Acme matches your skills",
      "type": "info",
      "recipient_id": "42",
      "is_read": false,
      "kind": "job_match",
      "metadata": { "kind": "job_match", "job_id": "job-123" },
      "created_at": "2026-05-26T12:00:00.123456Z",
      "updated_at": "2026-05-26T12:00:00.123456Z"
    }
  ]
}
```

**Errors:** `401` — missing or invalid token.

**Frontend:** Always read `response.results` (not a bare array).

---

### 2. Create notification (current user only)

```http
POST /api/me/notifications/
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request body:**

```json
{
  "title": "New Job Match! 🎯",
  "message": "Software Engineer at Acme matches your skills",
  "type": "info",
  "metadata": {
    "kind": "job_match",
    "job_id": "job-123"
  }
}
```

| Field | Required | Notes |
|-------|----------|--------|
| `title` | yes | max 255 chars |
| `message` | yes | |
| `type` | yes | `info` \| `success` \| `warning` \| `error` |
| `metadata` | no | defaults to `{}` |
| `kind` | no | optional; copied from `metadata.kind` if omitted |

- Any `recipient_id` in the body is **ignored** — always created for the authenticated user.
- **Response `201`:** single notification object (same shape as above).
- **Errors:** `400` validation, `401` unauthorized.

**Use case:** SPA job-match checker (~every 30 minutes).

---

### 3. Mark one notification as read

```http
PATCH /api/me/notifications/{id}/read/
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Path:** `{id}` = integer PK (parse string `"1"` → `1` for the URL).

**Body:** optional `{}` or empty.

**Response `200`:** updated notification object.

| Status | When |
|--------|------|
| `200` | Success |
| `403` | Not owner, or **broadcast** (`recipient_id` null) |
| `404` | Unknown id |
| `401` | Unauthorized |

**Frontend:** Do not offer “mark read” on broadcast items, or handle `403` gracefully.

---

### 4. Mark all personal notifications as read

```http
PATCH /api/me/notifications/read-all/
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:** optional `{}`.

**Response `200`:**

```json
{
  "updated": 5
}
```

Only rows with `recipient_id` = current user and `is_read` = false. **Does not** update broadcasts.

---

### 5. List job IDs already notified (dedup)

```http
GET /api/me/job-notifications/
Authorization: Bearer <access_token>
```

**Response `200`:**

```json
{
  "job_ids": ["job-1", "job-2", "job-123"]
}
```

**Use case:** Before creating a job-match notification, check if `job_id` is already in `job_ids`.

---

### 6. Record job as notified (dedup upsert)

```http
POST /api/me/job-notifications/
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request body:**

```json
{
  "job_id": "job-123"
}
```

| Status | Meaning |
|--------|---------|
| `201` | First time for this user + job |
| `200` | Already recorded (idempotent) |

**Response body:**

```json
{
  "job_id": "job-123"
}
```

---

## Endpoint summary (SPA)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/me/notifications/` | List personal + broadcast |
| `GET` | `/api/me/notifications/?kind=<kind>` | Filter by `kind` |
| `POST` | `/api/me/notifications/` | Create notification for self |
| `PATCH` | `/api/me/notifications/{id}/read/` | Mark one read |
| `PATCH` | `/api/me/notifications/read-all/` | Mark all personal unread read |
| `GET` | `/api/me/job-notifications/` | List notified job IDs |
| `POST` | `/api/me/job-notifications/` | Record job notified |

---

## Internal endpoint (BFF only — do not call from browser)

```http
POST /api/internal/notifications/
X-Internal-Key: <NOTIFICATIONS_INTERNAL_KEY>
Content-Type: application/json
```

No JWT. Returns `401` if key is missing or wrong.

**Request body:**

```json
{
  "recipient_id": "42",
  "title": "Company join request",
  "message": "employer_join_request:550e8400-e29b-41d4-a716-446655440000|Jane Doe wants to join Acme Corp. Open Notifications to approve.",
  "type": "info",
  "metadata": {
    "kind": "employer_join_request",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "company_id": 123
  }
}
```

**Response `201`:** created notification object.

**BFF use cases:**

1. **Join request created** → notify each company admin (`recipient_id` = admin’s Django user id).
2. **Join request approved** → notify requester with `kind: "employer_join_approved"`.

The SPA only **lists** these via `GET /api/me/notifications/?kind=employer_join_request`.

---

## Related Django employer routes (not notifications)

These exist on Django but are **not** the notifications API:

| Method | Endpoint |
|--------|----------|
| `POST` | `/api/employer/login/` |
| `POST` | `/api/employer/register/` |
| `POST` | `/api/employer/verify-email/` |
| `GET` / `PUT` / etc. | `/api/employer/profile/` |
| `POST` | `/api/employer/change-password/` |

**Missing on Django:** `/api/employer/access-state/` — implement on BFF or add to Django separately.

---

## Recommended SPA flows

### Notifications page / bell

1. `GET /api/me/notifications/`
2. Show `results`; unread badge = items with `is_read === false` (treat broadcasts separately if needed).
3. Click personal item → `PATCH /api/me/notifications/{id}/read/`
4. “Mark all read” → `PATCH /api/me/notifications/read-all/`

### Employer join inbox (admin)

1. `GET /api/me/notifications/?kind=employer_join_request`
2. Deep link using `metadata.request_id` and `metadata.company_id`
3. Approve/reject via **BFF join-request endpoints**, not notification PATCH

### Job match checker (periodic)

For each new match with `job_id`:

1. `GET /api/me/job-notifications/` — skip if `job_id` ∈ `job_ids`
2. `POST /api/me/notifications/` with `metadata: { kind: "job_match", job_id }`
3. `POST /api/me/job-notifications/` with `{ job_id }`

---

## TypeScript types

```ts
export type NotificationType = "info" | "success" | "warning" | "error";

export type NotificationKind =
  | "employer_join_request"
  | "employer_join_approved"
  | "job_match"
  | "";

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: NotificationType;
  recipient_id: string | null;
  is_read: boolean;
  kind: NotificationKind | string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface NotificationListResponse {
  results: Notification[];
}

export interface JobNotificationsResponse {
  job_ids: string[];
}

export interface ReadAllResponse {
  updated: number;
}
```

---

## Example API client (`fetch`)

```ts
const API = import.meta.env.VITE_API_URL; // e.g. https://your-django-host.com

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function fetchNotifications(
  token: string,
  kind?: string
): Promise<Notification[]> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  const res = await fetch(`${API}/api/me/notifications/${query}`, {
    headers: headers(token),
  });
  if (!res.ok) throw new Error(`GET /api/me/notifications/ → ${res.status}`);
  const data: NotificationListResponse = await res.json();
  return data.results;
}

export async function createNotification(
  token: string,
  body: {
    title: string;
    message: string;
    type: NotificationType;
    metadata?: Record<string, unknown>;
    kind?: string;
  }
): Promise<Notification> {
  const res = await fetch(`${API}/api/me/notifications/`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST /api/me/notifications/ → ${res.status}`);
  return res.json();
}

export async function markNotificationRead(
  token: string,
  id: string
): Promise<Notification> {
  const res = await fetch(`${API}/api/me/notifications/${id}/read/`, {
    method: "PATCH",
    headers: headers(token),
    body: "{}",
  });
  if (!res.ok) throw new Error(`PATCH /api/me/notifications/${id}/read/ → ${res.status}`);
  return res.json();
}

export async function markAllNotificationsRead(token: string): Promise<number> {
  const res = await fetch(`${API}/api/me/notifications/read-all/`, {
    method: "PATCH",
    headers: headers(token),
    body: "{}",
  });
  if (!res.ok) throw new Error(`PATCH /api/me/notifications/read-all/ → ${res.status}`);
  const data: ReadAllResponse = await res.json();
  return data.updated;
}

export async function getNotifiedJobIds(token: string): Promise<string[]> {
  const res = await fetch(`${API}/api/me/job-notifications/`, {
    headers: headers(token),
  });
  if (!res.ok) throw new Error(`GET /api/me/job-notifications/ → ${res.status}`);
  const data: JobNotificationsResponse = await res.json();
  return data.job_ids;
}

export async function recordJobNotified(
  token: string,
  jobId: string
): Promise<void> {
  const res = await fetch(`${API}/api/me/job-notifications/`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ job_id: jobId }),
  });
  if (res.status !== 200 && res.status !== 201) {
    throw new Error(`POST /api/me/job-notifications/ → ${res.status}`);
  }
}
```

---

## Migration checklist (frontend)

- [ ] Remove Supabase `notifications` and `job_notifications` reads/writes
- [ ] List/create/read: `/api/me/notifications/` with JWT
- [ ] Job dedup: `/api/me/job-notifications/`
- [ ] Parse list from `{ results: [...] }`
- [ ] Treat `id` and `recipient_id` as strings
- [ ] Filter employer joins: `GET /api/me/notifications/?kind=employer_join_request`
- [ ] Approve/reject: keep BFF join-request API; link via `metadata.request_id`
- [ ] Do **not** call `POST /api/internal/notifications/` from the browser
- [ ] Do **not** expect `GET /api/employer/access-state/` on Django (use BFF)

---

## Environment (backend / BFF)

Django and the employer BFF must share:

```bash
NOTIFICATIONS_INTERNAL_KEY=<same-secret>
```

Django validates `X-Internal-Key` on `POST /api/internal/notifications/`.

---

## Cursor agent prompt (short)

> Integrate Breneo notifications against Django only (no Supabase). Use JWT on all `/api/me/notifications/` and `/api/me/job-notifications/` routes; trailing slashes required. List via `GET /api/me/notifications/` → `results[]`. Create job matches with `POST /api/me/notifications/`; dedup with `GET`/`POST /api/me/job-notifications/`. Mark read: `PATCH /api/me/notifications/{id}/read/` (403 for broadcasts). Mark all: `PATCH /api/me/notifications/read-all/`. Employer join alerts: filter `?kind=employer_join_request`; approve via BFF join-request API using `metadata.request_id`. Never call `/api/internal/notifications/` from the SPA. Full spec: `docs/FRONTEND_NOTIFICATIONS_API.md` in breneo-api repo.
