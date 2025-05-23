import csv
import json
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
MSG_FILE = "messages.json"

# Загрузка message_id сообщений для дат
if os.path.exists(MSG_FILE):
    with open(MSG_FILE, "r") as f:
        messages = json.load(f)
else:
    messages = {}

def save_messages():
    with open(MSG_FILE, "w") as f:
        json.dump(messages, f)

class Booking(StatesGroup):
    date = State()
    time = State()
    source = State()
    contact = State()
    count = State()
    age_min = State()
    price = State()
    comment = State()

# Общая функция для сброса состояния и уведомления
async def reset_dialog(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Диалог сброшен. Напиши /new, чтобы начать запись заново.")

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("Привет! Напиши /new чтобы добавить запись.")

@dp.message_handler(commands=['new'])
async def cmd_new(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Введите дату (например, 24.05.25):")
    await Booking.date.set()

@dp.message_handler(commands=['cancel', 'reset'], state='*')
async def cmd_cancel_reset(message: types.Message, state: FSMContext):
    await reset_dialog(message, state)

@dp.message_handler(state=Booking.date)
async def process_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Введите время (например, 18:00):")
    await Booking.next()

@dp.message_handler(state=Booking.time)
async def process_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Введите источник (например, мк или qh):")
    await Booking.next()

@dp.message_handler(state=Booking.source)
async def process_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await message.answer("Введите контакт (@ник или номер):")
    await Booking.next()

@dp.message_handler(state=Booking.contact)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Введите количество человек:")
    await Booking.next()

@dp.message_handler(state=Booking.count)
async def process_count(message: types.Message, state: FSMContext):
    await state.update_data(count=message.text)
    await message.answer("Введите минимальный возраст:")
    await Booking.next()

@dp.message_handler(state=Booking.age_min)
async def process_age_min(message: types.Message, state: FSMContext):
    await state.update_data(age_min=message.text)
    await message.answer("Введите цену (в рублях):")
    await Booking.next()

@dp.message_handler(state=Booking.price)
async def process_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Дополнительная информация (если есть):")
    await Booking.next()

@dp.message_handler(state=Booking.comment)
async def process_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    data = await state.get_data()

    # Сохраняем в CSV
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            data['date'], data['time'], data['source'], data['contact'],
            data['count'], data['age_min'], data['price'], data['comment']
        ])

    # Обновляем или создаём сообщение в канале
    await update_channel_message(data['date'])

    await message.answer("Запись добавлена!")
    await state.finish()

async def update_channel_message(date: str):
    entries = load_entries_for_date(date)
    text = render_day_message(date, entries)

    if date in messages:
        try:
            msg_id = messages[date]
            await bot.edit_message_text(text, chat_id=CHANNEL_ID, message_id=msg_id, parse_mode="HTML")
        except Exception as e:
            # Если не получилось отредактировать (например, сообщение удалено), отправим новое
            sent = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            messages[date] = sent.message_id
            save_messages()
    else:
        sent = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        messages[date] = sent.message_id
        save_messages()

def load_entries_for_date(date: str):
    entries = []
    if not os.path.exists(CSV_FILE):
        return entries
    with open(CSV_FILE, 'r', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 8 and row[0] == date:
                entries.append({
                    'date': row[0], 'time': row[1], 'source': row[2],
                    'contact': row[3], 'count': row[4], 'age_min': row[5],
                    'price': row[6], 'comment': row[7]
                })
    return entries

def render_day_message(date: str, entries: list):
    text = f"✨ <b>Записи на {date}</b>\n\n"
    for entry in entries:
        text += (
            f"⏰ <b>{entry['time']}</b> — {entry['count']} чел, от {entry['age_min']} лет, {entry['price']}₽\n"
            f"☎ {entry['contact']} ({entry['source']})\n"
            f"✉ {entry['comment'] or '—'}\n\n"
        )
    return text

@dp.message_handler(commands=['csv'])
async def send_csv(message: types.Message):
    try:
        await bot.send_document(message.chat.id, types.InputFile(CSV_FILE))
    except FileNotFoundError:
        await message.answer("Файл пока не создан.")

@dp.message_handler(commands=['today'])
async def send_today_entries(message: types.Message):
    today = datetime.today().strftime("%d.%m.%y")
    entries = load_entries_for_date(today)
    if entries:
        text = render_day_message(today, entries)
    else:
        text = f"❌ На сегодня ({today}) записей нет."
    await message.answer(text, parse_mode="HTML")

if __name__ == '__main__':
    print("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
