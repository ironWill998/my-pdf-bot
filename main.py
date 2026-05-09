import os
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Твои настройки
TOKEN = os.getenv("BOT_TOKEN")
# Вставь сюда свой числовой ID (можно узнать у @userinfobot)
ADMIN_ID = 1729842917
DB_NAME = "users_data.db"  # Твоя текущая база данных

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- КНОПКИ ---
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📖 Инструкция"))
    builder.add(KeyboardButton(text="📄 Мой лимит"))
    # Настройка расположения кнопок (в один ряд)
    return builder.as_markup(resize_keyboard=True)


# --- КОМАНДА /START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Добавляем пользователя в базу, если его там нет
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()

    # Текст с ссылкой на тебя (замени 'your_username' на свой ник)
    welcome_text = (
        "👋 Привет! Я помогу тебе превратить фото в PDF-файл.\n\n"
        "📸 Просто отправь мне до 3-х изображений.\n\n"
        "👨‍💻 **Разработчик:** @@Aboba228nagibator\n"
        "💼 **Заказать бота:** [Мой Kwork](https://kwork.ru/user/@Aboba228nagibator)"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


# --- АДМИН-КОМАНДА /ADMIN ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    # Проверка: является ли пользователь админом
    if message.from_user.id == ADMIN_ID:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                count = await cursor.fetchone()

        await message.answer(f"📊 **Статистика бота**\n\nВсего пользователей: {count[0]}", parse_mode="Markdown")
    else:
        # Если пишет не админ — просто игнорируем или отвечаем стандартно
        await message.answer("У вас нет прав для этой команды. ❌")


# --- ОБРАБОТКА КНОПКИ ИНСТРУКЦИЯ ---
@dp.message(F.text == "📖 Инструкция")
async def show_help(message: types.Message):
    await message.answer(
        "Всё просто:\n1. Отправь мне фото (как изображение, а не файл).\n"
        "2. Я накоплю их и предложу сделать PDF.\n"
        "3. Помни про лимит — не более 3-х фото за раз!"
    )


# Запуск бота (используется в твоем файле main.py)
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())