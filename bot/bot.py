import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
from database import init_db, get_db, User, Deadline, Coursework
from google_auth import get_authorization_url
from google.auth.exceptions import RefreshError

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Количество дедлайнов на странице
DEADLINES_PER_PAGE = 5


# FSM States для добавления дедлайна
class AddDeadlineStates(StatesGroup):
    waiting_for_course = State()
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_link = State()


def get_main_keyboard():
    """Создать основную клавиатуру с кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Дедлайни"),
                KeyboardButton(text="📖 Курси")
            ],
            [
                KeyboardButton(text="➕ Додати дедлайн"),
                KeyboardButton(text="🔄 Синхронізація")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard



@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    telegram_id = message.from_user.id
    username = message.from_user.username

    db = get_db()
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        user = User(telegram_id=telegram_id, username=username)
        db.add(user)
        db.commit()

    db.close()

    await message.answer(
        "👋 Привіт! Я бот для нагадувань про дедлайни з Google Classroom.\n\n"
        "📚 Команди:\n"
        "/connect - Підключити Google Classroom\n"
        "/deadlines - Показати актуальні дедлайни\n"
        "/courses - Вибрати предмет\n"
        "/sync - Синхронізувати дедлайни\n\n"
        "Використовуй кнопки внизу для швидкого доступу! 👇",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("connect"))
async def cmd_connect(message: types.Message):
    telegram_id = message.from_user.id
    auth_url = get_authorization_url(telegram_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Підключити Google", url=auth_url)]
    ])

    await message.answer(
        "Натисніть кнопку для підключення Google Classroom:",
        reply_markup=keyboard
    )


@dp.message(Command("deadlines"))
async def cmd_deadlines(message: types.Message):
    """Показать актуальные дедлайны с пагинацией"""
    telegram_id = message.from_user.id
    await show_deadlines_page(message, telegram_id, page=0)


async def show_deadlines_page(message: types.Message, telegram_id: int, page: int = 0):
    """Показать страницу дедлайнов"""
    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await message.answer("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return
    
    now = datetime.utcnow()

    deadlines = db.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.due_date >= now
    ).order_by(Deadline.due_date).all()

    db.close()

    if not deadlines:
        await message.answer("📭 У вас немає актуальних дедлайнів.")
        return

    # Пагинация
    total_pages = (len(deadlines) - 1) // DEADLINES_PER_PAGE + 1
    page = max(0, min(page, total_pages - 1))

    start_idx = page * DEADLINES_PER_PAGE
    end_idx = start_idx + DEADLINES_PER_PAGE
    page_deadlines = deadlines[start_idx:end_idx]

    text = f"📚 <b>Актуальні дедлайни ({page + 1}/{total_pages}):</b>\n\n"

    for dl in page_deadlines:
        time_left = dl.due_date - now
        days_left = time_left.days
        hours_left = time_left.seconds // 3600

        text += f"📝 <b>{dl.title}</b>\n"
        text += f"📖 {dl.course_name}\n"
        text += f"⏰ {dl.due_date.strftime('%d.%m.%Y %H:%M')}\n"

        if days_left > 0:
            text += f"⏳ Залишилось: {days_left} д. {hours_left} год.\n"
        else:
            text += f"⏳ Залишилось: {hours_left} год.\n"

        if dl.link:
            text += f"🔗 <a href='{dl.link}'>Відкрити</a>\n"
        text += "\n"

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"dl_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"dl_page_{page + 1}"))

    keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


@dp.callback_query(F.data.startswith("dl_page_"))
async def process_deadlines_page(callback_query: types.CallbackQuery):
    """Обработка переключения страниц дедлайнов"""
    await callback_query.answer()

    page = int(callback_query.data.replace("dl_page_", ""))
    telegram_id = callback_query.from_user.id

    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await callback_query.message.edit_text("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return
    
    now = datetime.utcnow()

    # Получаем ТОЛЬКО активные дедлайны
    deadlines = db.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.due_date >= now
    ).order_by(Deadline.due_date).all()

    db.close()

    if not deadlines:
        await callback_query.message.edit_text("📭 У вас немає активних дедлайнів.")
        return

    # Пагинация
    total_pages = (len(deadlines) - 1) // DEADLINES_PER_PAGE + 1
    page = max(0, min(page, total_pages - 1))

    start_idx = page * DEADLINES_PER_PAGE
    end_idx = start_idx + DEADLINES_PER_PAGE
    page_deadlines = deadlines[start_idx:end_idx]

    text = f"📚 <b>Активні дедлайни ({page + 1}/{total_pages}):</b>\n\n"

    for dl in page_deadlines:
        time_left = dl.due_date - now
        days_left = time_left.days
        hours_left = time_left.seconds // 3600

        text += f"✅ <b>{dl.title}</b>\n"
        text += f"📖 {dl.course_name}\n"
        text += f"⏰ {dl.due_date.strftime('%d.%m.%Y %H:%M')}\n"

        if days_left > 0:
            text += f"⏳ Залишилось: {days_left} д. {hours_left} год.\n"
        else:
            text += f"⏳ Залишилось: {hours_left} год.\n"

        if dl.link:
            text += f"🔗 <a href='{dl.link}'>Відкрити</a>\n"
        text += "\n"

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"dl_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"dl_page_{page + 1}"))

    keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")


@dp.message(Command("courses"))
async def cmd_courses(message: types.Message):
    """Показать список предметов"""
    telegram_id = message.from_user.id
    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await message.answer("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return

    # Получаем список всех курсов из кеша или из базы данных
    if hasattr(bot, 'all_courses_cache') and telegram_id in bot.all_courses_cache:
        all_courses_list = bot.all_courses_cache[telegram_id]
    else:
        # Fallback: получаем только курсы с дедлайнами из базы
        courses_db = db.query(Deadline.course_name).filter(
            Deadline.user_id == user.id
        ).distinct().all()
        all_courses_list = [c[0] for c in courses_db]

    db.close()

    if not all_courses_list:
        await message.answer("📭 У вас ще немає курсів. Спочатку виконайте /sync")
        return

    # Создаем кнопки для каждого курса
    keyboard = []
    for idx, course_name in enumerate(all_courses_list):
        # Обрезаем длинные названия
        display_name = course_name[:45] + "..." if len(course_name) > 45 else course_name
        keyboard.append([
            InlineKeyboardButton(
                text=f"📖 {display_name}",
                callback_data=f"c_{idx}_0"  # idx курса + страница 0
            )
        ])

    # Сохраняем курсы в кеш для обработки callback
    if not hasattr(bot, 'courses_cache'):
        bot.courses_cache = {}
    bot.courses_cache[telegram_id] = all_courses_list

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "📚 <b>Оберіть предмет:</b>",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


# Обработчик кнопки "📖 Курси"
@dp.message(F.text == "📖 Курси")
async def show_courses_button(message: types.Message):
    """Показать список предметов через кнопку"""
    # Переиспользуем логику команды /courses
    await cmd_courses(message)


@dp.callback_query(F.data.startswith("c_"))
async def process_course_callback(callback_query: types.CallbackQuery):
    """Обработка выбора курса с пагинацией"""
    await callback_query.answer()

    parts = callback_query.data.split("_")
    course_idx = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    telegram_id = callback_query.from_user.id

    if not hasattr(bot, 'courses_cache') or telegram_id not in bot.courses_cache:
        await callback_query.message.answer("❌ Помилка. Спробуйте /courses ще раз.")
        return

    courses_list = bot.courses_cache[telegram_id]
    if course_idx >= len(courses_list):
        await callback_query.message.answer("❌ Предмет не знайдено.")
        return

    course_name = courses_list[course_idx]

    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await callback_query.message.answer("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return
    
    now = datetime.utcnow()

    all_deadlines = db.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.course_name == course_name
    ).order_by(Deadline.due_date).all()
    
    # Получаем coursework без дедлайнов
    all_coursework = db.query(Coursework).filter(
        Coursework.user_id == user.id,
        Coursework.course_name == course_name
    ).all()

    db.close()

    if not all_deadlines and not all_coursework:
        await callback_query.message.answer("📭 Дедлайнів не знайдено.")
        return

    active = [dl for dl in all_deadlines if dl.due_date >= now]
    expired = [dl for dl in all_deadlines if dl.due_date < now]

    # Объединяем: сначала актуальные, потом просроченные, потом coursework без дедлайнов
    all_items = active + expired + all_coursework

    # Пагинация
    total_pages = (len(all_items) - 1) // DEADLINES_PER_PAGE + 1
    page = max(0, min(page, total_pages - 1))

    start_idx = page * DEADLINES_PER_PAGE
    end_idx = start_idx + DEADLINES_PER_PAGE
    page_items = all_items[start_idx:end_idx]

    text = f"📖 <b>{course_name}</b> ({page + 1}/{total_pages})\n\n"

    for item in page_items:
        # Проверяем, это deadline или coursework
        if isinstance(item, Deadline):
            is_active = item.due_date >= now

            if is_active:
                time_left = item.due_date - now
                days_left = time_left.days
                hours_left = time_left.seconds // 3600

                text += f"✅ <b>{item.title}</b>\n"
                text += f"⏰ {item.due_date.strftime('%d.%m.%Y %H:%M')}\n"

                if days_left > 0:
                    text += f"⏳ Залишилось: {days_left} д. {hours_left} год.\n"
                else:
                    text += f"⏳ Залишилось: {hours_left} год.\n"
            else:
                text += f"❌ {item.title}\n"
                text += f"⏰ Був: {item.due_date.strftime('%d.%m.%Y %H:%M')}\n"

            if item.link:
                text += f"🔗 <a href='{item.link}'>Відкрити</a>\n"
        else:  # Coursework без дедлайна
            text += f"📝 {item.title}\n"
            text += f"⚠️ <i>Без дедлайну</i>\n"
            if item.link:
                text += f"🔗 <a href='{item.link}'>Відкрити</a>\n"
        
        text += "\n"

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"c_{course_idx}_{page - 1}"
        ))

    nav_buttons.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="ignore"
    ))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"c_{course_idx}_{page + 1}"
        ))

    keyboard.append(nav_buttons)

    # Кнопка "Назад до списку"
    keyboard.append([InlineKeyboardButton(
        text="◀️ До списку предметів",
        callback_data="back_to_courses"
    )])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")


@dp.callback_query(F.data == "back_to_courses")
async def back_to_courses(callback_query: types.CallbackQuery):
    """Вернуться к списку курсов"""
    await callback_query.answer()

    telegram_id = callback_query.from_user.id

    if not hasattr(bot, 'courses_cache') or telegram_id not in bot.courses_cache:
        await callback_query.message.answer("❌ Помилка. Спробуйте /courses ще раз.")
        return

    courses_list = bot.courses_cache[telegram_id]

    keyboard = []
    for idx, course_name in enumerate(courses_list):
        display_name = course_name[:45] + "..." if len(course_name) > 45 else course_name
        keyboard.append([
            InlineKeyboardButton(
                text=f"📖 {display_name}",
                callback_data=f"c_{idx}_0"
            )
        ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback_query.message.edit_text(
        "📚 <b>Оберіть предмет:</b>",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback_query: types.CallbackQuery):
    """Игнорировать нажатие на счетчик страниц"""
    await callback_query.answer()


@dp.message(Command("sync"))
async def cmd_sync(message: types.Message):
    telegram_id = message.from_user.id
    db = get_db()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user or not user.google_token:
        await message.answer("⚠️ Спочатку підключіть Google Classroom (/connect)")
        db.close()
        return

    await message.answer("🔄 Синхронізація... Це може зайняти хвилину.")
    
    # Выполняем синхронизацию
    try:
        from classroom_sync import sync_user_deadlines
        added_count, updated_count, all_courses = sync_user_deadlines(user.id, telegram_id, user.google_token)
        
        # Сохраняем список всех курсов в кеш
        if not hasattr(bot, 'all_courses_cache'):
            bot.all_courses_cache = {}
        bot.all_courses_cache[telegram_id] = all_courses
        
        await message.answer(
            f"✅ Синхронізація завершена!\n"
            f"📝 Додано нових: {added_count}\n"
            f"🔄 Оновлено: {updated_count}\n"
            f"📚 Знайдено курсів: {len(all_courses)}\n\n"
            f"Використайте кнопку '📚 Дедлайни' для перегляду!"
        )
    except RefreshError:
        print(f"❌ Token expired for user {telegram_id}")
        # Инвалидируем токен
        user.google_token = None
        db.commit()
        
        await message.answer(
            "⚠️ <b>Термін дії доступу минув!</b>\n\n"
            "Google вимагає повторного входу (зазвичай раз на 7 днів для тестових додатків).\n"
            "Будь ласка, підключіться знову: /connect",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Помилка синхронізації: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(
            f"❌ Помилка при синхронізації.\n"
            f"Деталі: {str(e)}\n\n"
            f"Спробуйте ще раз або зверніться до адміністратора."
        )
    finally:
        db.close()


# Обработчик кнопки "🔄 Синхронізація"
@dp.message(F.text == "🔄 Синхронізація")
async def sync_button_handler(message: types.Message):
    """Синхронізація через кнопку"""
    await cmd_sync(message)


# Обработчик кнопки "📚 Дедлайни" (только активные дедлайны)
@dp.message(F.text == "📚 Дедлайни")
async def show_active_deadlines(message: types.Message):
    """Показать активные дедлайны"""
    telegram_id = message.from_user.id
    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await message.answer("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return
    
    now = datetime.utcnow()

    # Получаем ТОЛЬКО активные дедлайны
    deadlines = db.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.due_date >= now
    ).order_by(Deadline.due_date).all()

    db.close()

    if not deadlines:
        await message.answer("📭 У вас немає активних дедлайнів.")
        return

    # Пагинация
    total_pages = (len(deadlines) - 1) // DEADLINES_PER_PAGE + 1
    page = 0

    start_idx = page * DEADLINES_PER_PAGE
    end_idx = start_idx + DEADLINES_PER_PAGE
    page_deadlines = deadlines[start_idx:end_idx]

    text = f"📚 <b>Активні дедлайни ({page + 1}/{total_pages}):</b>\n\n"

    for dl in page_deadlines:
        time_left = dl.due_date - now
        days_left = time_left.days
        hours_left = time_left.seconds // 3600

        text += f"✅ <b>{dl.title}</b>\n"
        text += f"📖 {dl.course_name}\n"
        text += f"⏰ {dl.due_date.strftime('%d.%m.%Y %H:%M')}\n"

        if days_left > 0:
            text += f"⏳ Залишилось: {days_left} д. {hours_left} год.\n"
        else:
            text += f"⏳ Залишилось: {hours_left} год.\n"

        if dl.link:
            text += f"🔗 <a href='{dl.link}'>Відкрити</a>\n"
        text += "\n"

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"dl_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"dl_page_{page + 1}"))

    keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


# Обработчик кнопки "❌ Прострочені" (просроченные дедлайны)
@dp.message(F.text == "❌ Прострочені")
async def show_overdue_deadlines(message: types.Message):
    """Показать просроченные дедлайны"""
    telegram_id = message.from_user.id
    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await message.answer("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return
    
    now = datetime.utcnow()

    deadlines = db.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.due_date < now
    ).order_by(Deadline.due_date.desc()).all()

    db.close()

    if not deadlines:
        await message.answer("✅ У вас немає прострочених дедлайнів!")
        return

    # Пагинация
    total_pages = (len(deadlines) - 1) // DEADLINES_PER_PAGE + 1
    page = 0

    start_idx = page * DEADLINES_PER_PAGE
    end_idx = start_idx + DEADLINES_PER_PAGE
    page_deadlines = deadlines[start_idx:end_idx]

    text = f"❌ <b>Прострочені дедлайни ({page + 1}/{total_pages}):</b>\n\n"

    for dl in page_deadlines:
        time_ago = now - dl.due_date
        days_ago = time_ago.days
        hours_ago = time_ago.seconds // 3600

        text += f"📝 {dl.title}\n"
        text += f"📖 {dl.course_name}\n"
        text += f"⏰ Був: {dl.due_date.strftime('%d.%m.%Y %H:%M')}\n"

        if days_ago > 0:
            text += f"⌛ Прострочено: {days_ago} д. {hours_ago} год. тому\n"
        else:
            text += f"⌛ Прострочено: {hours_ago} год. тому\n"

        if dl.link:
            text += f"🔗 <a href='{dl.link}'>Відкрити</a>\n"
        text += "\n"

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"overdue_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"overdue_page_{page + 1}"))

    keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


# Обработчик пагинации для просроченных дедлайнов
@dp.callback_query(F.data.startswith("overdue_page_"))
async def process_overdue_page(callback_query: types.CallbackQuery):
    """Обработка переключения страниц просроченных дедлайнов"""
    await callback_query.answer()

    page = int(callback_query.data.replace("overdue_page_", ""))
    telegram_id = callback_query.from_user.id

    db = get_db()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        await callback_query.message.edit_text("❌ Користувача не знайдено. Спробуйте /start")
        db.close()
        return
    
    now = datetime.utcnow()

    deadlines = db.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.due_date < now
    ).order_by(Deadline.due_date.desc()).all()

    db.close()

    if not deadlines:
        await callback_query.message.edit_text("✅ У вас немає прострочених дедлайнів!")
        return

    # Пагинация
    total_pages = (len(deadlines) - 1) // DEADLINES_PER_PAGE + 1
    page = max(0, min(page, total_pages - 1))

    start_idx = page * DEADLINES_PER_PAGE
    end_idx = start_idx + DEADLINES_PER_PAGE
    page_deadlines = deadlines[start_idx:end_idx]

    text = f"❌ <b>Прострочені дедлайни ({page + 1}/{total_pages}):</b>\n\n"

    for dl in page_deadlines:
        time_ago = now - dl.due_date
        days_ago = time_ago.days
        hours_ago = time_ago.seconds // 3600

        text += f"📝 {dl.title}\n"
        text += f"📖 {dl.course_name}\n"
        text += f"⏰ Був: {dl.due_date.strftime('%d.%m.%Y %H:%M')}\n"

        if days_ago > 0:
            text += f"⌛ Прострочено: {days_ago} д. {hours_ago} год. тому\n"
        else:
            text += f"⌛ Прострочено: {hours_ago} год. тому\n"

        if dl.link:
            text += f"🔗 <a href='{dl.link}'>Відкрити</a>\n"
        text += "\n"

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"overdue_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"overdue_page_{page + 1}"))

    keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")


# Обработчик для inline кнопки "Скасувати" при додаванні дедлайну
@dp.callback_query(F.data == "cancel_add_deadline")
async def cancel_add_deadline_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Отмена добавления дедлайна через inline кнопку"""
    await state.clear()
    await callback_query.message.edit_text("❌ Додавання дедлайну скасовано.")
    await callback_query.answer()


