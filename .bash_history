        report_id = c.lastrowid
        conn.commit()
        conn.close()

        admin_text = (
            f"📥 **NEW SCAM REPORT AUDIT (ID: #{report_id})**\n\n"
            f"👤 **Scammer:**\n{s_info}\n\n"
            f"📝 **Details:**\n{desc}"
        )
        admin_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"app_{report_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"rej_{report_id}")
            ]
        ])

        for pid in context.user_data['photos']:
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=pid)
            
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode="Markdown",
            reply_markup=admin_keyboard
        )

        await query.edit_message_text("✅ သင့်တိုင်ကြားချက်အား Admin အဖွဲ့ထံ စစ်ဆေးရန် ပို့ဆောင်ပြီးပါပြီ။")
    else:
        await query.edit_message_text("❌ တိုင်ကြားချက်ကို ပယ်ဖျက်လိုက်ပါပြီ။")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ တိုင်ကြားမှု လုပ်ငန်းစဉ် မပြီးဆုံးသေးဘဲ ရပ်တန့်လိုက်ပါပြီ။")
    return ConversationHandler.END

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("app_") or data.startswith("rej_"):
        action, r_id = data.split("_")
        conn = sqlite3.connect('reports.db')
        c = conn.cursor()
        c.execute("SELECT scammer_info, description, photos FROM reports WHERE id=?", (r_id,))
        row = c.fetchone()

        if not row:
            await query.message.reply_text("❌ Report အချက်အလက် ရှာမတွေ့ပါ။")
            conn.close()
            return

        s_info, desc, photos_str = row

        if action == "app":
            c.execute("UPDATE reports SET status='APPROVED' WHERE id=?", (r_id,))
            conn.commit()

            public_text = (
                f"🚨 **CONFIRMED SCAM ALERT (Report #{r_id})** 🚨\n\n"
                f"👤 **လိမ်လည်သူ အချက်အလက်:**\n{s_info}\n\n"
                f"📝 **ဖြစ်စဉ် အသေးစိတ်:**\n{desc}\n\n"
                "⚠️ *Verified by Anonymous Cyber Police*"
            )
            
            photos_list = photos_str.split(",")
            for pid in photos_list:
                await context.bot.send_photo(chat_id=PUBLIC_GROUP_ID, photo=pid)
                
            await context.bot.send_message(chat_id=PUBLIC_GROUP_ID, text=public_text, parse_mode="Markdown")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ Report #{r_id} ကို Approve လုပ်လိုက်ပါပြီ။ Auto-Tracking စနစ်မှ ထို Scammer Account အား အမြဲမပြတ် စစ်ဆေးပေးသွားမည် ဖြစ်သည်။")

        elif action == "rej":
            c.execute("UPDATE reports SET status='REJECTED' WHERE id=?", (r_id,))
            conn.commit()
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"❌ Report #{r_id} ကို ပယ်ဖျက်လိုက်ပါပြီ။")

        conn.close()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('report', start_report)],
        states={
            SCAMMER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_scammer_info)],
            INCIDENT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            EVIDENCE_PHOTOS: [MessageHandler(filters.PHOTO | filters.TEXT, get_photos)],
            CONFIRMATION: [CallbackQueryHandler(handle_confirmation)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # Background Auto-Checker (၁ နာရီတစ်ကြိမ် အလိုအလျောက် စစ်ပေးမည်)
    if app.job_queue:
        app.job_queue.run_repeating(auto_check_scammers, interval=3600, first=10)

    print("ACP Bot is running with Auto Scammer Tracker...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
EOF

nohup python main.py > bot.log 2>&1 &
pkill -f main.py
cat << 'EOF' > main.py
import logging
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    filters
)

# Configuration
BOT_TOKEN = "8940490090:AAE6T-YVCjPNs7Yp9RfEazAqrC2E9ONC-d4"
ADMIN_CHAT_ID = -1005270771505
PUBLIC_GROUP_ID = -1004349678696

# Conversation States
SCAMMER_INFO, INCIDENT_DESC, EVIDENCE_PHOTOS, CONFIRMATION = range(4)

logging.basicConfig(level=logging.INFO)

# Database Setup
def init_db():
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  scammer_info TEXT, 
                  description TEXT, 
                  photos TEXT, 
                  status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Auto-Check Background Task (၁ နာရီတစ်ကြိမ် Scammer ၏ Status ကို စစ်ပေးမည်)
async def auto_check_scammers(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    c.execute("SELECT id, scammer_info FROM reports WHERE status='APPROVED'")
    approved_reports = c.fetchall()

    for report_id, s_info in approved_reports:
        try:
            words = s_info.split()
            target = None
            for w in words:
                if w.startswith("@") or w.isdigit():
                    target = w
                    break

            if target:
                try:
                    chat = await context.bot.get_chat(target)
                    if chat.first_name is None or "Deleted Account" in str(chat.first_name):
                        c.execute("UPDATE reports SET status='BANNED' WHERE id=?", (report_id,))
                        conn.commit()

                        ban_alert = (
                            f"🔥 <b>SCAMMER ACCOUNT TERMINATED!</b>\n\n"
                            f"📋 <b>Report ID:</b> #{report_id}\n"
                            f"👤 <b>Scammer Info:</b> {s_info}\n"
                            f"STATUS: 🔴 <b>Account Deleted / Banned by Telegram</b>\n\n"
                            f"Telegram Abuse Team မှ အဆိုပါ Scammer အကောင့်အား အပြီးတိုင် အရေးယူ/ပိတ်သိမ်းလိုက်ပါပြီ။"
                        )
                        await context.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=ban_alert,
                            parse_mode="HTML"
                        )
                except Exception as e:
                    if "Chat not found" in str(e) or "User not found" in str(e):
                        c.execute("UPDATE reports SET status='BANNED' WHERE id=?", (report_id,))
                        conn.commit()

                        ban_alert = (
                            f"🔥 <b>SCAMMER ACCOUNT TERMINATED!</b>\n\n"
                            f"📋 <b>Report ID:</b> #{report_id}\n"
                            f"👤 <b>Scammer Info:</b> {s_info}\n"
                            f"STATUS: 🔴 <b>Account Deleted / Banned by Telegram</b>\n\n"
                            f"Telegram Abuse Team မှ အဆိုပါ Scammer အကောင့်အား အပြီးတိုင် အရေးယူ/ပိတ်သိမ်းလိုက်ပါပြီ။"
                        )
                        await context.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=ban_alert,
                            parse_mode="HTML"
                        )
        except Exception as err:
            logging.error(f"Error checking scammer status: {err}")

    conn.close()

