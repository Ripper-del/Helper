import asyncio
import os
from datetime import datetime, timedelta
from aiogram import Bot
from database import get_db, User, Deadline
from classroom_api import fetch_all_deadlines

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)


async def sync_user_deadlines(user_id: int, telegram_id: int, google_token: str):
    print(f"🔄 Синхронизация для user {telegram_id}...")

    deadlines_data = fetch_all_deadlines(google_token)

    if not deadlines_data:
        print(f"⚠️ Нет дедлайнов для user {telegram_id}")
        return

    db = get_db()
    added_count = 0
    updated_count = 0

    for dl_data in deadlines_data:
        existing = db.query(Deadline).filter(
            Deadline.external_id == dl_data['external_id']
        ).first()

        if existing:
            existing.due_date = dl_data['due_date']
            existing.title = dl_data['title']
            existing.link = dl_data['link']
            existing.notified = False
            updated_count += 1
        else:
            new_deadline = Deadline(
                user_id=user_id,
                course_name=dl_data['course_name'],
                title=dl_data['title'],
                due_date=dl_data['due_date'],
                link=dl_data['link'],
                external_id=dl_data['external_id'],
                notified=False
            )
            db.add(new_deadline)
            added_count += 1

    db.commit()
    db.close()

    print(f"✅ User {telegram_id}: добавлено {added_count}, обновлено {updated_count}")

    try:
        await bot.send_message(
            telegram_id,
            f"✅ Синхронізація завершена!\n"
            f"📝 Додано нових: {added_count}\n"
            f"🔄 Оновлено: {updated_count}\n\n"
            f"Використайте /deadlines для перегляду"
        )
    except Exception as e:
        print(f"❌ Не вдалося відправити повідомлення user {telegram_id}: {e}")


async def check_deadlines():
    print("🔔 Checking deadlines...")

    db = get_db()
    now = datetime.utcnow()
    tomorrow = now + timedelta(hours=24)

    deadlines = db.query(Deadline).filter(
        Deadline.due_date >= now,
        Deadline.due_date <= tomorrow,
        Deadline.notified == False
    ).all()

    for deadline in deadlines:
        user = db.query(User).filter(User.id == deadline.user_id).first()
        if not user:
            continue

        time_left = deadline.due_date - now
        hours_left = time_left.seconds // 3600

        message = (
            f"⚠️ <b>Нагадування про дедлайн!</b>\n\n"
            f"📝 {deadline.title}\n"
            f"📖 Курс: {deadline.course_name}\n"
            f"⏰ Дедлайн: {deadline.due_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏳ Залишилось: {hours_left} годин\n"
        )

        if deadline.link:
            message += f"🔗 <a href='{deadline.link}'>Відкрити завдання</a>"

        try:
            await bot.send_message(user.telegram_id, message, parse_mode="HTML")
            deadline.notified = True
            print(f"✅ Уведомление отправлено user {user.telegram_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления: {e}")

    db.commit()
    db.close()


async def sync_all_users():
    print("🔄 Синхронизация всех пользователей...")

    db = get_db()
    users = db.query(User).filter(User.google_token != None).all()
    db.close()

    for user in users:
        try:
            await sync_user_deadlines(user.id, user.telegram_id, user.google_token)
        except Exception as e:
            print(f"❌ Ошибка синхронизации user {user.telegram_id}: {e}")


async def main():
    print("🔔 Checker started...")

    while True:
        try:
            await sync_all_users()
            await check_deadlines()

            print("⏰ Следующая проверка через 30 минут...")
            await asyncio.sleep(1800)

        except Exception as e:
            print(f"❌ Ошибка в checker: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