# Обработчик кнопки "➕ Додати дедлайн"
@dp.message(F.text == "➕ Додати дедлайн")
async def start_add_deadline(message: types.Message, state: FSMContext):
    """Начать процесс добавления дедлайна"""
    await state.set_state(AddDeadlineStates.waiting_for_course)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_deadline")]
    ])
    
    await message.answer(
        "📖 Введіть назву предмета (курсу):\n\n"
        "Наприклад: Математичний аналіз",
        reply_markup=cancel_keyboard
    )


@dp.message(AddDeadlineStates.waiting_for_course)
async def process_course_name(message: types.Message, state: FSMContext):
    """Обработка названия курса"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Додавання дедлайну скасовано.", reply_markup=get_main_keyboard())
        return

    await state.update_data(course_name=message.text)
    await state.set_state(AddDeadlineStates.waiting_for_title)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_deadline")]
    ])
    
    await message.answer(
        "📝 Введіть назву завдання:\n\n"
        "Наприклад: Лабораторна робота №3",
        reply_markup=cancel_keyboard
    )


@dp.message(AddDeadlineStates.waiting_for_title)
async def process_deadline_title(message: types.Message, state: FSMContext):
    """Обработка названия задания"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Додавання дедлайну скасовано.", reply_markup=get_main_keyboard())
        return

    await state.update_data(title=message.text)
    await state.set_state(AddDeadlineStates.waiting_for_date)
    
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_deadline")]
    ])
    
    await message.answer(
        "📅 Введіть дату дедлайну:\n\n"
        "Формат: ДД.ММ.РРРР\n"
        "Наприклад: 25.12.2026",
        reply_markup=cancel_keyboard
    )


