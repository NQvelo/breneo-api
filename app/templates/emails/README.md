# Email Templates

This directory contains HTML and plain text email templates for Resend email notifications.

## Available Templates

1. **verification_code.html/txt** - User registration verification code
2. **academy_verification_code.html/txt** - Academy registration verification code  
3. **password_reset.html/txt** - Password reset code (forgot password)
4. **password_changed.html/txt** - Password changed confirmation email

## Customizing Templates

### HTML Templates
Edit the `.html` files to customize the visual appearance:
- Modify colors, fonts, and styling in the `<style>` section
- Update the HTML structure and content
- Add your branding (logo, colors, etc.)

### Plain Text Templates
Edit the `.txt` files for email clients that don't support HTML.

### Template Variables

#### Verification Code Email
- `verification_code` - The 6-digit verification code
- `first_name` - User's first name (optional)

#### Academy Verification Code Email
- `verification_code` - The 6-digit verification code

#### Password Reset Email
- `reset_code` - The 6-digit password reset code

#### Password Changed Email
- `first_name` - User's first name (optional)
- `changed_at` - Timestamp when password was changed

## Testing

After making changes:
1. Restart your Django server
2. Trigger the email (register user, request password reset, etc.)
3. Check Resend dashboard → Logs to see the rendered email

## Notes

- Both HTML and plain text versions are sent automatically
- Templates use Django's template language (variables, filters, etc.)
- Email styling should be inline or in `<style>` tags (some email clients strip external CSS)
