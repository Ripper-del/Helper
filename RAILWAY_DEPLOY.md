# 🚂 Deployment на Railway.app

## Крок 1: Створи акаунт на Railway

1. Зайди на https://railway.app/
2. Зареєструйся через GitHub
3. Підтверди email

## Крок 2: Отримай Telegram Bot Token

1. Відкрий Telegram, знайди @BotFather
2. Надішли команду `/newbot`
3. Слідуй інструкціям
4. Скопіюй токен (виглядає як `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

## Крок 3: Налаштуй Google Cloud Project

1. Зайди на https://console.cloud.google.com/
2. Створи новий проект
3. Увімкни **Google Classroom API**
4. Іди в **APIs & Services > Credentials**
5. Створи **OAuth 2.0 Client ID** (Web application)
6. В **Authorized redirect URIs** додай:
   ```
   https://your-project-name.up.railway.app/auth/callback
   ```
   (замість `your-project-name` буде твоя назва проекту на Railway)
7. Скопіюй **Client ID** та **Client Secret**

## Крок 4: Deploy на Railway

### Варіант A: Через GitHub (РЕКОМЕНДОВАНО)

1. **Створи новий проект на Railway:**
   - Натисни "New Project"
   - Вибери "Deploy from GitHub repo"
   - Вибери репозиторій `Helper`

2. **Додай PostgreSQL:**
   - Натисни "New Service"
   - Вибери "Database"
   - Вибери "PostgreSQL"
   - Railway автоматично створить базу даних

3. **Налаштуй Environment Variables:**
   
   В налаштуваннях проекту додай змінні:
   
   ```
   BOT_TOKEN=твій_токен_від_BotFather
   GOOGLE_CLIENT_ID=твій_google_client_id
   GOOGLE_CLIENT_SECRET=твій_google_client_secret
   REDIRECT_URI=https://your-project-name.up.railway.app/auth/callback
   ```
   
   Railway автоматично створить:
   - `DATABASE_URL` (з PostgreSQL сервісу)
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `POSTGRES_DB`

4. **Deploy:**
   - Railway автоматично задеплоїть після push в GitHub
   - Чекай ~2-3 хвилини

### Варіант B: Через Railway CLI

```bash
# Встанови Railway CLI
npm i -g @railway/cli

# Залогінься
railway login

# Ініціалізуй проект
railway init

# Додай PostgreSQL
railway add

# Налаштуй змінні оточення
railway variables set BOT_TOKEN=your_token
railway variables set GOOGLE_CLIENT_ID=your_client_id
railway variables set GOOGLE_CLIENT_SECRET=your_secret
railway variables set REDIRECT_URI=https://your-app.up.railway.app/auth/callback

# Deploy
railway up
```

## Крок 5: Оновлення REDIRECT_URI

Після першого deploy:

1. Railway дасть тобі URL: `https://your-app-name.up.railway.app`
2. Скопіюй цей URL
3. Іди в Google Cloud Console
4. Онови **Authorized redirect URIs** на:
   ```
   https://your-app-name.up.railway.app/auth/callback
   ```
5. Онови змінну `REDIRECT_URI` на Railway

## Крок 6: Перевірка

1. Відкрий свого бота в Telegram
2. Надішли `/start`
3. Натисни `/connect`
4. Пройди OAuth авторизацію
5. Надішли `/sync`

## 🔧 Troubleshooting

### Бот не відповідає
- Перевір логи на Railway: `Deployments > View Logs`
- Перевір чи правильний `BOT_TOKEN`

### OAuth не працює
- Перевір `REDIRECT_URI` в Google Cloud і на Railway
- Переконайся що Google Classroom API увімкнено

### База даних не підключається
- Railway автоматично створює `DATABASE_URL`
- Перевір чи PostgreSQL сервіс запущений

## 💰 Ціни

Railway надає:
- **$5 безкоштовних кредитів щомісяця**
- Цього вистачить для:
  - 1 бот (bot service)
  - 1 checker service
  - 1 oauth_server
  - PostgreSQL база даних
  
При невеликому використанні (~10-50 користувачів) - повністю безкоштовно!

## 🔄 Автоматичне оновлення

Кожен `git push` в GitHub автоматично оновлює бота на Railway!

```bash
git add .
git commit -m "Update bot"
git push origin main
```

## 📊 Моніторинг

Railway Dashboard показує:
- CPU/Memory usage
- Логи в реальному часі
- Статус кожного сервісу
- Metrics та аналітика

## ⚠️ Важливо

1. **Ніколи не комітьте .env** в git!
2. Всі секрети зберігай в Railway Environment Variables
3. Після зміни змінних - перезапусти сервіси
4. Регулярно перевіряй логи на помилки
