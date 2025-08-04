from dotenv import load_dotenv
import os
import psycopg2
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

(FIO, ADDRESS, FIO_ROD1, FIO_ROD2, PHONE, DOC1, DOC2, DOC3) = range(8)

def get_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        dbname=os.getenv("PG_DATABASE")
    )

def create_table():
    with get_connection() as conn:
        with conn.cursor() as cur:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS zayavki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                fio TEXT,
                address TEXT,
                fio_rod1 TEXT,
                fio_rod2 TEXT,
                phone TEXT,
                doc1 TEXT,
                doc2 TEXT,
                doc3 TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def clean_old_data(days=3):
    with sqlite3.connect("zayavki.db") as conn:
        conn.execute(f"DELETE FROM zayavki WHERE timestamp < datetime('now', '-{days} days')")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ваше ФИО:")
    return FIO

async def get_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fio"] = update.message.text
    await update.message.reply_text("Введите адрес проживания:")
    return ADDRESS

async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text("Введите ФИО и номер телефона родственника 1:")
    return FIO_ROD1

async def get_fio_rod1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fio_rod1"] = update.message.text
    await update.message.reply_text("Введите ФИО и номер телефона родственника 2:")
    return FIO_ROD2

async def get_fio_rod2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fio_rod2"] = update.message.text
    await update.message.reply_text("Введите ваш номер телефона:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("Отправьте PDF: удостоверение личности")
    return DOC1

async def get_doc1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc and doc.mime_type == 'application/pdf':
        context.user_data["doc1"] = doc.file_id
        await update.message.reply_text("Теперь отправьте PDF: справка ПНД")
        return DOC2
    await update.message.reply_text("Пожалуйста, отправьте PDF-файл удостоверения личности.")
    return DOC1

async def get_doc2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc and doc.mime_type == 'application/pdf':
        context.user_data["doc2"] = doc.file_id
        await update.message.reply_text("Теперь отправьте PDF: справка НД")
        return DOC3
    await update.message.reply_text("Пожалуйста, отправьте PDF-файл справки ПНД.")
    return DOC2

async def get_doc3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc and doc.mime_type == 'application/pdf':
        context.user_data["doc3"] = doc.file_id
        clean_old_data()

        data = context.user_data
        user_id = update.message.from_user.id

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO zayavki (telegram_id, fio, address, fio_rod1, fio_rod2, phone, doc1, doc2, doc3)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    user_id, data['fio'], data['address'], data['fio_rod1'], data['fio_rod2'],
                    data['phone'], data['doc1'], data['doc2'], data['doc3']
            ))
        conn.commit()

        text = (
            f"Новая заявка:\n\n"
            f"ФИО: {data['fio']}\n"
            f"Адрес: {data['address']}\n"
            f"Родственник 1: {data['fio_rod1']}\n"
            f"Родственник 2: {data['fio_rod2']}\n"
            f"Телефон: {data['phone']}"
        )

        await context.bot.send_message(chat_id=ADMIN_ID, text=text)
        await context.bot.send_document(chat_id=ADMIN_ID, document=data['doc1'], caption="Удостоверение личности")
        await context.bot.send_document(chat_id=ADMIN_ID, document=data['doc2'], caption="Справка ПНД")
        await context.bot.send_document(chat_id=ADMIN_ID, document=data['doc3'], caption="Справка НД")

        await update.message.reply_text("✅ Все документы получены. Заявка отправлена.")
        return ConversationHandler.END

    await update.message.reply_text("Пожалуйста, отправьте PDF-файл справки НД.")
    return DOC3

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

def clean_old_data(days=1):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM zayavki WHERE timestamp < NOW() - INTERVAL '{days} days'")
        conn.commit()

if __name__ == '__main__':
    create_table()
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            FIO_ROD1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio_rod1)],
            FIO_ROD2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio_rod2)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            DOC1: [MessageHandler(filters.Document.PDF, get_doc1)],
            DOC2: [MessageHandler(filters.Document.PDF, get_doc2)],
            DOC3: [MessageHandler(filters.Document.PDF, get_doc3)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("✅ Бот запущен...")
    app.run_polling()
