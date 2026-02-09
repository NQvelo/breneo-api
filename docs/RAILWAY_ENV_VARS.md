# Railway Environment Variables Setup

## Required Environment Variables for Email Functionality

Based on your `.env` file, add these variables to Railway:

### How to Add Variables in Railway:

1. Go to [Railway Dashboard](https://railway.app)
2. Select your **app service** (not the database)
3. Click on the **Variables** tab
4. Click **+ New Variable** or **Add variable**
5. Add each variable one by one

---

## Critical Variables (Must Have)

### 1. Email Configuration (NEW - Required for emails to work)
```
RESEND_API_KEY=re_CnSUFLGi_JyVuDABmuaT8gYnRaqXySTR5
DEFAULT_FROM_EMAIL=noreply@breneo.app
BRENEO_LOGO_URL=https://dashboard.breneo.app/lovable-uploads/Breneo-logo.png
```

**Important Notes:**
- `RESEND_API_KEY` - Required for emails to send (without this, emails only print to logs)
- `DEFAULT_FROM_EMAIL` - Must be from a verified domain in Resend dashboard
- `BRENEO_LOGO_URL` - Optional but recommended (shows logo in emails)

### 2. Django Core
```
SECRET_KEY=your-django-secret-key-here
DEBUG=0
DJANGO_DEBUG=0
```

### 3. Database (usually auto-set by Railway)
```
DATABASE_URL=postgresql://... (usually set automatically when you link PostgreSQL)
```

---

## Optional but Recommended

### Cloudinary (for image uploads)
```
CLOUDINARY_CLOUD_NAME=Breneo-cloud
CLOUDINARY_API_KEY=445566653793823
CLOUDINARY_API_SECRET=M65OgIqJ7fFSU6rfXGlAEnyR02U
```

### AI/API Keys (if used)
```
GSK_API_KEY=your-key-here
GROQ_API_KEY=your-key-here
```

### BOG Payment (if used)
```
BOG_CLIENT_ID=your-client-id
BOG_CLIENT_SECRET=your-secret
BOG_TOKEN_URL=your-token-url
BOG_ORDER_URL=your-order-url
BOG_SUBSCRIBE_URL=your-subscribe-url
BOG_CALLBACK_SECRET_PUBLIC_KEY=your-public-key
```

### Supabase (if used)
```
SUPABASE_JWT_SECRET=your-secret
```

---

## Quick Checklist

After adding variables:
- [ ] `RESEND_API_KEY` is set (emails will send)
- [ ] `DEFAULT_FROM_EMAIL` is set (from verified domain)
- [ ] `BRENEO_LOGO_URL` is set (logo appears in emails)
- [ ] `SECRET_KEY` is set (Django security)
- [ ] `DATABASE_URL` is set (usually automatic)
- [ ] Cloudinary variables are set (if using image uploads)

---

## Verify Email Setup

After deploying with the email variables:
1. Check Railway logs - you should see: `[Email] Using Resend SMTP – emails will appear in resend.com → Logs`
2. Test by registering a user or requesting password reset
3. Check Resend dashboard → Logs to see sent emails

---

## Domain Verification in Resend

For `DEFAULT_FROM_EMAIL=noreply@breneo.app` to work:
1. Go to [Resend Dashboard](https://resend.com/domains)
2. Add and verify your domain `breneo.app`
3. Add DNS records as instructed by Resend
4. Wait for verification (usually a few minutes)

Until verified, you can use `onboarding@resend.dev` for testing (no verification needed).
