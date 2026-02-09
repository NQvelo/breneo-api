# Email sending – what you need

Emails are sent via **Resend HTTP API** (not SMTP) to avoid timeouts on Railway and other cloud hosts.

## Checklist for successful sending

1. **In `.env` (project root):**

   ```env
   RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx
   DEFAULT_FROM_EMAIL=onboarding@resend.dev
   BRENEO_LOGO_URL=https://your-domain.com/path/to/logo.png
   ```

   - Get the API key from [Resend → API Keys](https://resend.com/api-keys).
   - Use `onboarding@resend.dev` for testing (no domain verification needed). For production, use an address from a [verified domain](https://resend.com/domains) (e.g. `noreply@yourdomain.com`).
   - Set `BRENEO_LOGO_URL` to a publicly accessible URL of your logo image (PNG, JPG, or SVG). The logo will appear at the top of all email templates. If not set, emails will be sent without a logo.

2. **Restart the server** after changing `.env` so the new values are loaded.

3. **Resend dashboard:**
   - **Domain:** For real inbox delivery, either use `onboarding@resend.dev` (testing) or add and verify your domain under [Resend → Domains](https://resend.com/domains).
   - **API key:** Ensure the key is active and not revoked.

4. **From address and Resend Logs:** If you use a custom address like `noreply@breneo.app`, that **domain must be verified** in [Resend → Domains](https://resend.com/domains). Until it is, Resend may reject the message (and it might not appear in Logs). Use `onboarding@resend.dev` to test without domain verification.

5. **Local:** `.env` is loaded from the project root; no extra config is required for local sending.

---

# Why email might not be sending

## 1. **RESEND_API_KEY not set or not loaded**

- Email is sent only when **`RESEND_API_KEY`** is set in your **`.env`** (project root).
- If it’s missing or empty, Django uses the **console backend**: messages are printed in the terminal where you run `runserver`, and nothing is sent to real inboxes.
- **Check:** In `.env` you should have:
  ```env
  RESEND_API_KEY=re_xxxxxxxxxxxx
  ```
- **Check:** Restart the server after changing `.env`. Settings are loaded at startup.

## 2. **`.env` not in the right place**

- `.env` must be in the **project root** (same folder as `manage.py`).
- `settings.py` loads it with `load_dotenv(BASE_DIR / ".env")` so it’s found regardless of where you run the app from.

## 3. **Resend limits and verification**

- **Free tier:** Resend may only allow sending to the account email or to verified addresses.
- **From address:** `DEFAULT_FROM_EMAIL=onboarding@resend.dev` works for testing. For your own domain you must verify it in the Resend dashboard.
- **Invalid or revoked API key:** If the key is wrong or revoked, SMTP will fail (you may see an error in the API response or in the runserver console).

## 4. **See what’s actually happening**

- With **console backend** (no `RESEND_API_KEY`): look at the terminal where `runserver` is running; the email content is printed there.
- With **Resend**: if `send_mail` raises (e.g. SMTP error), the API will return 500 and the traceback will appear in the runserver terminal. Use the debug middleware / `DEBUG=1` to see the full error.

## 5. **Quick checklist**

- [ ] `.env` is in the project root (next to `manage.py`).
- [ ] `RESEND_API_KEY=re_...` is set in `.env` (no quotes, no spaces around `=`).
- [ ] Server was restarted after editing `.env`.
- [ ] Resend dashboard: API key is valid, domain/from address is allowed for your plan.
