import os
import asyncio
import aiosqlite
import img2pdf
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, LabeledPrice, PreCheckoutQuery
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# 1. Веб-сервер для Render
app = Flask('')


@app.route('/')
def home():
    return "Bot is running!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


# 2. Настройка бота
TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_PATH = "users_data.db"


# 3. Работа с Базой Данных
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, conversions INTEGER DEFAULT 0, is_premium BOOLEAN DEFAULT 0)
        ''')
        await db.commit()


async def get_user_status(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT conversions, is_premium FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row  # (conversions, is_premium)
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return (0, 0)


async def increment_conversions(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET conversions = conversions + 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def set_premium(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
        await db.commit()


# 4. Обработчики команд
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Привет! Я сделаю PDF из твоих фото.\nБесплатно: 3 фото. Далее — подписка за Звёзды ⭐")


# 5. Обработка ОПЛАТЫ (Звёзды)
@dp.message(Command("buy"))
async def buy_premium(message: types.Message):
    await message.answer_invoice(
        title="Безлимитный PDF",
        description="Открывает бесконечную конвертацию фото!",
        payload="premium_sub",
        currency="XTR",  # Код валюты для Telegram Stars
        prices=[LabeledPrice(label="Купить доступ", amount=50)],  # 50 звезд
    )


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    await set_premium(message.from_user.id)
    await message.answer("Ура! Теперь у вас безлимитный доступ! 🎉")


# 6. Основная логика: Фото -> PDF
@dp.message(F.photo)
async def photo_to_pdf(message: types.Message):
    user_id = message.from_user.id
    conversions, is_premium = await get_user_status(user_id)

    # Проверка лимита
    if not is_premium and conversions >= 3:
        await message.answer("Бесплатные попытки кончились. Купите доступ: /buy")
        return

    if not os.path.exists("temp"):
        os.makedirs("temp")

    msg = await message.answer("⏳ Обрабатываю...")
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)

    img_path = f"temp/{file_id}.jpg"
    pdf_path = f"temp/{file_id}.pdf"

    await bot.download_file(file.file_path, img_path)

    try:
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(img_path))

        await message.answer_document(FSInputFile(pdf_path))
        await increment_conversions(user_id)
        await msg.delete()
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        if os.path.exists(img_path): os.remove(img_path)
        if os.path.exists(pdf_path): os.remove(pdf_path)


# 7. Запуск
async def main():
    if not os.path.exists("temp"):
        os.makedirs("temp")

    await init_db()
    keep_alive()

    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")