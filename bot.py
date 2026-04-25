import asyncio
import sqlite3
import os
import re
from urllib.parse import quote
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN:
    print("❌ BOT_TOKEN topilmadi!")
    exit()

if not WEBHOOK_URL:
    print("❌ WEBHOOK_URL topilmadi!")
    exit()

# Google Form sozlamalari
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSevHWSfY1ZMxq0FtMPTcgYUebSGwQl-fDWpiR6VNxmnfS7Kuw/viewform"
ENTRY_FULLNAME = "entry.2092238618"
ENTRY_BIRTH = "entry.696211298"
ENTRY_PHONE = "entry.368714458"
ENTRY_PROFESSION = "entry.479301265"
ENTRY_REGION = "entry.1283378214"
ENTRY_ORGANIZATION = "entry.1096850068"
ENTRY_DIPLOMA = "entry.943553587"
ENTRY_OTHER_ORG = "entry.807992286"

GROUP_INVITE_LINK = "https://t.me/+ooSj6Z1xRvg4ZTQ6"
SOCIAL_LINKS = """
📢 *Bizning ijtimoiy tarmoqlarimizga a'zo bo'ling!*

🔗 *Telegram:* https://t.me/worldskillstalim
📸 *Instagram:* https://www.instagram.com/worldskillsuzbekistan/
🎬 *YouTube:* https://www.youtube.com/@worldskillsuzbekistan3441
📘 *Facebook:* https://www.facebook.com/WorldskillsUzbekistan/
"""

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            birth_date TEXT,
            phone_number TEXT,
            region TEXT,
            profession TEXT,
            profession_en TEXT,
            organization TEXT,
            diploma_specialty TEXT,
            receipt_file_id TEXT,
            receipt_status TEXT DEFAULT 'pending',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ DB tayyor!")

def save_user(user_id, data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (
            user_id, first_name, last_name, birth_date, phone_number, region,
            profession, profession_en, organization, diploma_specialty,
            receipt_file_id, receipt_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data.get('name'), data.get('lastname'), data.get('birth_date'),
          data.get('phone'), data.get('region'), data.get('profession'),
          data.get('profession_en'), data.get('organization'),
          data.get('diploma_specialty', ''), data.get('file_id'), 'pending'))
    conn.commit()
    conn.close()

def update_status(user_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET receipt_status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def get_pending():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, last_name, phone_number, profession FROM users WHERE receipt_status = 'pending'")
    res = cursor.fetchall()
    conn.close()
    return res

def make_form_link(data):
    full_name = f"{data.get('lastname', '')} {data.get('name', '')}"
    prof = data.get('profession', '')
    if '. ' in prof:
        prof = prof.split('. ', 1)[-1]
    org = data.get('organization', '')
    params = {
        ENTRY_FULLNAME: full_name,
        ENTRY_BIRTH: data.get('birth_date', ''),
        ENTRY_PHONE: data.get('phone', ''),
        ENTRY_PROFESSION: prof,
        ENTRY_REGION: data.get('region', ''),
        ENTRY_ORGANIZATION: org,
        ENTRY_DIPLOMA: data.get('diploma_specialty', ''),
        ENTRY_OTHER_ORG: org,
    }
    p = "&".join([f"{k}={quote(str(v))}" for k, v in params.items() if v])
    return f"{GOOGLE_FORM_URL}?usp=pp_url&{p}"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
init_db()

PROFESSIONS_UZ = [
    "1. Elektromontaj",
    "2. Payvandlash",
    "3. Santexnika",
    "4. Quruq qurilish va suvoq ishlari",
    "5. Kompyuter grafikasi va dizayn",
    "6. Modalar texnologiyasi",
    "7. Avtomobillarga texnik xizmat ko'rsatish",
    "8. Sartaroshlik",
    "9. Tibbiy va ijtimoiy g'amxo'rlik",
    "10. Oshpazlik"
]

PROFESSIONS_EN = [
    "1. Electrical Installation",
    "2. Welding",
    "3. Plumbing",
    "4. Dry Construction and Plastering",
    "5. Computer Graphics and Design",
    "6. Fashion Technology",
    "7. Automotive Maintenance",
    "8. Hairdressing",
    "9. Medical and Social Care",
    "10. Culinary Arts"
]

REGIONS = [
    "Qoraqalpog'iston Respublikasi",
    "Andijon viloyati",
    "Buxoro viloyati",
    "Jizzax viloyati",
    "Qashqadaryo viloyati",
    "Navoiy viloyati",
    "Namangan viloyati",
    "Samarqand viloyati",
    "Sirdaryo viloyati",
    "Surxondaryo viloyati",
    "Toshkent viloyati",
    "Farg'ona viloyati",
    "Xorazm viloyati",
    "Toshkent shahri"
]

class Form(StatesGroup):
    name = State()
    lastname = State()
    birth_date = State()
    phone = State()
    region = State()
    language = State()
    profession = State()
    organization = State()
    diploma_specialty = State()
    receipt = State()

def phone_kb():
    btn = KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)
    return ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True)

