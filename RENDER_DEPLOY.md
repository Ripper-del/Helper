# 🎨 Deployment на Render.com

Render.com - найкращий варіант для Docker проектів. Підтримує PostgreSQL з коробки.

## ✅ Переваги Render

- ✅ Нативна підтримка Docker
- ✅ Безкоштовний PostgreSQL
- ✅ 750 годин безкоштовно/місяць
- ✅ Автоматичні deploys з GitHub
- ✅ Простіше за Railway

## 🚀 Швидкий старт

### Крок 1: Створи акаунт

1. Зайди на https://render.com/
2. Sign Up через GitHub
3. Підтверди email

### Крок 2: Підготовка секретів

**Telegram Bot Token:**
- Telegram → @BotFather → `/newbot`
- Скопіюй токен

**Google Cloud:**
1. https://console.cloud.google.com/
2. Створи проект → Google Classroom API (Enable)
3. APIs & Services → Credentials → Create OAuth 2.0 Client
4. Authorized redirect URIs: `https://classroom-oauth.onrender.com/auth/callback`
5. Скопіюй Client ID та Client Secret

### Крок 3: Deploy на Render

**Варіант A: Через Blueprint (НАЙПРОСТІШЕ)**

1. В Render Dashboard натисни **"New +"** → **"Blueprint"**
2. Connect GitHub репозиторій `Helper`
3. Render автоматично знайде `render.yaml`
4. **Налаштуй Environment Variables:**
   - `BOT_TOKEN` = твій токен
   - `GOOGLE_CLIENT_ID` = твій client ID
   - `GOOGLE_CLIENT_SECRET` = твій secret
5. Натисни **"Apply"**
6. Render створить:
   - 🤖 `classroom-bot` (Web Service)
   - 🔐 `classroom-oauth` (Web Service)
   - ⏰ `classroom-checker` (Background Worker)
   - 🗄️ `classroom-db` (PostgreSQL)

**Варіант B: Вручну**

1. **Створи PostgreSQL:**
   - New + → PostgreSQL
   - Name: `classroom-db`
   - Database: `kpihelper`
   - Безкоштовний plan

2. **Створи Bot Service:**
   - New + → Web Service
   - Connect GitHub → `Helper`
   - Root Directory: `.`
   - Dockerfile Path: `bot/Dockerfile`
   - Environment:
     - `BOT_TOKEN`
     - `DATABASE_URL` (from database)
     - `GOOGLE_CLIENT_ID`
     - `GOOGLE_CLIENT_SECRET`
     - `REDIRECT_URI`

3. **Створи OAuth Service:**
   - New + → Web Service
   - Dockerfile Path: `oauth_server/Dockerfile`
   - Ті ж environment variables

4. **Створи Checker Service:**
   - New + → Background Worker
   - Dockerfile Path: `checker/Dockerfile`
   - Ті ж environment variables

### Крок 4: Оновлення REDIRECT_URI

Після deploy OAuth service:

1. Render дасть URL: `https://classroom-oauth-xxxx.onrender.com`
2. **Онови в Google Cloud Console:**
   - Authorized redirect URIs → `https://твій-oauth-url.onrender.com/auth/callback`
3. **Онови в Render:**
   - Bot service → Environment → `REDIRECT_URI` = новий URL

### Крок 5: Перевірка

1. Відкрий бота в Telegram
2. `/start`
3. `/connect` → OAuth має працювати
4. `/sync` → дедлайни синхронізуються

## 📊 Структура на Render

```
Render Dashboard
├── classroom-bot (Web Service) - Telegram бот
├── classroom-oauth (Web Service) - OAuth сервер
├── classroom-checker (Background Worker) - Нагадування
└── classroom-db (PostgreSQL) - База даних
```

## 💰 Безкоштовні ліміти

- **Web Services**: 750 годин/місяць (достатньо для 1 сервісу 24/7)
- **PostgreSQL**: 90 днів безкоштовно, потім $7/міс
- **Background Workers**: 750 годин/місяць

**Підказка:** Для економії можна об'єднати bot + oauth в один сервіс.

## 🔄 Автоматичні оновлення

Кожен `git push` автоматично оновлює все:

```bash
git add .
git commit -m "Update bot"
git push origin main
```

Render автоматично:
1. Бачить зміни в GitHub
2. Rebuild Docker images
3. Redeploy всі сервіси

## 🐛 Troubleshooting

### Bot не відповідає
- Перевір логи: Dashboard → Service → Logs
- Перевір `BOT_TOKEN` в Environment

### OAuth не працює
- Переконайся що `REDIRECT_URI` правильний
- Перевір що Google Cloud має той самий URL

### База даних не підключається
- Render автоматично створює `DATABASE_URL`
- Перевір Connection String в Database settings

### Web Service засинає
- Безкоштовні web services засинають після 15 хв неактивності
- Вони автоматично прокидаються при запиті
- Для 24/7: потрібен платний plan ($7/міс)

## 💡 Оптимізація

**Об'єднати Bot + OAuth в один сервіс:**
- Економить 750 годин
- Один Dockerfile з двома процесами
- Складніше налаштувати

**Використати Cron Jobs замість Background Worker:**
- Cron Jobs безкоштовні
- Checker може працювати як cron
- Запускається кожні 30 хв

## 📈 Моніторинг

Render Dashboard показує:
- CPU/Memory usage
- Request metrics
- Логи в реальному часі
- Deploy history

## ⚠️ Важливо

1. Безкоштовні web services **засинають** після 15 хв
2. PostgreSQL безкоштовна тільки **90 днів**
3. Після 90 днів потрібен платний plan або міграція
4. Всі секрети зберігай в Environment Variables на Render
