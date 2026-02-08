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

**If you get 500 on the new tables (profile, educations, work-experiences, skills):** Those endpoints and the Admin pages for Education/Work Experience depend on migration `0066_profile_education_workexperience_userskill`. Ensure migrations have run (e.g. redeploy so the Procfile runs `migrate`, or run migrate via Railway CLI/Shell below). If migration fails with a **unique constraint** error on `app_userskill`, the migration will first remove duplicate (user, skill) rows, then add the constraint; if you see a different error, check the traceback in logs.

### Run migrations with Railway CLI

To run migrations against your **Railway database** from your machine (using Railway’s `DATABASE_URL`):

1. **Install Railway CLI** (if needed): [https://docs.railway.app/develop/cli](https://docs.railway.app/develop/cli)
2. **Install Django and dependencies locally** (required — `railway run` runs the command on your machine with Railway’s env vars only):
   ```bash
   cd /path/to/breneo-api
   python3 -m venv .venv
   source .venv/bin/activate    # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Link the project** (once per machine):
   ```bash
   railway link
   ```
   Choose your project and the **app** service (the one that uses the database).
4. **Run migrate:**
   ```bash
   railway run python manage.py migrate app
   ```
   Or migrate all apps: `railway run python manage.py migrate`

**Or use Railway’s in-browser Shell:** In the [Railway dashboard](https://railway.app) → your **app service** → **Shell** tab → run:
```bash
python manage.py migrate app
```
The Shell already uses Railway’s environment (including `DATABASE_URL`).

### 3. Create an admin user

**Where to run it:** In Railway’s dashboard (browser), not in your project files.

**Steps:**

1. Go to [railway.app](https://railway.app) → your **project** → click your **app service** (the web app).
2. Open the **"Shell"** or **"Command"** / **"Run"** tab (one-off command or shell).
3. In the shell/command box, type exactly:
   ```bash
   python manage.py createsuperuser
   ```
   and run it.
4. When prompted, enter **username**, **email**, and **password** (no characters will show when you type the password).
5. Then open `https://your-app.up.railway.app/admin/` in a browser and log in with that username and password.

**If your project has no Shell tab:** Install [Railway CLI](https://docs.railway.app/develop/cli), run `railway link` in your project folder, then in the same folder run `railway run python manage.py createsuperuser` in your **local terminal** (not in a file).

**Change superuser (e.g. password):** In the same Railway **Shell** (or `railway run ...` in terminal), run:
```bash
python manage.py changepassword <username>
```
Replace `<username>` with your admin username. You’ll be prompted for a new password twice. To create a different superuser instead, run `python manage.py createsuperuser` again (you can have more than one).

**If you see `no such table: auth_user`:** The command is using a database that has no tables. Use one of these:
- **Changing password on Railway:** Run the command in Railway’s **Shell** (or with `railway run` from your project folder so Railway’s `DATABASE_URL` is used). Do not run it in a local terminal without `railway run`, or Django will use your local SQLite and that DB may have no tables.
- **Using local DB:** From the project folder run `python manage.py migrate`, then run `changepassword` or `createsuperuser`.

**Delete current superuser and add a new one:** In Railway **Shell** (or `railway run ...` from the project folder), run:

1. Open Django shell and delete the user (replace `OLD_USERNAME` with the existing superuser’s username):
   ```bash
   python manage.py shell
   ```
   Then in the shell:
   ```python
   from django.contrib.auth import get_user_model
   User = get_user_model()
   User.objects.filter(username='OLD_USERNAME').delete()
   exit()
   ```
2. Create the new superuser:
   ```bash
   python manage.py createsuperuser
   ```
   Enter the new username, email, and password when prompted.

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

### 6. "could not translate host name postgres.railway.internal"

The app is using Railway’s **private** DB URL, which isn’t resolving in your setup. Use the **public** URL instead:

1. Open your **Postgres** service on Railway → **Variables** (or **Connect**).
2. Find **`DATABASE_URL`** (the public one; host usually looks like `*.proxy.rlwy.net` or `*.railway.app`). If you see **`DATABASE_PRIVATE_URL`** (host `postgres.railway.internal`), do **not** use that for the app.
3. In your **app** service → **Variables**, set **`DATABASE_URL`** to that **public** value:
   - Either use **Add variable reference** and pick the Postgres service’s **`DATABASE_URL`** (not `DATABASE_PRIVATE_URL`), or
   - Copy the public `DATABASE_URL` from the Postgres service and paste it as a raw variable in the app.
4. **Redeploy** the app so the new variable is used.

After that, the app should connect.

### 7. Import local database into Railway

Use Django's **dumpdata** (local) and **loaddata** (Railway) so Railway Postgres gets the same data as your local DB. Railway tables must already exist (migrations applied).

**Step 1 – Export from local (SQLite)**

From your project folder, with your **local** env (no `DATABASE_URL` or local SQLite):

```bash
cd /path/to/breneo-api
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission \
  -o data.json
```

- `--natural-foreign` / `--natural-primary` help when loading into another DB.
- Excluding `contenttypes` and `auth.Permission` avoids duplicate-key errors on Railway (those rows already exist from `migrate`).
- To export only specific apps: e.g. `dumpdata app auth -o data.json` (and keep the `-e` exclusions if you use them).

**Step 2 – Load into Railway**

**Option A – Railway Shell:** The fixture file must exist on the container. Commit `data.json` to the repo root and deploy, then in Railway → app service → **Shell** (or SSH) run:
```bash
python manage.py loaddata /app/data.json -v 2
```
Use the full path `/app/data.json` so Django finds the file. You can add `data.json` to `.gitignore` and remove it from the repo in a later commit if you don't want it in version control long term.

**Option B – Railway CLI** (no need to commit the file): From your project folder (where `data.json` is), run:
```bash
railway run python manage.py loaddata "$(pwd)/data.json" -v 2
```
Use the full path (`$(pwd)/data.json` or `/absolute/path/to/data.json`) so the file is found. This uses Railway's `DATABASE_URL` and reads the file from your machine. Use `-v 2` to see progress. If you get "No such file or directory", use Option A (commit and load in Railway Shell) instead.

**Large fixtures (e.g. 4–5 MB):** loaddata can take several minutes over the network. Let it run to completion; don't cancel with Ctrl+C. If you already partially loaded and get duplicate key errors, either flush the Railway DB and run loaddata again, or run with `--ignorenonexistent`.

If you get "Duplicate key" or content-type errors, run loaddata with `--ignorenonexistent`, or adjust the `dumpdata` exclusions. Postgres logs showing “invalid length of startup packet” are often from health checks or probes hitting the DB port; they’re usually harmless if the app connects successfully.