def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def prof_kb(lang="uz"):
    proflar = PROFESSIONS_UZ if lang == "uz" else PROFESSIONS_EN
    keyboard = [[InlineKeyboardButton(text=p, callback_data=f"prof_{i}")] for i, p in enumerate(proflar)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def region_kb():
    keyboard = [[InlineKeyboardButton(text=r, callback_data=f"region_{i}")] for i, r in enumerate(REGIONS)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await msg.answer(
        "🏆 *WorldSkills Sertifikat Botiga xush kelibsiz!*\n\n"
        "Milliy Worldskills Ekspert-2026 dasturiga ro'yxatdan o'tish.\n\n"
        "✏️ *Ismingizni kiriting:*\n_(Masalan: Jahongir)_",
        parse_mode="Markdown"
    )
    await state.set_state(Form.name)

@dp.message(Form.name)
async def get_name(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 2:
        await msg.answer("❌ Ism 2 harfdan kam bo'lmasligi kerak. Qaytadan kiriting:")
        return
    await state.update_data(name=msg.text.strip())
    await msg.answer(
        "✏️ *Familiyangizni kiriting:*\n_(Masalan: Karimov)_",
        parse_mode="Markdown"
    )
    await state.set_state(Form.lastname)

@dp.message(Form.lastname)
async def get_lastname(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 2:
        await msg.answer("❌ Familiya 2 harfdan kam bo'lmasligi kerak. Qaytadan kiriting:")
        return
    await state.update_data(lastname=msg.text.strip())
    await msg.answer(
        "📅 *Tug'ilgan kuningizni kiriting:*\n_(Masalan: 22.01.1989)_",
        parse_mode="Markdown"
    )
    await state.set_state(Form.birth_date)

@dp.message(Form.birth_date)
async def get_birth(msg: types.Message, state: FSMContext):
    if not re.match(r'\d{2}\.\d{2}\.\d{4}', msg.text.strip()):
        await msg.answer("❌ Noto'g'ri format! Iltimos, 22.01.1989 ko'rinishida yozing.")
        return
    await state.update_data(birth_date=msg.text.strip())
    await msg.answer(
        "📱 *Telefon raqamingizni yuboring:*\n\n✅ Pastdagi tugmani bosing YOKI\n✏️ Qo'lda yozing (masalan: +998901234567)",
        parse_mode="Markdown",
        reply_markup=phone_kb()
    )
    await state.set_state(Form.phone)

@dp.message(Form.phone, F.contact)
async def get_phone_contact(msg: types.Message, state: FSMContext):
    await state.update_data(phone=msg.contact.phone_number)
    await msg.answer("📍 *Viloyatingizni tanlang:*", parse_mode="Markdown", reply_markup=region_kb())
    await state.set_state(Form.region)

@dp.message(Form.phone)
async def get_phone_manual(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    if len(phone) < 9 or not any(c.isdigit() for c in phone):
        await msg.answer("❌ Noto'g'ri telefon raqam! Qaytadan kiriting:")
        return
    if not phone.startswith('+'):
        phone = '+998' + phone[-9:] if len(phone) == 9 else phone
    await state.update_data(phone=phone)
    await msg.answer("📍 *Viloyatingizni tanlang:*", parse_mode="Markdown", reply_markup=region_kb())
    await state.set_state(Form.region)

@dp.callback_query(Form.region, F.data.startswith("region_"))
async def get_region(call: types.CallbackQuery, state: FSMContext):
    idx = int(call.data.split("_")[1])
    region = REGIONS[idx]
    await state.update_data(region=region)
    await call.message.delete()
    await call.message.answer(
        "🌐 *Tilni tanlang:*",
        parse_mode="Markdown",
        reply_markup=lang_kb()
    )
    await state.set_state(Form.language)
    await call.answer()

@dp.callback_query(Form.language, F.data.startswith("lang_"))
async def process_language(call: types.CallbackQuery, state: FSMContext):
    language = "uz" if call.data == "lang_uz" else "en"
    await state.update_data(language=language)
    text = "👨‍💼 *Kasbingizni tanlang:*" if language == "uz" else "👨‍💼 *Select your profession:*"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=prof_kb(language))
    await state.set_state(Form.profession)
    await call.answer()

@dp.callback_query(Form.profession, F.data.startswith("prof_"))
async def get_profession(call: types.CallbackQuery, state: FSMContext):
    idx = int(call.data.split("_")[1])
    user_data = await state.get_data()
    language = user_data.get("language", "uz")
    
    profession_uz = PROFESSIONS_UZ[idx]
    profession_en = PROFESSIONS_EN[idx]
    await state.update_data(profession=profession_uz, profession_en=profession_en)
    
    await call.message.delete()
    await call.message.answer(
        "🏢 *Ish joyingiz / Tashkilotingiz nomini yozing:*\n_(Masalan: Toshkent shahar 1-son maktab)_",
        parse_mode="Markdown"
    )
    await state.set_state(Form.organization)
    await call.answer()

@dp.message(Form.organization)
async def get_organization(msg: types.Message, state: FSMContext):
    await state.update_data(organization=msg.text.strip())
    await msg.answer(
        "📜 *Diplom bo'yicha mutaxassisligingiz (agar mavjud bo'lsa):*\n_(Bo'sh qoldirishingiz mumkin yoki '-' yozing)_",
        parse_mode="Markdown"
    )
    await state.set_state(Form.diploma_specialty)

@dp.message(Form.diploma_specialty)
async def get_diploma(msg: types.Message, state: FSMContext):
    diploma = msg.text.strip()
    if diploma == "-":
        diploma = ""
    await state.update_data(diploma_specialty=diploma)
    
    payment_text = """
💰 *Milliy Worldskills Ekspert-2026*

📚 *O'qish puli:* 1 000 000 so'm

🏢 *"ISHCHI KASBLARNI RIVOJLANTIRISH VA OMMALASHTIRISH AKADEMIYASI" MChJ*

🏦 *Bank rekvizitlari:*
• INN: 308344436
• Bank: AKB "Kapitalbank" Mirzo Ulug'bek tuman filiali
• MFO: 01018
• Hisob raqam: 20208000305369587001

📧 *Email:* dadaxon45@gmail.com
📞 *Telefon:* +998 93 340 40 80

📝 *To'lov maqsadi:* Ekspertlikka o'qish uchun

📄 *Shartnoma raqami:* 22011956 (Tug'ilgan kuningiz: kun.oy.yil)

📅 *Sana:* 22.04.2026

✅ *To'lovni amalga oshirgandan so'ng, kvitansiyani shu botga yuboring!*

🔐 *Kvitansiya tekshirilgandan so'ng siz yopiq guruhga qo'shilasiz.*
"""
    
    await msg.answer(payment_text, parse_mode="Markdown")
    await msg.answer("📎 *Kvitansiyangizni yuklang (rasm yoki PDF formatida):*", parse_mode="Markdown")
    await state.set_state(Form.receipt)

@dp.message(Form.receipt, F.photo | F.document)
async def get_receipt(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    
    save_user(msg.from_user.id, {
        "name": data.get('name'),
        "lastname": data.get('lastname'),
        "birth_date": data.get('birth_date'),
        "phone": data.get('phone'),
        "region": data.get('region'),
        "profession": data.get('profession'),
        "profession_en": data.get('profession_en'),
        "organization": data.get('organization', ''),
        "diploma_specialty": data.get('diploma_specialty', ''),
        "file_id": file_id
    })
    
    form_link = make_form_link(data)
    
    await msg.answer(
        f"✅ *Kvitansiyangiz qabul qilindi!*\n\n"
        f"📋 Iltimos, quyidagi havola orqali Google Formni to'ldiring:\n\n"
        f"🔗 [Google Formni to'ldirish]({form_link})\n\n"
        f"*Eslatma:* Ma'lumotlaringiz avtomatik to'ldirilgan. Faqat tekshirib \"Submit\" tugmasini bosing.\n\n"
        f"Admin tekshiruvidan so'ng sizga xabar beriladi.",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""
🆕 *YANGI ARIZA!*

👤 *Ism:* {data.get('name')} {data.get('lastname')}
📅 *Tug'ilgan kun:* {data.get('birth_date')}
📱 *Telefon:* {data.get('phone')}
📍 *Viloyat:* {data.get('region')}
👨‍💼 *Kasb:* {data.get('profession')}
🏢 *Tashkilot:* {data.get('organization', '-')}
📜 *Diplom:* {data.get('diploma_specialty', '-')}
🆔 *ID:* {msg.from_user.id}

📎 *Kvitansiya quyida:*
"""
            if msg.photo:
                await bot.send_photo(admin_id, photo=file_id, caption=admin_text, parse_mode="Markdown")
            else:
                await bot.send_document(admin_id, document=file_id, caption=admin_text, parse_mode="Markdown")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{msg.from_user.id}"),
                 InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{msg.from_user.id}")]
            ])
            await bot.send_message(admin_id, "📝 *Qaror qabul qiling:*", parse_mode="Markdown", reply_markup=keyboard)
            
        except Exception as e:
            print(f"❌ Admin xatosi: {e}")
    
    await state.clear()

@dp.message(Form.receipt)
async def invalid_receipt(msg: types.Message):
    await msg.answer("❌ Iltimos, kvitansiyani **rasm (photo)** yoki **PDF** formatida yuboring!", parse_mode="Markdown")

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    
    user_id = int(call.data.split("_")[1])
    update_status(user_id, "approved")
    
    await bot.send_message(
        user_id,
        f"✅ *Tabriklaymiz!* To'lovingiz tasdiqlandi.\n\n"
        f"🔐 *Yopiq guruhga qo'shilish havolasi:*\n{GROUP_INVITE_LINK}\n\n"
        f"{SOCIAL_LINKS}\n\n"
        f"Ekspertlik kurslari muvaffaqiyatli boshlanadi!",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await call.message.edit_text(f"✅ {user_id} ID li foydalanuvchi TASDIQLANDI!")
    await call.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    
    user_id = int(call.data.split("_")[1])
    update_status(user_id, "rejected")
    
    await bot.send_message(
        user_id,
        "❌ *Kechirasiz!* To'lovingiz tasdiqlanmadi.\n\n"
        "Iltimos, to'g'ri to'lov kvitansiyasini yuboring yoki qo'llab-quvvatlash xizmatiga murojaat qiling.\n\n"
        "📞 Telefon: +998 93 340 40 80",
        parse_mode="Markdown"
    )
    await call.message.edit_text(f"❌ {user_id} ID li foydalanuvchi RAD ETILDI!")
    await call.answer()

@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("❌ Siz admin emassiz!")
        return
    
    pending_users = get_pending()
    
    if not pending_users:
        await msg.answer("📭 *Kutilayotgan arizalar yo'q*", parse_mode="Markdown")
        return
    
    text = "📋 *Kutilayotgan arizalar:*\n\n"
    for user in pending_users:
        text += f"🆔 {user[0]} | {user[1]} {user[2]} | {user[3]}\n"
    
    await msg.answer(text, parse_mode="Markdown")

# ========== HEALTH CHECK ENDPOINT ==========
async def health_check(request):
    """Sog'likni tekshirish uchun endpoint - Render uchun majburiy"""
    return web.Response(text="OK", status=200)

# ========== WEBHOOK VA SERVER ==========
async def keep_webhook_alive():
    """Har 30 daqiqada webhook holatini tekshiradi va kerak bo'lsa qayta o'rnatadi"""
    while True:
        await asyncio.sleep(1800)  # 30 daqiqa
        try:
            webhook_info = await bot.get_webhook_info()
            if not webhook_info.url:
                await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
                print("⚠️ Webhook qayta o'rnatildi")
        except Exception as e:
            print(f"❌ Webhook tekshiruvida xato: {e}")

async def on_startup(app):
    webhook_full_url = f"{WEBHOOK_URL}/webhook"
    await bot.set_webhook(webhook_full_url)
    print(f"✅ Webhook sozlandi: {webhook_full_url}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()
    print("❌ Webhook tozalandi")

def main():
    app = web.Application()
    
    # 1. Health check endpoint (Render uchun)
    app.router.add_get("/health", health_check)
    
    # 2. Webhook handler
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    
    # 3. Asosiy sahifaga oddiy xabar
    async def index(request):
        return web.Response(text="Bot is running. Use /webhook for Telegram updates.", status=200)
    app.router.add_get("/", index)
    
    # 4. Webhook keep-alive vazifasini ishga tushiruvchi startup funksiyasi
    async def startup_with_keep_alive():
        await on_startup(app)
        asyncio.create_task(keep_webhook_alive())
        print("✅ Webhook keep-alive vazifasi ishga tushdi")
    
    # 5. Startup va shutdown eventlari
    app.on_startup.append(startup_with_keep_alive)
    app.on_shutdown.append(on_shutdown)
    
    # 6. Serverni ishga tushirish
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Server {port} portda ishga tushmoqda...")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()