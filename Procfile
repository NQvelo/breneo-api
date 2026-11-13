web: python manage.py migrate --noinput && python manage.py fetch_profession_data --skip-groq && python manage.py seed_atoms && python manage.py collectstatic --noinput && gunicorn mysite.wsgi --timeout 120 --log-file -
worker: python manage.py run_job_match_scheduler
