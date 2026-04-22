import asyncio
import sqlite3
import os
import re
from datetime import datetime
from urllib.parse import quote
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

if not TOKEN:
    print("❌ .env faylida BOT_TOKEN topilmadi!")
    exit()

# ==================== GOOGLE FORM SOZLAMALARI ====================
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSevHWSfY1ZMxq0FtMPTcgYUebSGwQl-fDWpiR6VNxmnfS7Kuw/viewform"

# Entry ID lar
ENTRY_FULLNAME = "entry.2092238618"  # Familiyasi Ismi Sharifingiz
ENTRY_BIRTH = "entry.696211298"  # Tug'ilgan kuni
ENTRY_PHONE = "entry.368714458"  # Tel raqami
ENTRY_PROFESSION = "entry.479301265"  # Kasb nomi
ENTRY_REGION = "entry.1283378214"  # Viloyat
ENTRY_ORGANIZATION = "entry.1096850068"  # Faoliyat ko'rsatayotgan tashkilotingiz
ENTRY_DIPLOMA = "entry.943553587"  # Diplom bo'yicha mutaxassisligingiz
ENTRY_OTHER_ORG = "entry.807992286"  # Tashkilot nomi
# ================================================================

# Guruh va ijtimoiy tarmoqlar havolalari
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
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS users
                   (
                       user_id
                       INTEGER
                       PRIMARY
                       KEY,
                       first_name
                       TEXT,
                       last_name
                       TEXT,
                       birth_date
                       TEXT,
                       phone_number
                       TEXT,
                       region
                       TEXT,
                       profession
                       TEXT,
                       profession_en
                       TEXT,
                       organization
                       TEXT,
                       diploma_specialty
                       TEXT,
                       receipt_file_id
                       TEXT,
                       receipt_status
                       TEXT
                       DEFAULT
                       'pending',
                       registered_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')
    conn.commit()
    conn.close()
    print("✅ Ma'lumotlar bazasi tayyor!")


def save_user(user_id, data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (
            user_id, first_name, last_name, birth_date, phone_number, region,
            profession, profession_en, organization, diploma_specialty,
            receipt_file_id, receipt_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id,
          data.get('name'),
          data.get('lastname'),
          data.get('birth_date'),
          data.get('phone'),
          data.get('region'),
          data.get('profession'),
          data.get('profession_en'),
          data.get('organization'),
          data.get('diploma_specialty', ''),
          data.get('file_id'),
          'pending'))
    conn.commit()
    conn.close()


def update_receipt_status(user_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET receipt_status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()


def get_pending_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, first_name, last_name, phone_number, profession FROM users WHERE receipt_status = 'pending'")
    results = cursor.fetchall()
    conn.close()
    return results


def make_prefilled_form_link(user_data):
    """Google Form uchun prefilled link yaratish"""

    # To'liq ism
    full_name = f"{user_data.get('lastname', '')} {user_data.get('name', '')}"

    # Kasbni tozalash (raqam va nuqtani olib tashlash)
    profession = user_data.get('profession', '')
    if '. ' in profession:
        profession = profession.split('. ', 1)[-1]

    # Tashkilot (texnikum o'rniga foydalanuvchi yozgan tashkilot)
    organization = user_data.get('organization', '')

    params = {
        ENTRY_FULLNAME: full_name,
        ENTRY_BIRTH: user_data.get('birth_date', ''),
        ENTRY_PHONE: user_data.get('phone', ''),
        ENTRY_PROFESSION: profession,
        ENTRY_REGION: user_data.get('region', ''),
        ENTRY_ORGANIZATION: organization,
        ENTRY_DIPLOMA: user_data.get('diploma_specialty', ''),
        ENTRY_OTHER_ORG: organization,
    }

    # URL qurish
    param_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items() if v])

    return f"{GOOGLE_FORM_URL}?usp=pp_url&{param_string}"


bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
init_db()

# Kasblar
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
    organization = State()  # Texnikum o'rniga tashkilot
    diploma_specialty = State()
    receipt = State()


def get_phone_keyboard():
    btn = KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)
    return ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True)


def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])


