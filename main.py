import os
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web  # Нужно для "обмана" Render

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1729842917
DB_NAME = "users_data.db"
PORT = int(os.environ.get("PORT", 8080))  # Порт, который требует Render

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- РАБОТА С БАЗОЙ ДАННЫХ ---
async def init_db():
    """Создает таблицу users, если её еще нет"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.commit()
        print("База данных готова к работе.")


# --- КНОПКИ ---
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📖 Инструкция"))
    builder.add(KeyboardButton(text="📄 Мой лимит"))
    return builder.as_markup(resize_keyboard=True)


# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()

    welcome_text = (
        "👋 Привет! Я помогу тебе превратить фото в PDF-файл.\n\n"
        "📸 Просто отправь мне до 3-х изображений.\n\n"
        "👨‍💻 **Разработчик:** @Aboba228nagibator\n"
        "💼 **Заказать бота:** [Мой Kwork](https://kwork.ru/user/@Aboba228nagibator)"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown",
                         disable_web_page_preview=True)


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                count = await cursor.fetchone()
        await message.answer(f"📊 **Статистика бота**\n\nВсего пользователей: {count[0]}", parse_mode="Markdown")
    else:
        await message.answer("У вас нет прав для этой команды. ❌")


@dp.message(F.text == "📖 Инструкция")
async def show_help(message: types.Message):
    await message.answer(
        "Всё просто:\n1. Отправь мне фото (как изображение, а не файл).\n"
        "2. Я накоплю их и предложу сделать PDF.\n"
        "3. Помни про лимит — не более 3-х фото за раз!"
    )


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Веб-сервер запущен на порту {PORT}")


# --- ЗАПУСК ---
async def main():
    # 1. Сначала инициализируем базу
    await init_db()

    # 2. Запускаем веб-сервер (чтобы Render не убил процесс)
    asyncio.create_task(start_web_server())

    # 3. Чистим очередь обновлений и запускаем бота
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")