# Admin သီးသန့် Scammer အချက်အလက်အစုံ တိုက်ရိုက် ထည့်သွင်းသည့် စနစ်
async def add_scammer_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⚠️ ဤ Command အား Admin Group တွင်သာ အသုံးပြုနိုင်ပါသည်။")
        return

    if not context.args:
        await update.message.reply_text(
            "📝 <b>Admin Scammer Direct Entry System</b>\n\n"
            "<b>သုံးစွဲပုံ:</b>\n"
            "<code>/addscammer ID / Username / Phone / KPay / Wave / အသေးစိတ်</code>\n\n"
            "<b>ဥပမာ:</b>\n"
            "<code>/addscammer ID: 12345678 | @scammer_id | Phone: 09123456789 | KPay: 09123456789 (U Kyaw) | Wave: 09123456789 | ဈေးဝယ်ငွေလိမ်သူ</code>",
            parse_mode="HTML"
        )
        return

    full_info = " ".join(context.args)
    user_id = update.effective_user.id

    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    c.execute("INSERT INTO reports (user_id, scammer_info, description, photos, status) VALUES (?, ?, ?, ?, ?)",
              (user_id, full_info, "Admin Direct Entry Database", "", 'APPROVED'))
    report_id = c.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ <b>Scammer အချက်အလက်များ Database သို့ ထည့်သွင်းပြီးပါပြီ!</b>\n\n"
        f"📋 <b>Record ID:</b> #{report_id}\n"
        f"📄 <b>အချက်အလက်များ:</b>\n{full_info}\n\n"
        f"<i>ယခုမှစ၍ User များ ID, Username, Phone, KPay သို့မဟုတ် Wave နံပါတ်ဖြင့် /search ရိုက်ရှာပါက တန်းပေါ်လာမည် ဖြစ်သည်။</i>",
        parse_mode="HTML"
    )

