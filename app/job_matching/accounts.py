from __future__ import annotations


def is_candidate(user) -> bool:
    """Employer and academy accounts count only when they also have a candidate UserProfile."""
    from app.models import UserProfile
    from app.views import _user_is_academy, _user_is_employer

    if not (_user_is_employer(user) or _user_is_academy(user)):
        return True
    return UserProfile.objects.filter(user_id=user.pk).exists()


def has_verified_email(user) -> bool:
    """Signup verifies the code sent to the email and stores that address as the username.
    An email edited later on the profile has not been verified, so it no longer matches."""
    email = (user.email or "").strip()
    if not email or not user.is_active:
        return False
    return email.lower() == (user.username or "").strip().lower()
