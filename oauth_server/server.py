from aiohttp import web
import os
from google_auth_oauthlib.flow import Flow
from database import init_db, get_db, User, Deadline

os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

init_db()

CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [os.getenv("REDIRECT_URI")]
    }
}

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.course-work.readonly'
]



async def handle_callback(request):
    code = request.query.get('code')
    state = request.query.get('state')

    if not code or not state:
        return web.Response(text="❌ Error: Missing parameters")

    telegram_id = int(state)

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=os.getenv("REDIRECT_URI")
    )

    flow.fetch_token(code=code)
    credentials = flow.credentials

    db = get_db()
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if user:
        # Удаляем старые дедлайны при переподключении нового аккаунта
        db.query(Deadline).filter(Deadline.user_id == user.id).delete()
        
        # Обновляем токен
        user.google_token = credentials.refresh_token
        db.commit()

    db.close()

    html = """
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>✅ Успішно!</h1>
        <p>Google Classroom підключено.</p>
        <p>Можете закрити це вікно і повернутись до бота.</p>
    </body>
    </html>
    """

    return web.Response(text=html, content_type="text/html")


app = web.Application()
app.router.add_get('/auth/callback', handle_callback)

if __name__ == '__main__':
    print("🌐 OAuth server running on port 8000")
    web.run_app(app, host='0.0.0.0', port=8000)