# User များ Scammer အချက်အလက် ရိုက်ရှာသည့် Search Engine
async def search_scammer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🔍 <b>ACP Scammer Search Engine</b>\n\n"
            "ရှာဖွေလိုသော Scammer ၏ Telegram ID, Username, Phone Number, KPay သို့မဟုတ် WavePay Account ကို /search ၏ အနောက်တွင် တွဲရိုက်ရှာပါ။\n\n"
            "<b>ဥပမာ:</b>\n"
            "• <code>/search 09123456789</code>\n"
            "• <code>/search @scammer_id</code>\n"
            "• <code>/search 123456789</code>",
            parse_mode="HTML"
        )
        return

    query = " ".join(context.args).strip()
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    
    # Database ထဲတွင် Query ပါမပါ ရှာဖွေခြင်း
    c.execute("SELECT id, scammer_info, description FROM reports WHERE scammer_info LIKE ? AND status='APPROVED'", (f'%{query}%',))
    results = c.fetchall()
    conn.close()

    if results:
        msg = f"🚨 <b>WARNING! MATCHED SCAMMER FOUND!</b> 🚨\n\n"
        msg += f"ရှာဖွေမှု <b>'{query}'</b> နှင့် ပတ်သက်၍ Database ထဲတွင် အောက်ပါ လိမ်လည်မှု မှတ်တမ်း(များ) တွေ့ရှိရပါသည်:\n\n"
        for r in results:
            msg += f"📌 <b>Record ID:</b> #{r[0]}\n"
            msg += f"👤 <b>အချက်အလက် အပြည့်အစုံ:</b>\n{r[1]}\n"
            if r[2] != "Admin Direct Entry Database":
                msg += f"📝 <b>ဖြစ်စဉ် အသေးစိတ်:</b> {r[2]}\n"
            msg += "-----------------------------------------\n"
        msg += "⚠️ <b>သတိပေးချက်:</b> ဤသူသည် လိမ်လည်မှု မှတ်တမ်းရှိထားသူဖြစ်၍ ငွေမလွှဲမီ အထူးသတိပြုပါ။"
        await update.message.reply_text(msg, parse_mode="HTML")
    else:
        await update.message.reply_text(
            f"✅ <b>CLEAN RESULT</b>\n\n"
            f"<b>'{query}'</b> အား ACP Database ထဲတွင် တိုင်ကြားထားသည့် Scammer မှတ်တမ်း မတွေ့ရှိသေးပါ။\n\n"
            f"<i>(မှတ်ချက် - အကောင့်သစ်/ဖုန်းနံပါတ်သစ် ပြောင်း၍ လိမ်လည်သူ ဖြစ်နိုင်သဖြင့် ဈေးမဝယ်မီ သတိပြုပါ)</i>",
            parse_mode="HTML"
        )

