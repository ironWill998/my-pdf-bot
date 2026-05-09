import os
import asyncio
import aiosqlite
import img2pdf

from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    KeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# =========================================================
# НАСТРОЙКИ
# =========================================================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1729842917  # Твой Telegram ID
DB_NAME = "users_data.db"
PORT = int(os.environ.get("PORT", 8080))

FREE_LIMIT = 3          # Бесплатных конвертаций
PRICE_STARS = 50        # Стоимость подписки в Telegram Stars

TEMP_DIR = "temp"

if not TOKEN:
    raise ValueError("Не найдена переменная окружения BOT_TOKEN")


# =========================================================
# ИНИЦИАЛИЗАЦИЯ БОТА
# =========================================================
bot = Bot(token=TOKEN)
dp = Dispatcher()


# =========================================================
# БАЗА ДАННЫХ
# =========================================================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                conversions INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0
            )
        """)
        await db.commit()
        print("База данных готова.")


async def ensure_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()


async def get_user_data(user_id: int):
    await ensure_user(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT conversions, is_premium FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row  # (conversions, is_premium)


async def increment_conversions(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET conversions = conversions + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def set_premium(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET is_premium = 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def get_users_count():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0]


# =========================================================
# КЛАВИАТУРЫ
# =========================================================
def get_main_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()

    builder.add(KeyboardButton(text="📖 Инструкция"))
    builder.add(KeyboardButton(text="📄 Мой лимит"))

    if user_id == ADMIN_ID:
        builder.add(KeyboardButton(text="👑 Админ-панель"))

    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# =========================================================
# КОМАНДЫ
# =========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await ensure_user(message.from_user.id)

    text = (
        "Привет! Я сделаю PDF из твоих фото.\n"
        "Бесплатно: 3 фото. Далее — подписка за Звёзды ⭐"
    )

    await message.answer(
        text,
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@dp.message(Command("buy"))
async def cmd_buy(message: types.Message):
    await message.answer_invoice(
        title="Безлимитный PDF",
        description="Открывает бесконечную конвертацию фото!",
        payload="premium_sub",
        currency="XTR",  # Telegram Stars
        prices=[
            LabeledPrice(
                label="Заплатить 50 звёзд",
                amount=PRICE_STARS
            )
        ]
    )


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    await set_premium(message.from_user.id)
    await message.answer(
        "Ура! Теперь у вас безлимитный доступ! 🎉"
    )


# =========================================================
# КНОПКИ
# =========================================================
@dp.message(F.text == "📖 Инструкция")
async def show_help(message: types.Message):
    await message.answer(
        "1. Отправь фотографию.\n"
        "2. Бот преобразует её в PDF.\n"
        "3. Бесплатно доступно 3 конвертации.\n"
        "4. После лимита можно купить безлимит за 50 ⭐."
    )


@dp.message(F.text == "📄 Мой лимит")
async def show_limit(message: types.Message):
    conversions, is_premium = await get_user_data(message.from_user.id)

    if is_premium:
        await message.answer("🌟 У вас безлимитный доступ.")
        return

    remaining = max(0, FREE_LIMIT - conversions)

    await message.answer(
        f"📄 Осталось бесплатных конвертаций: {remaining} из {FREE_LIMIT}."
    )


@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    count = await get_users_count()

    await message.answer(
        f"📊 Статистика бота\n\n"
        f"Всего пользователей: {count}"
    )


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав.")
        return

    count = await get_users_count()

    await message.answer(
        f"📊 Статистика бота\n\n"
        f"Всего пользователей: {count}"
    )


# =========================================================
# ОБРАБОТКА ФОТО → PDF
# =========================================================
@dp.message(F.photo)
async def photo_to_pdf(message: types.Message):
    user_id = message.from_user.id
    conversions, is_premium = await get_user_data(user_id)

    # Проверка лимита
    if not is_premium and conversions >= FREE_LIMIT:
        await message.answer(
            "Бесплатные попытки кончились. Купите доступ: /buy"
        )
        return

    # Создаём временную папку
    os.makedirs(TEMP_DIR, exist_ok=True)

    status_msg = await message.answer("⏳ Обрабатываю...")

    # Берём фото максимального размера
    file_id = message.photo[-1].file_id
    tg_file = await bot.get_file(file_id)

    img_path = os.path.join(TEMP_DIR, f"{file_id}.jpg")
    pdf_path = os.path.join(TEMP_DIR, f"{file_id}.pdf")

    try:
        # Скачиваем изображение
        await bot.download_file(tg_file.file_path, img_path)

        # Конвертируем в PDF
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(img_path))

        # Отправляем PDF
        await message.answer_document(
            FSInputFile(pdf_path),
            caption="✅ Готово!"
        )

        # Увеличиваем счётчик только для бесплатных пользователей
        if not is_premium:
            await increment_conversions(user_id)

        # Удаляем сообщение "Обрабатываю..."
        await status_msg.delete()

    except Exception as e:
        await message.answer(f"Ошибка: {e}")

    finally:
        # Удаляем временные файлы
        if os.path.exists(img_path):
            os.remove(img_path)

        if os.path.exists(pdf_path):
            os.remove(pdf_path)


# =========================================================
# ВЕБ-СЕРВЕР ДЛЯ RENDER
# =========================================================
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


# =========================================================
# ЗАПУСК
# =========================================================
async def main():
    # Создаём папку temp
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Инициализируем БД
    await init_db()

    # Запускаем веб-сервер для Render
    asyncio.create_task(start_web_server())

    # Удаляем старые обновления и запускаем бота
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")