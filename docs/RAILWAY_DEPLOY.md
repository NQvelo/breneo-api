# Deploying on Railway

## Fix 500 on admin login

The usual cause is **database not set up** or **migrations not run**.

### 1. Add a PostgreSQL database on Railway

**Where to add `DATABASE_URL` (brief):**

1. In [Railway](https://railway.app) open your **project** (the one with your breneo-api app).
2. Click **+ New** → **Database** → **PostgreSQL**. Wait until the database service is created.
3. **Link it to your app** so the app gets `DATABASE_URL`:
   - Click your **app service** (the web app, not the database).
   - Open the **Variables** tab.
   - Click **+ New Variable** or **Add variable**.
   - Either:
     - Choose **Add a variable reference** and pick **`DATABASE_URL`** from the PostgreSQL service (if Railway shows it), or
     - Open the **PostgreSQL service** → **Variables** or **Connect** tab, copy the **`DATABASE_URL`** value, then in your **app service** → **Variables** add a new variable: name **`DATABASE_URL`**, value = the pasted URL.
4. **Redeploy** the app (Deployments → ⋮ → Redeploy, or push a new commit) so the new variable is used.

### 2. Migrations and static files

The **Procfile** runs on each deploy:

- `python manage.py migrate --noinput` – create/update tables (required for admin login/sessions).
- `python manage.py collectstatic --noinput` – gather admin static files.
- Then starts **gunicorn**.

So after you add PostgreSQL and set `DATABASE_URL`, the next deploy will run migrations and admin login should stop returning 500.

### 3. Create an admin user

After the first successful deploy with PostgreSQL:

- In Railway: open your app service → **Settings** or **Shell**.
- Run:
  ```bash
  railway run python manage.py createsuperuser
  ```
  (or use **Railway Shell** and run `python manage.py createsuperuser` there.)

Then log in at `https://your-app.up.railway.app/admin/` with that user.

### 4. Environment variables on Railway

Set at least:

- **`DATABASE_URL`** – set automatically if you use Railway Postgres and link the DB to your app.
- **`SECRET_KEY`** – e.g. `openssl rand -base64 50`.
- **`ALLOWED_HOSTS`** – optional; your Railway host is already in code. Add more if you use a custom domain.
- **`CSRF_TRUSTED_ORIGINS`** – optional; add `https://your-custom-domain.com` if you use one.

Add any other vars your app needs (Cloudinary, Resend, etc.) in the Railway service **Variables** tab.

### 5. If you still get 500

- Open **Deployments** → select the latest deploy → **View Logs**.
- Look for the Python traceback; it will point to the failing line (e.g. missing table, connection error, missing env var).
