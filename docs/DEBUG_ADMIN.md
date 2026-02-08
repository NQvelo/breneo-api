# Debugging admin 500 errors

## 1. See the error in the terminal (runserver)

When you run `python manage.py runserver`, **any 500 error** will now print the **full traceback** in that terminal. Reproduce the error (e.g. save Academy or UserProfile in admin), then look at the terminal where runserver is running.

## 2. Show the error on the form (UserProfile only)

For **UserProfile** admin, save errors are caught and shown as a red message at the top of the change form instead of a 500 page. The same error is also logged to the console.

## 3. Use Django debug page (full traceback in browser)

To see the yellow Django debug page with traceback in the browser:

```bash
export DEBUG=1
python manage.py runserver
```

Or set `DEBUG=1` or `DJANGO_DEBUG=1` in your `.env`. Then reload the failing admin page; you’ll get the full traceback in the browser.

## 4. Turn off debug logging later

- Remove or comment out `mysite.debug_middleware.LogExceptionMiddleware` in `MIDDLEWARE` in `mysite/settings.py` if you don’t want every 500 logged to the console.
- Set `DEBUG=0` (or unset `DEBUG` / `DJANGO_DEBUG`) when you’re done debugging.
