import os

# ✅ Виправлений список прав (SCOPES)
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly'
]


def get_authorization_url(telegram_id: int) -> str:
    """Генерирует URL для авторизации Google"""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")

    scope = " ".join(SCOPES)

    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={telegram_id}"
    )

    return url