@dp.message(AddDeadlineStates.waiting_for_date)
async def process_deadline_date(message: types.Message, state: FSMContext):
    """Обработка даты дедлайна"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Додавання дедлайну скасовано.", reply_markup=get_main_keyboard())
        return

    try:
        # Парсинг даты (только дата)
        date_obj = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(deadline_date=date_obj.strftime("%d.%m.%Y"))
        
        await state.set_state(AddDeadlineStates.waiting_for_time)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏩ Пропустити (23:59)", callback_data="skip_time")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_deadline")]
        ])
        
        await message.answer(
            "⏰ Введіть час дедлайну (ГГ:ХХ):\n"
            "Наприклад: 14:30\n\n"
            "Або натисніть 'Пропустити' (буде встановлено 23:59)",
            reply_markup=keyboard
        )

    except ValueError:
        await message.answer(
            "❌ Неправильний формат дати!\n\n"
            "Використовуй формат: ДД.ММ.РРРР\n"
            "Наприклад: 25.12.2026",
            reply_markup=get_main_keyboard()
        )


@dp.callback_query(F.data == "skip_time", AddDeadlineStates.waiting_for_time)
async def skip_time_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Пропуск ввода времени"""
    await callback_query.answer()
    await state.update_data(deadline_time="23:59")
    await proceed_to_link(callback_query.message, state)


