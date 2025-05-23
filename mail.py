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

@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("Привет! Напиши /new чтобы добавить запись.")

@dp.message_handler(commands=['cancel', 'reset'], state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Диалог сброшен. Напиши /new, чтобы начать запись заново.")

@dp.message_handler(commands=['new'], state='*')
async def new_entry(message: types.Message, state: FSMContext):
    await state.finish()  # сброс перед новым вводом
    await Booking.date.set()
    await message.answer("Введите дату (например, 24.05.25):")

# Теперь обработчики по состояниям, строго по очереди:

@dp.message_handler(state=Booking.date)
async def get_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await Booking.next()
    await message.answer("Введите время (например, 18:00):")

@dp.message_handler(state=Booking.time)
async def get_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await Booking.next()
    await message.answer("Введите источник (например, мк или qh):")

@dp.message_handler(state=Booking.source)
async def get_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await Booking.next()
    await message.answer("Введите контакт (@ник или номер):")

@dp.message_handler(state=Booking.contact)
async def get_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await Booking.next()
    await message.answer("Введите количество человек:")

@dp.message_handler(state=Booking.count)
async def get_count(message: types.Message, state: FSMContext):
    await state.update_data(count=message.text)
    await Booking.next()
    await message.answer("Введите минимальный возраст:")

@dp.message_handler(state=Booking.age_min)
async def get_age_min(message: types.Message, state: FSMContext):
    await state.update_data(age_min=message.text)
    await Booking.next()
    await message.answer("Введите цену (в рублях):")

@dp.message_handler(state=Booking.price)
async def get_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await Booking.next()
    await message.answer("Дополнительная информация (если есть):")

@dp.message_handler(state=Booking.comment)
async def get_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    data = await state.get_data()

    # Сохраняем в CSV
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            data['date'], data['time'], data['source'], data['contact'],
            data['count'], data['age_min'], data['price'], data['comment']
        ])

    # Обновляем сообщение в канале
    await update_channel_message(data['date'])

    await message.answer("Запись добавлена!")
    await state.finish()

async def update_channel_message(date):
    entries = load_entries_for_date(date)
    text = render_day_message(date, entries)

    if date in messages:
        msg_id = messages[date]
        try:
            await bot.edit_message_text(text, chat_id=CHANNEL_ID, message_id=msg_id, parse_mode="HTML")
        except Exception as e:
            # Если редактирование не удалось (например, сообщение удалено), отправим новое
            sent = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
            messages[date] = sent.message_id
            save_messages()
    else:
        sent = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        messages[date] = sent.message_id
        save_messages()

def load_entries_for_date(date):
    entries = []
    if not os.path.exists(CSV_FILE):
        return entries
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            if row[0] == date:
                entries.append({
                    'date': row[0], 'time': row[1], 'source': row[2],
                    'contact': row[3], 'count': row[4], 'age_min': row[5],
                    'price': row[6], 'comment': row[7]
                })
    return entries

def render_day_message(date, entries):
    text = f"\u2728 <b>Записи на {date}</b>\n\n"
    separator = "\n" + "―" * 30 + "\n\n"
    for i, entry in enumerate(entries):
        text += (f"\u23F0 <b>{entry['time']}</b> — {entry['count']} чел, от {entry['age_min']} лет, {entry['price']}₽\n"
                 f"\u260E {entry['contact']} ({entry['source']})\n"
                 f"\u2709 {entry['comment'] or '—'}\n")
        if i != len(entries) - 1:
            text += separator
    return text

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
        entries = load_entries_for_date(today)
        if entries:
            text = render_day_message(today, entries)
        else:
            text = f"❌ На сегодня ({today}) записей нет."
        await message.answer(text, parse_mode="HTML")
    except FileNotFoundError:
        await message.answer("Файл с записями не найден.")

@dp.message_handler()
async def fallback(message: types.Message, state: FSMContext):
    # Если пользователь пишет что-то не по состоянию - даем подсказку
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Напиши /new, чтобы начать новую запись или /cancel для отмены.")
    else:
        # Если в состоянии - игнорируем или даем подсказку, чтобы не мешать
        await message.answer("Пожалуйста, следуй инструкциям. Для отмены напиши /cancel.")

if __name__ == '__main__':
    print("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
