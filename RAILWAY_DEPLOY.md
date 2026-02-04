# 🚂 Railway Deployment - ОНОВЛЕНА ІНСТРУКЦІЯ

## ❗ Важлива зміна

Railway не підтримує Docker Compose безпосередньо. Потрібно створити **3 окремі сервіси**.

## 📋 Покрокова інструкція

### Крок 1: Створи проект на Railway

1. Зайди на https://railway.app/
2. Натисни **"New Project"**
3. Вибери **"Deploy from GitHub repo"**
4. Вибери репозиторій **Helper**

### Крок 2: Додай PostgreSQL

1. В проекті натисни **"New"**
2. Вибери **"Database"** → **"PostgreSQL"**
3. Railway автоматично створить базу даних
4. Скопіюй `DATABASE_URL` зі змінних

### Крок 3: Налаштуй Bot Service (головний)

Перший сервіс вже створений з GitHub. Налаштуй його:

1. **Settings** → **Root Directory**: залиш порожнім
2. **Variables** - додай:
   ```
   BOT_TOKEN=твій_токен
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   GOOGLE_CLIENT_ID=твій_client_id
   GOOGLE_CLIENT_SECRET=твій_secret
   REDIRECT_URI=https://твій-проект.up.railway.app/auth/callback
   ```

### Крок 4: Створи Checker Service

1. Натисни **"New"** → **"GitHub Repo"**
2. Вибери той самий репозиторій **Helper**
3. **Settings**:
   - **Service Name**: `checker`
   - **Root Directory**: `checker`
   - **Start Command**: `python checker.py`
4. **Variables** (ті ж самі що в bot):
   ```
   BOT_TOKEN=${{bot.BOT_TOKEN}}
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   GOOGLE_CLIENT_ID=${{bot.GOOGLE_CLIENT_ID}}
   GOOGLE_CLIENT_SECRET=${{bot.GOOGLE_CLIENT_SECRET}}
   ```

### Крок 5: Створи OAuth Server Service

1. Натисни **"New"** → **"GitHub Repo"**
2. Вибери **Helper**
3. **Settings**:
   - **Service Name**: `oauth-server`
   - **Root Directory**: `oauth_server`
   - **Start Command**: `python server.py`
4. **Variables**:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   GOOGLE_CLIENT_ID=${{bot.GOOGLE_CLIENT_ID}}
   GOOGLE_CLIENT_SECRET=${{bot.GOOGLE_CLIENT_SECRET}}
   REDIRECT_URI=${{bot.REDIRECT_URI}}
   ```
5. **Networking**:
   - **Generate Domain** - це дасть публічний URL для OAuth

### Крок 6: Оновлення REDIRECT_URI

Після створення всіх сервісів:

1. OAuth Server отримає URL типу `https://oauth-server-production-xxxx.up.railway.app`
2. **Онови `REDIRECT_URI`** в bot service на:
   ```
   https://oauth-server-production-xxxx.up.railway.app/auth/callback
   ```
3. **Онови в Google Cloud Console**:
   - Іди в OAuth 2.0 Client
   - Додай в Authorized redirect URIs:
     ```
     https://oauth-server-production-xxxx.up.railway.app/auth/callback
     ```

### Крок 7: Перевірка

1. Всі 4 сервіси повинні бути **Active** (зелені)
2. Перевір логи кожного сервісу
3. Відкрий бота в Telegram → `/start`

## 🎯 Структура проекту на Railway

```
Railway Project
├── bot (GitHub: Helper, root: /)
├── checker (GitHub: Helper, root: checker/)
├── oauth-server (GitHub: Helper, root: oauth_server/)
└── PostgreSQL (Database)
```

## 📊 Очікуване використання

- **Bot**: ~512MB RAM, завжди запущений
- **Checker**: ~256MB RAM, запускається кожні 30 хв
- **OAuth**: ~256MB RAM, тільки при OAuth
- **PostgreSQL**: ~256MB RAM

**Загалом**: ~1.5GB RAM - вкладається в $5 безкоштовних кредитів!

## 🔧 Troubleshooting

### Build fails
- Перевір що `Root Directory` правильно встановлений
- Перевір логи в Deployments

### Bot не відповідає
- Перевір BOT_TOKEN
- Перевір що bot service запущений (зелений)

### OAuth не працює
- Переконайся що oauth-server має публічний домен
- REDIRECT_URI повинен використовувати OAuth server URL, не bot URL

### База даних не підключається  
- Використовуй `${{Postgres.DATABASE_URL}}` для автоматичного підключення
- Не hardcode DATABASE_URL

## 💡 Важливо

1. Кожен push в GitHub автоматично оновлює ВСІ 3 сервіси
2. Змінні можна шарити між сервісами: `${{service.VARIABLE}}`
3. Railway автоматично перезапускає сервіси при крашах
4. Логи доступні в реальному часі для кожного сервісу

## 🔄 Автодеплой

```bash
git add .
git commit -m "Update"
git push origin main
```

Всі 3 сервіси автоматично оновляться!
