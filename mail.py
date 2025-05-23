import csv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

CSV_FILE = "data.csv"

class Booking(StatesGroup):
    date = State()
    time = State()
    source = State()
    contact = State()
    count = State()
    age_min = State()
    price = State()
    comment = State()


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Привет! Напиши /new чтобы добавить запись.")


@dp.message_handler(commands=['new'])
async def new_entry(message: types.Message):
    await message.answer("Введите дату (например, 24.05.25):")
    await Booking.date.set()


@dp.message_handler(state=Booking.date)
async def get_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Введите время (например, 18:00):")
    await Booking.next()


@dp.message_handler(state=Booking.time)
async def get_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Введите источник (например, мк или qh):")
    await Booking.next()


@dp.message_handler(state=Booking.source)
async def get_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await message.answer("Введите контакт (@ник или номер):")
    await Booking.next()


@dp.message_handler(state=Booking.contact)
async def get_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Введите количество человек:")
    await Booking.next()


@dp.message_handler(state=Booking.count)
async def get_count(message: types.Message, state: FSMContext):
    await state.update_data(count=message.text)
    await message.answer("Введите минимальный возраст:")
    await Booking.next()


@dp.message_handler(state=Booking.age_min)
async def get_age_min(message: types.Message, state: FSMContext):
    await state.update_data(age_min=message.text)
    await message.answer("Введите цену (в рублях):")
    await Booking.next()


@dp.message_handler(state=Booking.price)
async def get_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Дополнительная информация (если есть):")
    await Booking.next()


@dp.message_handler(state=Booking.comment)
async def get_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    data = await state.get_data()

    # Сообщение в канал (старый формат — оставляем для истории/логов)
    text = (f"{data['date']}, {data['time']} ({data['source']}): {data['contact']}\n"
            f"{data['count']} чел, от {data['age_min']} лет, {data['price']}₽\n"
            f"{data['comment']}")
    await bot.send_message(CHANNEL_ID, text)

    # Красиво оформленное сообщение
    pretty = (
        f"📅 <b>Дата</b>: {data['date']}\n"
        f"⏰ <b>Время</b>: {data['time']}\n"
        f"👥 <b>Кол-во</b>: {data['count']} человек (от {data['age_min']} лет)\n"
        f"💸 <b>Цена</b>: {data['price']}₽\n"
        f"📲 <b>Контакт</b>: {data['contact']}\n"
        f"🧭 <b>Источник</b>: {data['source']}\n"
        f"💬 <b>Комментарий</b>: {data['comment'] or '—'}"
    )
    await bot.send_message(CHANNEL_ID, pretty, parse_mode="HTML")

    # Сохранение в CSV
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            data['date'], data['time'], data['source'], data['contact'],
            data['count'], data['age_min'], data['price'], data['comment']
        ])

    await message.answer("Запись добавлена!")
    await state.finish()

@dp.message_handler(commands=['csv'])
async def send_csv(message: types.Message):
    try:
        await bot.send_document(message.chat.id, types.InputFile(CSV_FILE))
    except FileNotFoundError:
        await message.answer("Файл пока не создан.")

@dp.message_handler(commands=['today'])
async def send_today_entries(message: types.Message):
    try:
        today = datetime.today().strftime("%d.%m.%y")
        entries = []

        with open(CSV_FILE, 'r', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0] == today:  # row[0] — дата
                    entry = (f"🕓 {row[1]} — {row[4]} чел, от {row[5]} лет, {row[6]}₽\n"
                             f"📲 {row[3]} ({row[2]})\n"
                             f"💬 {row[7]}\n")
                    entries.append(entry)

        if entries:
            result = f"📅 Записи на сегодня ({today}):\n\n" + "\n".join(entries)
        else:
            result = f"❌ На сегодня ({today}) записей нет."

        await message.answer(result)
    except FileNotFoundError:
        await message.answer("Файл с записями не найден.")

if __name__ == '__main__':
    print("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