# Welcome Message for Public Group
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
            
        welcome_text = (
            f"👋 မင်္ဂလာပါ {member.mention_html()}!\n"
            f"ACP - Cyber Scam Watch Public Group မှ ကြိုဆိုပါသည်။\n\n"
            f"🚨 <b>ဂရုအတွင်း လိုက်နာရမည့် စည်းကမ်းချက်များ:</b>\n"
            f"၁။ Telegram ရဲ့ Official Terms of Service များကို လုံးဝ လိုက်နာရမည်။\n"
            f"၂။ မမှန်သတင်းများ၊ Spam links၊ Scam / Phishing links များ မပို့ရ။\n"
            f"၃။ အမုန်းစကားများ၊ ခြိမ်းခြောက်မှုများနှင့် မဆိဒ္ဓိ/ရိုင်းစိုင်းသော စာသားနှင့် ပုံများ ပို့သခြင်း ပိတ်ပင်ထားသည်။\n"
            f"၄။ လိမ်လည်ခံရမှု သတင်းပို့လိုပါက ဒီဂရုထဲတွင် မတင်ဘဲ ကျွန်ုပ်တို့၏ Bot တွင် /report ဖြင့် သီးသန့် တိုင်ကြားပေးပါ။\n\n"
            f"⚠ <b>စည်းကမ်း ချိုးဖောက်ပါက အောက်ပါအတိုင်း အရေးယူဆောင်ရွက်ပါမည်:</b>\n"
            f"• ဂရုအတွင်းမှ ချက်ချင်း Mute / Permanent Ban မည်။\n"
            f"• စည်းကမ်းဖောက်ဖျက်မှု အထောက်အထားများဖြင့် Telegram Abuse Team ထံ တိုက်ရိုက် Report တိုင်ကြားမည်။"
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_text,
            parse_mode="HTML"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👮‍♂️ <b>Anonymous Cyber Police (ACP) Bot</b>\n\n"
        "လိမ်လည်သူများကို စနစ်တကျ သတင်းပို့ တိုင်ကြားနိုင်သလို Scammer ဟုတ်/မဟုတ်လည်း စစ်ဆေးနိုင်ပါသည်။\n\n"
        "• တိုင်ကြားရန်: /report\n"
        "• Scammer ရှာရန်: /search [Phone/KPay/Username/ID]"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['photos'] = []
    await update.message.reply_text(
        "🚨 <b>အဆင့် (၁/၃):</b>\nလိမ်လည်သူ၏ အချက်အလက်များကို ပို့ပေးပါ (ဥပမာ- Telegram ID, Username, Phone Number, KPay/Wave)။"
    )
    return SCAMMER_INFO

async def get_scammer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['scammer_info'] = update.message.text
    await update.message.reply_text(
        "📝 <b>အဆင့် (၂/၃):</b>\nလိမ်လည်ခံရသည့် ဖြစ်စဉ် အသေးစိတ်ကို ရေးသားပေးပါ။"
    )
    return INCIDENT_DESC

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text(
        "📸 <b>အဆင့် (၃/၃):</b>\nအထောက်အထား ဓာတ်ပုံများ ပို့ပေးပါ (တစ်ပုံမက ပို့နိုင်သည်)။\nပုံများ ပို့ပြီးပါက <b>'ပြီးပြီ'</b> ဟု စာရိုက်ပို့ပါ။"
    )
    return EVIDENCE_PHOTOS

async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        context.user_data['photos'].append(photo_id)
        await update.message.reply_text(f"✅ ပုံ {len(context.user_data['photos'])} ပုံ လက်ခံရရှိပါပြီ။ နောက်ထပ်ပုံ ပို့နိုင်ပါသေးသည် (သို့မဟုတ် 'ပြီးပြီ' ဟု ရိုက်ပို့ပါ)။")
        return EVIDENCE_PHOTOS
    
    elif update.message.text and update.message.text.strip() == "ပြီးပြီ":
        if not context.user_data['photos']:
            await update.message.reply_text("⚠️ ကျေးဇူးပြု၍ အနည်းဆုံး အထောက်အထား ပုံ ၁ ပုံ ပို့ပေးပါ။")
            return EVIDENCE_PHOTOS
            
        summary = (
            "📋 <b>သင့် တိုင်ကြားချက် အချက်အလက်များ</b>\n\n"
            f"👤 <b>လိမ်လည်သူ:</b>\n{context.user_data['scammer_info']}\n\n"
            f"📝 <b>ဖြစ်စဉ်:</b>\n{context.user_data['description']}\n\n"
            f"🖼 <b>အထောက်အထား:</b> {len(context.user_data['photos'])} ပုံ\n\n"
            "အတည်ပြု ပေးပို့ရန် 'အတည်ပြုမည်' ကို နှိပ်ပါ။"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ အတည်ပြုမည်", callback_data="submit_report")],
            [InlineKeyboardButton("❌ ပယ်ဖျက်မည်", callback_data="cancel_report")]
        ])
        await update.message.reply_text(summary, parse_mode="HTML", reply_markup=keyboard)
        return CONFIRMATION

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "submit_report":
        user_id = query.from_user.id
        s_info = context.user_data['scammer_info']
        desc = context.user_data['description']
        photos_str = ",".join(context.user_data['photos'])

        conn = sqlite3.connect('reports.db')
        c = conn.cursor()
        c.execute("INSERT INTO reports (user_id, scammer_info, description, photos, status) VALUES (?, ?, ?, ?, ?)",
                  (user_id, s_info, desc, photos_str, 'PENDING'))
        report_id = c.lastrowid
        conn.commit()
        conn.close()

        admin_text = (
            f"📥 <b>NEW SCAM REPORT AUDIT (ID: #{report_id})</b>\n\n"
            f"👤 <b>Scammer Info:</b>\n{s_info}\n\n"
            f"📝 <b>Details:</b>\n{desc}"
        )
        admin_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"app_{report_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"rej_{report_id}")
            ]
        ])

        for pid in context.user_data['photos']:
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=pid)
            
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )

        await query.edit_message_text("✅ သင့်တိုင်ကြားချက်အား Admin အဖွဲ့ထံ စစ်ဆေးရန် ပို့ဆောင်ပြီးပါပြီ။")
    else:
        await query.edit_message_text("❌ တိုင်ကြားချက်ကို ပယ်ဖျက်လိုက်ပါပြီ။")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ တိုင်ကြားမှု လုပ်ငန်းစဉ် မပြီးဆုံးသေးဘဲ ရပ်တန့်လိုက်ပါပြီ။")
    return ConversationHandler.END

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("app_") or data.startswith("rej_"):
        action, r_id = data.split("_")
        conn = sqlite3.connect('reports.db')
        c = conn.cursor()
        c.execute("SELECT scammer_info, description, photos FROM reports WHERE id=?", (r_id,))
        row = c.fetchone()

        if not row:
            await query.message.reply_text("❌ Report အချက်အလက် ရှာမတွေ့ပါ။")
            conn.close()
            return

        s_info, desc, photos_str = row

        if action == "app":
            c.execute("UPDATE reports SET status='APPROVED' WHERE id=?", (r_id,))
            conn.commit()

            public_text = (
                f"🚨 <b>CONFIRMED SCAM ALERT (Report #{r_id})</b> 🚨\n\n"
                f"👤 <b>လိမ်လည်သူ အချက်အလက်:</b>\n{s_info}\n\n"
                f"📝 <b>ဖြစ်စဉ် အသေးစိတ်:</b>\n{desc}\n\n"
                "⚠️ <i>Verified by Anonymous Cyber Police</i>"
            )
            
            if photos_str:
                photos_list = photos_str.split(",")
                for pid in photos_list:
                    await context.bot.send_photo(chat_id=PUBLIC_GROUP_ID, photo=pid)
                
            await context.bot.send_message(chat_id=PUBLIC_GROUP_ID, text=public_text, parse_mode="HTML")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ Report #{r_id} ကို Approve လုပ်လိုက်ပါပြီ။ Auto-Search စနစ်နှင့် Tracker ထဲသို့ ထည့်သွင်းလိုက်ပါပြီ။")

        elif action == "rej":
            c.execute("UPDATE reports SET status='REJECTED' WHERE id=?", (r_id,))
            conn.commit()
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"❌ Report #{r_id} ကို ပယ်ဖျက်လိုက်ပါပြီ။")

        conn.close()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('report', start_report)],
        states={
            SCAMMER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_scammer_info)],
            INCIDENT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            EVIDENCE_PHOTOS: [MessageHandler(filters.PHOTO | filters.TEXT, get_photos)],
            CONFIRMATION: [CallbackQueryHandler(handle_confirmation)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addscammer", add_scammer_direct))
    app.add_handler(CommandHandler("search", search_scammer))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # Background Auto-Checker (၁ နာရီတစ်ကြိမ် အလိုအလျောက် စစ်ပေးမည်)
    if app.job_queue:
        app.job_queue.run_repeating(auto_check_scammers, interval=3600, first=10)

    print("ACP Bot running with Direct Add & Search Engine...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
EOF

nohup python main.py > bot.log 2>&1 &
nohup bash -c 'while true; do python main.py; sleep 5; done' > bot.log 2>&1 &
mkdir -p ~/.termux/boot
nano ~/.termux/boot/start_bot.sh