def get_profession_keyboard(language="uz"):
    professions = PROFESSIONS_UZ if language == "uz" else PROFESSIONS_EN
    keyboard = [[InlineKeyboardButton(text=prof, callback_data=f"prof_{i}")] for i, prof in enumerate(professions)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_region_keyboard():
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
        await msg.answer("❌ Ism 2 harfdan kam bo'lmasligi kerak. Qaytadan kiriting:", parse_mode="Markdown")
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
        await msg.answer("❌ Familiya 2 harfdan kam bo'lmasligi kerak. Qaytadan kiriting:", parse_mode="Markdown")
        return
    await state.update_data(lastname=msg.text.strip())
    await msg.answer(
        "📅 *Tug'ilgan kuningizni kiriting:*\n_(Masalan: 22.01.1989)_",
        parse_mode="Markdown"
    )
    await state.set_state(Form.birth_date)


@dp.message(Form.birth_date)
async def get_birth_date(msg: types.Message, state: FSMContext):
    if not re.match(r'\d{2}\.\d{2}\.\d{4}', msg.text.strip()):
        await msg.answer("❌ Noto'g'ri format! Iltimos, 22.01.1989 ko'rinishida yozing.")
        return
    await state.update_data(birth_date=msg.text.strip())
    await msg.answer(
        "📱 *Telefon raqamingizni yuboring:*\n\n✅ Pastdagi tugmani bosing YOKI\n✏️ Qo'lda yozing (masalan: +998901234567)",
        parse_mode="Markdown",
        reply_markup=get_phone_keyboard()
    )
    await state.set_state(Form.phone)


@dp.message(Form.phone, F.contact)
async def get_phone_contact(msg: types.Message, state: FSMContext):
    await state.update_data(phone=msg.contact.phone_number)
    await msg.answer("📍 *Viloyatingizni tanlang:*", parse_mode="Markdown", reply_markup=get_region_keyboard())
    await state.set_state(Form.region)


@dp.message(Form.phone)
async def get_phone_manual(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    if len(phone) < 9 or not any(c.isdigit() for c in phone):
        await msg.answer("❌ Noto'g'ri telefon raqam! Qaytadan kiriting:", parse_mode="Markdown")
        return
    if not phone.startswith('+'):
        phone = '+998' + phone[-9:] if len(phone) == 9 else phone
    await state.update_data(phone=phone)
    await msg.answer("📍 *Viloyatingizni tanlang:*", parse_mode="Markdown", reply_markup=get_region_keyboard())
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
        reply_markup=get_language_keyboard()
    )
    await state.set_state(Form.language)
    await call.answer()


@dp.callback_query(Form.language, F.data.startswith("lang_"))
async def process_language(call: types.CallbackQuery, state: FSMContext):
    language = "uz" if call.data == "lang_uz" else "en"
    await state.update_data(language=language)
    text = "👨‍💼 *Kasbingizni tanlang:*" if language == "uz" else "👨‍💼 *Select your profession:*"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=get_profession_keyboard(language))
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
        "🏢 *Ish joyingiz / Tashkilotingiz nomini yozing:*\n_(Masalan: Toshkent shahar 1-son maktab yoki Yuq)_",
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
📞 *Telefon:* +998 93 340 40 numara

📝 *To'lov maqsadi:* Ekspertlikka o'qish uchun

📄 *Shartnoma raqami:* 22011956 (Tug'ilgan kuningiz: kun.oy.yil)

📅 *Sana:* 22.04.2026

✅ *To'lovni amalga oshirgandan so'ng, kvitansiyani shu botga yuboring!*

🔐 *Kvitansiya tekshirilgandan so'ng siz yopiq guruhga qo'shilasiz.*
    """

    await msg.answer(payment_text, parse_mode="Markdown")
    await msg.answer("📎 *Kvitansiyangizni yuklang (PDF yoki rasm formatida):*", parse_mode="Markdown")
    await state.set_state(Form.receipt)


@dp.message(Form.receipt, F.photo | F.document)
async def get_receipt(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id

    # Foydalanuvchini saqlash
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

    # Google Form prefilled link yaratish
    form_link = make_prefilled_form_link(data)

    await msg.answer(
        f"✅ *Kvitansiyangiz qabul qilindi!*\n\n"
        f"📋 Iltimos, quyidagi havola orqali Google Formni to'ldiring:\n\n"
        f"🔗 [Google Formni to'ldirish]({form_link})\n\n"
        f"*Eslatma:* Ma'lumotlaringiz avtomatik to'ldirilgan. Faqat tekshirib \"Submit\" tugmasini bosing.\n\n"
        f"Admin tekshiruvidan so'ng sizga xabar beriladi.",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    # ADMINLARGA XABAR (KVITANSIYA BILAN)
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
🆔 *User ID:* {msg.from_user.id}

📎 *Kvitansiya quyida:*
            """
            if msg.photo:
                await bot.send_photo(admin_id, photo=file_id, caption=admin_text, parse_mode="Markdown")
            else:
                await bot.send_document(admin_id, document=file_id, caption=admin_text, parse_mode="Markdown")

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{msg.from_user.id}")],
                [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{msg.from_user.id}")]
            ])
            await bot.send_message(admin_id, "📝 *Qaror qabul qiling:*", parse_mode="Markdown", reply_markup=keyboard)

        except Exception as e:
            print(f"❌ Admin {admin_id} ga xabar yuborishda xato: {e}")

    await state.clear()


@dp.message(Form.receipt)
async def invalid_receipt(msg: types.Message):
    await msg.answer("❌ Iltimos, kvitansiyani **rasm (photo)** yoki **PDF** formatida yuboring!", parse_mode="Markdown")


# ADMIN FUNKSIYALARI
@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    user_id = int(call.data.split("_")[1])
    update_receipt_status(user_id, "approved")

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
    update_receipt_status(user_id, "rejected")

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

    pending_users = get_pending_users()

    if not pending_users:
        await msg.answer("📭 *Kutilayotgan arizalar yo'q*", parse_mode="Markdown")
        return

    text = "📋 *Kutilayotgan arizalar:*\n\n"
    for user in pending_users:
        text += f"🆔 {user[0]} | {user[1]} {user[2]} | {user[3]}\n"

    await msg.answer(text, parse_mode="Markdown")


async def main():
    print("🚀 Bot ishga tushdi...")
    print(f"👑 Admin ID: {ADMIN_IDS}")
    print(f"🔗 Google Form ulandi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())