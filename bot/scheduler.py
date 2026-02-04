"""
Background scheduler for automated tasks:
- Auto-synchronization every 6-12 hours
- Reminder notifications before deadlines
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from database import get_db, User, Deadline, UserSettings
from classroom_sync import sync_user_deadlines
import os


# Bot instance will be set from bot.py
bot_instance = None


def set_bot_instance(bot):
    """Set bot instance for sending notifications"""
    global bot_instance
    bot_instance = bot


async def auto_sync_all_users():
    """Auto-sync all users with enabled auto-sync"""
    print(f"🔄 Auto-sync task started at {datetime.now()}")
    
    db = get_db()
    
    # Get all users with auto-sync enabled
    users = db.query(User).join(
        UserSettings, User.id == UserSettings.user_id, isouter=True
    ).filter(
        (UserSettings.auto_sync_enabled == True) | (UserSettings.id == None)
    ).all()
    
    for user in users:
        if not user.google_token:
            continue
            
        try:
            print(f"  Syncing user {user.telegram_id}...")
            added, updated, courses = sync_user_deadlines(
                user.id, 
                user.telegram_id, 
                user.google_token
            )
            
            if bot_instance and (added > 0 or updated > 0):
                await bot_instance.send_message(
                    user.telegram_id,
                    f"🔄 Автоматична синхронізація завершена!\n"
                    f"📝 Додано: {added}\n"
                    f"🔄 Оновлено: {updated}"
                )
        except Exception as e:
            print(f"  ❌ Error syncing user {user.telegram_id}: {e}")
    
    db.close()
    print(f"✅ Auto-sync completed")


async def check_and_send_reminders():
    """Check for upcoming deadlines and send reminders"""
    print(f"🔔 Checking reminders at {datetime.now()}")
    
    db = get_db()
    now = datetime.utcnow()
    
    # Check deadlines for reminders
    deadlines = db.query(Deadline).filter(
        Deadline.due_date > now,
        Deadline.completed == False
    ).all()
    
    for deadline in deadlines:
        time_until = deadline.due_date - now
        hours_until = time_until.total_seconds() / 3600
        
        user = db.query(User).filter(User.id == deadline.user_id).first()
        if not user:
            continue
            
        # Get user settings
        settings = db.query(UserSettings).filter(
            UserSettings.user_id == user.id
        ).first()
        
        # Default settings if not found
        if not settings:
            settings = UserSettings(
                user_id=user.id,
                remind_1day=True,
                remind_3hours=True,
                remind_1hour=True
            )
            db.add(settings)
        
        message_sent = False
        
        # 1 day reminder (20-28 hours)
        if settings.remind_1day and not deadline.reminder_1day and 20 <= hours_until <= 28:
            message = (
                f"📅 <b>Нагадування за 1 день!</b>\n\n"
                f"📖 {deadline.course_name}\n"
                f"📝 {deadline.title}\n"
                f"⏰ {deadline.due_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            if deadline.link:
                message += f"🔗 <a href='{deadline.link}'>Відкрити в Classroom</a>"
            
            deadline.reminder_1day = True
            message_sent = True
            
        # 3 hours reminder (2.5-3.5 hours)
        elif settings.remind_3hours and not deadline.reminder_3hours and 2.5 <= hours_until <= 3.5:
            message = (
                f"⏰ <b>Нагадування за 3 години!</b>\n\n"
                f"📖 {deadline.course_name}\n"
                f"📝 {deadline.title}\n"
                f"⏰ {deadline.due_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            if deadline.link:
                message += f"🔗 <a href='{deadline.link}'>Відкрити в Classroom</a>"
            
            deadline.reminder_3hours = True
            message_sent = True
            
        # 1 hour reminder (0.8-1.2 hours)
        elif settings.remind_1hour and not deadline.reminder_1hour and 0.8 <= hours_until <= 1.2:
            message = (
                f"🚨 <b>НАГАДУВАННЯ ЗА 1 ГОДИНУ!</b>\n\n"
                f"📖 {deadline.course_name}\n"
                f"📝 {deadline.title}\n"
                f"⏰ {deadline.due_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            if deadline.link:
                message += f"🔗 <a href='{deadline.link}'>Відкрити в Classroom</a>"
            
            deadline.reminder_1hour = True
            message_sent = True
        
        if message_sent and bot_instance:
            try:
                await bot_instance.send_message(
                    user.telegram_id,
                    message,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"  ❌ Failed to send reminder to {user.telegram_id}: {e}")
    
    db.commit()
    db.close()
    print(f"✅ Reminder check completed")


def start_scheduler():
    """Start the background scheduler"""
    scheduler = AsyncIOScheduler()
    
    # Auto-sync every 6 hours
    scheduler.add_job(
        auto_sync_all_users,
        IntervalTrigger(hours=6),
        id='auto_sync',
        name='Auto-sync Google Classroom',
        replace_existing=True
    )
    
    # Check reminders every 30 minutes
    scheduler.add_job(
        check_and_send_reminders,
        IntervalTrigger(minutes=30),
        id='check_reminders',
        name='Check and send reminders',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Scheduler started")
    print("  - Auto-sync: every 6 hours")
    print("  - Reminders: every 30 minutes")
    
    return scheduler
