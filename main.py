import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = "8909399982:AAHiM6SzDruzyX-mbcfPH5hyvFCZMplTXqI"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            serial_number INTEGER UNIQUE,
            group_number INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_text TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proofs (
            proof_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            proof_text TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class BotStates(StatesGroup):
    waiting_for_proof = State()
    waiting_for_new_task = State()

def get_or_create_user(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT serial_number, group_number FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row[0], row[1]
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    serial_number = count + 1
    group_number = ((serial_number - 1) // 10) + 1
    cursor.execute("INSERT INTO users (user_id, serial_number, group_number) VALUES (?, ?, ?)",
                   (user_id, serial_number, group_number))
    conn.commit()
    conn.close()
    return serial_number, group_number

def main_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 عرض المهمة الحالية", callback_data="show_task")],
        [InlineKeyboardButton(text="➕ إضافة مهمة جديدة", callback_data="add_task")]
    ])
    return kb

@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    serial, group = get_or_create_user(message.from_user.id)
    text = (
        f"أهلاً بك يا {message.from_user.first_name} في البوت! 👋\n\n"
        f"🆔 **رقمك التسلسلي:** `{serial}`\n"
        f"👥 **رقم مجموعتك:** `{group}`\n\n"
        "يمكنك الآن تنفيذ المهام المتاحة أو إضافة مهمتك الخاصة."
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.callback_query(F.data == "show_task")
async def show_task(callback: types.CallbackQuery):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT task_id, task_text FROM tasks ORDER BY task_id DESC LIMIT 1")
    task = cursor.fetchone()
    conn.close()
    if task:
        task_id, task_text = task
        text = f"🎯 **المهمة الحالية (رقم {task_id}):**\n\n{task_text}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ إرسال إثبات التنفيذ", callback_data=f"proof_{task_id}")],
            [InlineKeyboardButton(text="🔙 العودة للقائمة", callback_data="main_menu")]
        ])
    else:
        text = "لا توجد مهام متاحة حالياً. يمكنك إضافة أول مهمة!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إضافة مهمة", callback_data="add_task")],
            [InlineKeyboardButton(text="🔙 العودة للقائمة", callback_data="main_menu")]
        ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data.startswith("proof_"))
async def prepare_proof(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[1])
    await state.update_data(current_task_id=task_id)
    await state.set_state(BotStates.waiting_for_proof)
    await callback.message.answer("أرسل الآن الإثبات (رابط، نص، أو تفاصيل التنفيذ):")

@dp.message(BotStates.waiting_for_proof)
async def receive_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("current_task_id")
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO proofs (user_id, task_id, proof_text) VALUES (?, ?, ?)",
                   (message.from_user.id, task_id, message.text))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ تم حفظ الإثبات بنجاح! يمكنك الآن إضافة مهمتك الخاصة.", reply_markup=main_keyboard())

@dp.callback_query(F.data == "add_task")
async def prepare_add_task(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.waiting_for_new_task)
    await callback.message.answer("اكتب تفاصيل المهمة الجديدة التي تريد عرضها للمستخدمين:")

@dp.message(BotStates.waiting_for_new_task)
async def receive_new_task(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (user_id, task_text) VALUES (?, ?)",
                   (message.from_user.id, message.text))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("🚀 تم إضافة مهمتك بنجاح وتجهيزها للعرض باقي المشتركين!", reply_markup=main_keyboard())

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    serial, group = get_or_create_user(callback.from_user.id)
    text = (
        f"القائمة الرئيسية:\n\n"
        f"🆔 **رقمك التسلسلي:** `{serial}`\n"
        f"👥 **رقم مجموعتك:** `{group}`"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def main():
    print("البوت يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
