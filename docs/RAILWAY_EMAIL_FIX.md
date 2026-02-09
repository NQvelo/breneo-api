# Fix Email Configuration in Railway

## Problem
Emails are being sent with `From: noreply@localhost` instead of your configured email address.

## Solution: Add Missing Environment Variables

### Step 1: Go to Railway Dashboard
1. Open [Railway Dashboard](https://railway.app)
2. Select your **app service** (the web app, not the database)

### Step 2: Add Email Variables
Go to **Variables** tab and add these three variables:

```
RESEND_API_KEY=re_CnSUFLGi_JyVuDABmuaT8gYnRaqXySTR5
DEFAULT_FROM_EMAIL=noreply@breneo.app
BRENEO_LOGO_URL=https://dashboard.breneo.app/lovable-uploads/Breneo-logo.png
```

**Important:**
- Copy the exact values from your `.env` file
- No quotes around the values
- No spaces around the `=` sign

### Step 3: Redeploy
After adding variables:
1. Go to **Deployments** tab
2. Click **⋮** (three dots) on the latest deployment
3. Click **Redeploy**

Or simply push a new commit to trigger a redeploy.

### Step 4: Verify
After redeploy, check the logs. You should see:
```
[Email] Using Resend SMTP – emails will appear in resend.com → Logs
```

If you see:
```
[Email] RESEND_API_KEY not set – emails only in terminal, not in Resend
```

Then the variable wasn't set correctly. Double-check:
- Variable name is exactly `RESEND_API_KEY` (case-sensitive)
- No extra spaces or quotes
- Value starts with `re_`

---

## Other Errors in Logs

### 1. JWT Refresh Token Error
```
User matching query does not exist
```
**Cause:** Trying to refresh a token for a user that was deleted or doesn't exist.
**Solution:** This is normal if users are deleted. The frontend should handle expired/invalid tokens.

### 2. 404 for `/api/academy/login/`
**Check:** Make sure the URL doesn't have a trailing slash issue. The endpoint exists at `/api/academy/login/`

### 3. 401 Unauthorized
**Cause:** Invalid or expired JWT token.
**Solution:** User needs to log in again to get a new token.

---

## Quick Checklist

- [ ] `RESEND_API_KEY` added to Railway Variables
- [ ] `DEFAULT_FROM_EMAIL` added to Railway Variables  
- [ ] `BRENEO_LOGO_URL` added to Railway Variables (optional)
- [ ] App redeployed after adding variables
- [ ] Logs show "Using Resend SMTP" message
- [ ] Test email sent successfully

---

## Domain Verification

If using `noreply@breneo.app`, make sure:
1. Domain `breneo.app` is verified in [Resend Dashboard](https://resend.com/domains)
2. DNS records are added correctly
3. Verification status shows "Verified"

Until verified, use `onboarding@resend.dev` for testing (no verification needed).
