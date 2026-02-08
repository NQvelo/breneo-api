# Why some datasets are empty & how to import old data

## Why are some tables empty?

Your database is empty for those tables because:

1. **Fresh database** – When we set up the project locally, we used a new SQLite database. Migrations only create the table structure; they do **not** insert any data.

2. **No seed data in the repo** – The project has no fixture files or scripts that load initial data for:
   - **DynamicTechQuestion** – tech assessment questions
   - **DynamicSoftSkillsQuestion** – soft skills questions
   - **CareerCategory**, **CareerQuestion**, **CareerOption** – career assessment
   - **Skill**, **Job**, **Course** – skills, jobs, courses

So these tables start empty until you add data via Django admin or import.

---

## How to import old data

### Option 1: Export from old Django database, then load here (recommended)

If your old data is in another Django project (e.g. production or another machine):

**1. On the OLD project** (where the data lives), export to a JSON fixture:

```bash
# Export all app models (questions, categories, skills, jobs, etc.)
python manage.py dumpdata app --indent 2 -o app_backup.json

# Or export only the tables you need, in dependency order:
python manage.py dumpdata app.CareerCategory app.CareerQuestion app.CareerOption app.DynamicTechQuestion app.DynamicSoftSkillsQuestion app.Skill app.Job app.Course --indent 2 -o questions_backup.json
```

**2. Copy the JSON file** into this project (e.g. into `app/fixtures/` or the project root).

**3. On THIS project** (breneo-api), load the fixture:

```bash
# Activate venv first, then:
.venv/bin/python manage.py loaddata app_backup.json

# Or with full path:
.venv/bin/python manage.py loaddata /path/to/questions_backup.json
```

Django will create the records in the correct order (respecting foreign keys). If you see errors about duplicate primary keys or missing references, export with natural keys or exclude conflicting models (e.g. `auth.User` if you don’t want to import users).

---

### Option 2: Use the `app/fixtures/` folder

Django automatically looks for fixtures in each app’s `fixtures/` directory:

1. Put your JSON fixture in `app/fixtures/` (e.g. `app/fixtures/initial_questions.json`).
2. Run:

   ```bash
   .venv/bin/python manage.py loaddata initial_questions
   ```

   (Use the filename **without** `.json`.)

---

### Option 3: Import from CSV or Excel

If your old data is in CSV/Excel (not from Django), you have two options:

- **Django admin** – Use the admin to add records manually, or install something like [django-import-export](https://django-import-export.readthedocs.io/) to import from CSV/Excel.
- **Custom management command** – Write a command that reads your CSV/Excel and creates `DynamicTechQuestion`, `CareerCategory`, etc. If you share the column names and sample row, we can sketch that command.

---

## Quick reference: tables that are often “empty”

| Table                           | Used for                        |
| ------------------------------- | ------------------------------- |
| `app_dynamictechquestion`       | Tech skill assessment questions |
| `app_dynamicsoftskillsquestion` | Soft skills questions           |
| `app_careercategory`            | Career assessment categories    |
| `app_careerquestion`            | Career questions                |
| `app_careeroption`              | Options per career question     |
| `app_skill`                     | Skill names                     |
| `app_job`                       | Job listings                    |
| `app_course`                    | Courses                         |

After importing, you can confirm in Django admin:  
http://127.0.0.1:8000/admin/

---

## Downloading from Render.com PostgreSQL

Use the **External Database URL** from Render (Dashboard → your PostgreSQL service → Connect). The internal URL hostname does not resolve from your computer.

**1. Export data (run in your terminal):**

```bash
cd /Users/macbookpro/Downloads/breneo-api
source .venv/bin/activate
export DATABASE_URL="postgresql://USER:PASSWORD@HOST.oregon-postgres.render.com/DATABASE?sslmode=require"
python manage.py dumpdata app --exclude app.Course --indent 2 -o app_backup_from_render.json
```

- Replace `USER`, `PASSWORD`, `HOST`, `DATABASE` with your Render **External** URL values.
- `--exclude app.Course` is needed if Render’s schema is older (missing `academy_id` on `app_course`). If you get “no such column: app_course.academy_id”, keep the exclude. If dump works without it, you can omit it.
- If you see a “cursor does not exist” error, run the same command directly in your Mac’s Terminal (outside Cursor); it often works there.

**2. Load into your local database:**

```bash
unset DATABASE_URL
python manage.py loaddata app_backup_from_render.json
```

**3. (Optional) Sync schema on Render** so it matches your code and future full dumps work: in a terminal with `DATABASE_URL` set to Render’s URL, run `python manage.py migrate`. Only do this if you have permission to change the production DB.

---

## If full dump (auth + app) is too slow or seems stuck

Dumping `auth.User` and `app` together can take a long time over the network (many minutes of dots). Use **two dumps** instead:

**Step 1 – Dump only users (fast, usually &lt; 10 seconds):**

```bash
export DATABASE_URL="postgresql://render1212:qzJjltHcJRbGw9I9lX1DqsvHY25vOxVV@dpg-d4gcifhr0fns738bjv70-a.oregon-postgres.render.com/breneo_6pnu_fty7"
python manage.py dumpdata auth.User --indent 2 -o auth_users_only.json
```

**Step 2 – Dump only app (same as before, can be slow):**

```bash
python manage.py dumpdata app --indent 2 -o app_backup_from_render.json
```

**Step 3 – Load locally (users first, then app):**

You must load into your **local** DB (SQLite), not Render. Run from the project root:

```bash
cd /Users/macbookpro/Downloads/breneo-api
source .venv/bin/activate
unset DATABASE_URL
python manage.py loaddata auth_users_only.json
python manage.py loaddata app_backup_from_render.json
```

- Use the **full path** to the file if needed: `python manage.py loaddata /Users/macbookpro/Downloads/breneo-api/auth_users_only.json`
- If you get **duplicate key** or **IntegrityError**: your local DB already has users (e.g. pk=1). Either **flush first** (this deletes all data, including your superuser), then load:

  ```bash
  unset DATABASE_URL
  python manage.py flush --no-input
  python manage.py loaddata auth_users_only.json
  python manage.py loaddata app_backup_from_render.json
  python manage.py createsuperuser --username breneo-api --email breneoapp@gmail.com --noinput
  ```

  (Set `DJANGO_SUPERUSER_PASSWORD` if you want non-interactive superuser.)

- If users “don’t load”: confirm `DATABASE_URL` is unset (`echo $DATABASE_URL` should be empty), so loaddata writes to local SQLite, not Render.

If you already have `app_backup_from_render.json`, you only need to run Step 1 once to get `auth_users_only.json`, then run the two loaddata commands above.

**Note:** The full `app_backup_from_render.json` already includes **UserProfile** and **Academy** (and all other app models). Loading it after `auth_users_only.json` will load profiles and academies too. No extra dump needed for those tables.

---

## Dump only UserProfile and Academy (optional)

If you want a **small fixture** with just user profiles and academies (e.g. to refresh only those without re-dumping the whole app):

**On Render (with DATABASE_URL set):**

```bash
python manage.py dumpdata app.UserProfile app.Academy --indent 2 -o profiles_and_academies.json
```

**Load locally (after auth users are already loaded):**

```bash
unset DATABASE_URL
python manage.py loaddata profiles_and_academies.json
```

Load order if you use this file: `auth_users_only.json` → `profiles_and_academies.json` (then any other app fixtures if needed).