@dp.message(AddDeadlineStates.waiting_for_time)
async def process_deadline_time(message: types.Message, state: FSMContext):
    """Обработка времени дедлайна"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Додавання дедлайну скасовано.", reply_markup=get_main_keyboard())
        return

    try:
        # Валидация времени
        datetime.strptime(message.text.strip(), "%H:%M")
        await state.update_data(deadline_time=message.text.strip())
        await proceed_to_link(message, state)
    except ValueError:
        await message.answer("❌ Неправильний формат часу! Введіть ГГ:ХХ (напр. 14:30) або натисніть кнопку пропуску.")


async def proceed_to_link(message: types.Message, state: FSMContext):
    """Переход к вводу ссылки"""
    await state.set_state(AddDeadlineStates.waiting_for_link)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ Пропустити (без посилання)", callback_data="skip_link")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_add_deadline")]
    ])
    
    await message.answer(
        "🔗 Вставте посилання на завдання:\n"
        "Можна відправити `https://...`\n\n"
        "Або натисніть 'Пропустити'.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "skip_link", AddDeadlineStates.waiting_for_link)
async def skip_link_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Пропуск ввода ссылки"""
    await callback_query.answer()
    await finalize_deadline(callback_query.message, state, None)


@dp.message(AddDeadlineStates.waiting_for_link)
async def process_deadline_link(message: types.Message, state: FSMContext):
    """Обработка ссылки"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Додавання дедлайну скасовано.", reply_markup=get_main_keyboard())
        return

    link = message.text.strip()
    # Простая проверка на URL
    if not link.startswith("http"):
        await message.answer("⚠️ Це не виглядає як посилання. Воно має починатися з http або https.\nСпробуйте ще раз або натисніть 'Пропустити'.")
        return

    await finalize_deadline(message, state, link)


async def finalize_deadline(message: types.Message, state: FSMContext, link: str):
    """Финализация и сохранение дедлайна"""
    data = await state.get_data()
    course_name = data.get('course_name')
    title = data.get('title')
    date_str = data.get('deadline_date')
    time_str = data.get('deadline_time')
    
    # Собираем полный datetime
    full_dt_str = f"{date_str} {time_str}"
    try:
        due_date = datetime.strptime(full_dt_str, "%d.%m.%Y %H:%M")
    except ValueError:
         await message.answer("❌ Помилка обробки дати. Спробуйте ще раз.")
         await state.clear()
         return

    # Сохраняем в базу данных
    # message может быть Message или отредактированное сообщение от callback
    # Поэтому берем ID аккуратно
    if isinstance(message, types.CallbackQuery): 
        # Этого не должно быть, так как сюда передаем именно message объект
        pass
        
    # В случае callback'а message это message объекта callback
    telegram_id = message.chat.id # chat.id надежнее в данном контексте

    db = get_db()
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        # Если юзер не найден, возможно он пишет впервые, но команда /start должна была создать
        # Но на всякий случай
        await message.answer("❌ Помилка: користувач не знайдений. Спробуйте /start")
        db.close()
        await state.clear()
        return

    # Создаем уникальный external_id для ручного дедлайна
    import time
    external_id = f"manual_{telegram_id}_{int(time.time())}"

    new_deadline = Deadline(
        user_id=user.id,
        course_name=course_name,
        title=title,
        due_date=due_date,
        link=link,
        external_id=external_id,
        notified=False
    )

    db.add(new_deadline)
    db.commit()
    db.close()

    await state.clear()

    # Проверяем, активный или просроченный
    now = datetime.utcnow()
    if due_date >= now:
        time_left = due_date - now
        days_left = time_left.days
        hours_left = time_left.seconds // 3600
        time_str = f"{days_left} д. {hours_left} год." if days_left > 0 else f"{hours_left} год."
        status_msg = f"⏳ Залишилось: {time_str}"
    else:
        status_msg = "⚠️ Увага: дедлайн вже прострочений!"

    display_link = f"\n🔗 <a href='{link}'>Посилання</a>" if link else ""

    await message.answer(
        f"✅ Дедлайн успішно додано!\n\n"
        f"📖 Предмет: {course_name}\n"
        f"📝 Завдання: {title}\n"
        f"⏰ Дедлайн: {due_date.strftime('%d.%m.%Y %H:%M')}"
        f"{display_link}\n"
        f"{status_msg}",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


async def main():
    init_db()
    print("🤖 Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
