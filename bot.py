import asyncio
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

active_games = {}
registered_users = set()
registered_groups = set()
user_spam_tracker = {}

ADMIN_ID = 7677244398

IMPOSTOR_WIN_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHp1b3NnbG1xZTFjbm1yMmlxcG5iZXpnb3B0cm82bnRpd3d1OHlhYSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/LqU19aByR88PsnMv3V/giphy.gif"
CITIZEN_WIN_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbms1Mmd4cWRmZHQ4a2Mxa2p3YXRxOTRocm16a2VxejllOHZvbXUydyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/2gtoSIz4sUS0h4TOZ6/giphy.gif"

WORD_CATEGORIES = {
    "အစားအသောက် / မုန့်": ["ပန်းသီး", "ဒူးရင်းသီး", "ပီဇာ", "ကြက်ကြော်", "လက်ဖက်ရည်", "မုန်းဟင်းခါး", "ကော်ဖီ", "ရေခဲမုန့်", "ပေါင်မုန့်", "ဘာဂါ"],
    "မြို့ သို့မဟုတ် နေရာဒေသ": ["ရန်ကုန်", "မန္တလေး", "နေပြည်တော်", "တောင်ကြီး", "ပြင်ဦးလွင်", "ပုဂံ", "ချောင်းသာ", "ငပလီ"],
    "လျှပ်စစ်ပစ္စည်း / အသုံးအဆောင်": ["ဖုန်း", "ကွန်ပျူတာ", "တီဗီ", "ရေခဲသေတ္တာ", "ပန်ကာ", "အဲကွန်း", "လက်ပ်တော့", "နားကြပ်"],
    "ယာဉ်ကျေးမှု / သွားလာရေး": ["ကား", "ရဟတ်ယာဉ်", "လေယာဉ်ပျံ", "သင်္ဘော", "ရထား", "ဆိုင်ကယ်", "စက်ဘီး"],
    "သတ္တဝါ / တိရစ္ဆာန်": ["ကြောင်", "ခွေး", "ဆင်", "ခြင်္သေ့", "ကျား", "ဝက်", "ငှက်", "ငါး", "ယုန်"]
}

START_PRIVATE_TEXT = (
    "🚨 *ဂျင်းကလပ် - The Impostor (ဂိမ်းဆော့နည်း အသေးစိတ်)*\n\n"
    "🎭 *ဂိမ်း၏ ရည်ရွယ်ချက်:* \n"
    "Group Chat ထဲတွင် စကားလုံးတစ်လုံးကို အခြေခံပြီး ကစားသူများထဲမှ စကားလုံးမသိသော **Impostor (သူလျှို)** ကို စကားလုံးလှည့်စား၍ မဲပေးရှာဖွေရမည့် ဂိမ်းဖြစ်သည်။\n\n"
    "📖 *ကစားနည်း အဆင့်ဆင့်:*\n"
    "၁. Group Chat ထဲတွင် `/newgame` ဟု ရိုက်၍ ဂိမ်းသစ်စတင်ပါ။\n"
    "၂. ပါဝင်လိုသူများ **[🎮 Join Game]** Button ကို နှိပ်ပါ။\n"
    "၃. Host က `/Gamestart` နှိပ်သည်နှင့် ဂိမ်းစပါမည်။\n"
    "၄. Bot ရဲ့ DM ထံ ကစားသူများထံ လျှို့ဝှက်စကားလုံး ရောက်ရှိမည်။\n"
    "၅. Group Chat ထဲတွင် စကားလုံးနှင့် ပတ်သက်သည့် Hint ၁ ခွန်းစီ စာရိုက်ပြောပါ။\n"
    "၆. စကားပြောပြီးပါက `/vote` ဟု ရိုက်၍ Impostor ဟု သံသယရှိသူအား မဲပေးပါ။\n"
    "၇. ဂိမ်းပွဲစဉ်ကို ရပ်တန့်ချင်ပါက Host က `/endgame` ဟု ရိုက်ပေးပါ။"
)

def get_unlimited_word_and_hint():
    category = random.choice(list(WORD_CATEGORIES.keys()))
    word = random.choice(WORD_CATEGORIES[category])
    return word, f"အမျိုးအစားမှာ [{category}] ဖြစ်သည်"

async def start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        user_id = update.effective_user.id
        registered_users.add(user_id)
        await update.message.reply_text(START_PRIVATE_TEXT, parse_mode="Markdown")

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if update.effective_chat.type == "private":
        await update.message.reply_text("ဒီ Command ကို Group Chat ထဲမှာပဲ အသုံးပြုလို့ရပါတယ်။")
        return

    now = time.time()
    user_id = user.id
    if user_id not in user_spam_tracker:
        user_spam_tracker[user_id] = []
    
    user_spam_tracker[user_id] = [t for t in user_spam_tracker[user_id] if now - t < 60]
    user_spam_tracker[user_id].append(now)

    if len(user_spam_tracker[user_id]) >= 5:
        await update.message.reply_text(f"⚠️ 🚨 *Spam Warning!* {user.full_name} သည် `/newgame` ကို ၅ ခါဆက်တိုက် စပန်းသည့်အတွက် Admin ထံ Report ပို့လိုက်ပါပြီ။", parse_mode="Markdown")
        try:
            await context.bot.send_message(ADMIN_ID, f"🚨 *Spam Alert!*\nUser: {user.full_name} (ID: `{user_id}`)\nGroup: `{chat_id}`")
        except Exception:
            pass
        return

    registered_groups.add(chat_id)

    active_games[chat_id] = {
        "host_id": user.id,
        "host_name": user.full_name,
        "players": {user.id: user.full_name},
        "status": "lobby",
        "current_round": 1,
        "max_rounds": 3,
        "scores": {user.id: 0},
        "secret_word": "",
        "word_hint": "",
        "impostor_id": None,
        "votes": {}
    }

    keyboard = [
        [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")],
        [InlineKeyboardButton("💬 Bot DM သို့သွားရန် (Start နှိပ်ရန်)", url=f"https://t.me/{context.bot.username}?start=game")]
    ]

    caption = (
        f"🕵️‍♂️️ *ဂျင်းကလပ် - The Impostor (ဂိမ်းအသစ်)*\n\n"
        f"👑 *Host:* {user.full_name}\n\n"
        f"📜 *Player List (1):*\n"
        f"1. {user.full_name}\n\n"
        f"⚠️ *သတိပေးချက်:* Bot ထံမှ စကားလုံးရရှိရန် ကစားသူများ Bot DM တွင် /start သွားနှိပ်ထားပေးပါ။\n"
        f"📢 *ဂိမ်းစတင်ရန် Host ({user.full_name}) မှ `/Gamestart` ဟု ရိုက်ပေးပါ။ (ရပ်တန့်ရန် `/endgame` ဟု ရိုက်ပါ)*"
    )

    await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def join_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user = query.from_user

    if chat_id not in active_games or active_games[chat_id]["status"] not in ["lobby", "starting_buffer"]:
        await query.answer("လက်ရှိ စတင်ထားသော ဂိမ်းမရှိပါ သို့မဟုတ် ဂိမ်းစတင်သွားပါပြီ။", show_alert=True)
        return

    game = active_games[chat_id]

    if user.id in game["players"]:
        await query.answer("သင် စာရင်းဝင်ပြီးသား ဖြစ်ပါတယ်။", show_alert=True)
        return

    game["players"][user.id] = user.full_name
    if user.id not in game["scores"]:
        game["scores"][user.id] = 0
    await query.answer("ဂိမ်းထဲသို့ အောင်မြင်စွာ ပါဝင်လိုက်ပါပြီ!", show_alert=False)

    player_list_str = "\n".join([f"{i+1}. {name}" for i, name in enumerate(game["players"].values())])
    
    caption = (
        f"🕵️️‍♂️ *ဂျင်းကလပ် - The Impostor*\n\n"
        f"👑 *Host:* {game['host_name']}\n\n"
        f"📜 *Player List ({len(game['players'])}):*\n"
        f"{player_list_str}\n\n"
        f"⚠️ *သတိပေးချက်:* Bot ထံမှ စကားလုံးရရှိရန် ကစားသူများ Bot DM တွင် /start သွားနှိပ်ထားပေးပါ။\n"
        f"📢 *ဂိမ်းစတင်ရန် Host ({game['host_name']}) မှ `/Gamestart` ဟု ရိုက်ပေးပါ။*"
    )

    keyboard = [
        [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")],
        [InlineKeyboardButton("💬 Bot DM သို့သွားရန် (Start နှိပ်ရန်)", url=f"https://t.me/{context.bot.username}?start=game")]
    ]
    
    try:
        await query.edit_message_text(text=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass

async def game_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in active_games:
        await update.message.reply_text("စတင်ထားသော ဂိမ်းမရှိပါ။ ရှေးဦးစွာ `/newgame` ကို ရိုက်ပါ။")
        return

    game = active_games[chat_id]

    if user.id != game["host_id"]:
        await update.message.reply_text(f"❌ Join List ထဲတွင် Host ဖြစ်သူ *{game['host_name']}* တစ်ဦးတည်းသာ စတင်လို့ရတာဖြစ်ပါသည်။", parse_mode="Markdown")
        return

    if len(game["players"]) < 3:
        await update.message.reply_text("❌ ဒီဂိမ်းကို ဆော့ကစားရန် အနည်းဆုံး ကစားသူ ၃ ယောက် လိုအပ်ပါတယ်။")
        return

    game["status"] = "starting_buffer"
    await update.message.reply_text("⏳ *ဂိမ်းပွဲစဉ်ကို စက္ကန့် ၃၀ အတွင်း စတင်ပါတော့မည်!*\n\nပါဝင်လိုသူများ အပေါ်မှ **[🎮 Join Game]** ခလုတ်ကို စက္ကန့် ၃၀ အတွင်း နှိပ်၍ ပါဝင်နိုင်ပါသေးသည်။", parse_mode="Markdown")

    await asyncio.sleep(30)
    if chat_id in active_games and active_games[chat_id]["status"] == "starting_buffer":
        await start_round(chat_id, context)

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in active_games:
        await update.message.reply_text("လက်ရှိ ရပ်တန့်ရန် စတင်ထားသော ဂိမ်းပွဲစဉ်မရှိပါ။")
        return

    game = active_games[chat_id]

    if user.id != game["host_id"]:
        await update.message.reply_text(f"❌ ဂိမ်းကို ဖန်တီးခဲ့သူ Host (*{game['host_name']}*) တစ်ဦးတည်းသာ ဂိမ်းကို ရပ်တန့်ခွင့်ရှိပါသည်။", parse_mode="Markdown")
        return

    del active_games[chat_id]
    await update.message.reply_text(f"🛑 *Host ({user.full_name}) မှ ဂိမ်းပွဲစဉ်ကို အပြီးသတ် ရပ်တန့်လိုက်ပါပြီ။*\nဂိမ်းအသစ် ပြန်စဆော့ချင်ပါက `/newgame` ဟု ရိုက်ပါ။", parse_mode="Markdown")

async def start_round(chat_id, context):
    if chat_id not in active_games:
        return

    game = active_games[chat_id]
    game["status"] = "playing"
    game["votes"] = {}

    secret_word, word_hint = get_unlimited_word_and_hint()
    game["secret_word"] = secret_word
    game["word_hint"] = word_hint

    player_ids = list(game["players"].keys())
    impostor_id = random.choice(player_ids)
    game["impostor_id"] = impostor_id

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🚀 *Round {game['current_round']} / {game['max_rounds']} စတင်ပါပြီ!*\n\nလျှို့ဝှက်စကားလုံးများကို ကစားသူများ၏ DM သို့ ပို့ပေးနေပါသည်...",
        parse_mode="Markdown"
    )

    for pid in player_ids:
        try:
            if pid == impostor_id:
                await context.bot.send_message(
                    chat_id=pid,
                    text=f"🕵️️‍♂️ *သင်သည် IMPOSTOR (သူလျှို) ဖြစ်သည်။*\n\n💡 *မသိသာသော Hint:* `{word_hint}`\n\nစကားလုံးအမှန်ကို မသိရပါ။ ဒီ Hint ကို သုံးပြီး မမိအောင် ရောယှက်ပြောဆိုပါ။",
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id=pid,
                    text=f"🤫 *လျှို့ဝှက်စကားလုံးမှာ:* `{secret_word}`\n\nဒီစကားလုံးကို အခြားသူများ မသိအောင် လျှို့ဝှက်ထားပါ။",
                    parse_mode="Markdown"
                )
        except Exception:
            print(f"DM Send Error: {pid}")

    await asyncio.sleep(3)

    player_names = list(game["players"].values())
    random.shuffle(player_names)
    order_str = "\n".join([f"{i+1}. {name}" for i, name in enumerate(player_names)])

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"💬 *စကားပြော အလှည့်ကျ စာရင်း:*\n\n{order_str}\n\n"
             f"📢 *ကစားသူများ အပေါ်ပါ အစီအစဉ်အတိုင်း စကားလုံးနှင့် ပတ်သက်သည့် Hint ၁ ခွန်းစီ Group ထဲတွင် စာရိုက်ပြောကြပါ။*\n\n"
             f"အားလုံး စကားပြောပြီးပါက မဲပေးရန် `/vote` ဟု ရိုက်ပါ။",
        parse_mode="Markdown"
    )

async def start_voting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in active_games or active_games[chat_id]["status"] != "playing":
        await update.message.reply_text("လက်ရှိ မဲပေးနိုင်သော ပွဲစဉ်မရှိပါ။")
        return

    game = active_games[chat_id]
    game["status"] = "voting"

    keyboard = []
    for pid, name in game["players"].items():
        keyboard.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"impvote_{pid}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🗳 *မဲပေးပွဲ စတင်ပါပြီ! (Anonymous Voting)*\n\n"
        "မိမိ သံသယရှိသော Player ၏ အမည် ခလုတ်ကို နှိပ်၍ မဲပေးပါ (ကစားသူ အားလုံး မဲပေးပြီးပါက ရလဒ် ချက်ချင်း ထွက်ပါမည်):",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    for _ in range(45):
        await asyncio.sleep(1)
        if chat_id not in active_games or active_games[chat_id]["status"] == "results_shown":
            return

    await show_results(chat_id, context)

async def handle_imp_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if chat_id not in active_games or active_games[chat_id]["status"] != "voting":
        await query.answer("❌ မဲပေးချိန် ကုန်လွန်သွားပါပြီ။", show_alert=True)
        return

    game = active_games[chat_id]

    if user_id not in game["players"]:
        await query.answer("❌ သင်သည် ဒီပွဲစဉ်တွင် ပါဝင်ထားသူ မဟုတ်ပါ။", show_alert=True)
        return

    target_id = int(query.data.replace("impvote_", ""))
    target_name = game["players"].get(target_id, "Unknown")

    game["votes"][user_id] = target_id
    await query.answer(f"✅ သင်သည် {target_name} ကို လျှို့ဝှက်စွာ မဲပေးလိုက်ပါပြီ! 🤫", show_alert=True)

    if len(game["votes"]) >= len(game["players"]):
        await show_results(chat_id, context)

async def show_results(chat_id, context):
    if chat_id not in active_games or active_games[chat_id]["status"] != "voting":
        return

    game = active_games[chat_id]
    game["status"] = "results_shown"

    vote_counts = {}
    for voter, target in game["votes"].items():
        vote_counts[target] = vote_counts.get(target, 0) + 1

    impostor_id = game["impostor_id"]
    impostor_name = game["players"][impostor_id]
    secret_word = game["secret_word"]

    vote_summary = ""
    for pid, count in vote_counts.items():
        pname = game["players"][pid]
        vote_summary += f"• *{pname}:* {count} မဲ\n"

    if not vote_summary:
        vote_summary = "မည်သူမျှ မဲမပေးခဲ့ကြပါ\n"

    if vote_counts:
        voted_out_id = max(vote_counts, key=vote_counts.get)
        voted_out_name = game["players"][voted_out_id]
    else:
        voted_out_id = None

    round_text = f"📊 *Round {game['current_round']} မဲရလဒ်များ (Voting Results):*\n\n{vote_summary}\n"
    round_text += f"🤫 *လျှို့ဝှက်စကားလုံး:* `{secret_word}`\n"
    round_text += f"🕵️‍♂️ *အမှန်တကယ် Impostor မှာ:* *{impostor_name}*\n\n"

    if voted_out_id == impostor_id:
        round_text += f"🏆 *ရွာသားများ အနိုင်ရရှိသည်!* (Impostor ကို ဖမ်းဆီးနိုင်ခဲ့သည်)\n"
        for pid in game["players"].keys():
            if pid != impostor_id:
                game["scores"][pid] += 10
        win_type = "citizens"
    else:
        round_text += f"💀 *Impostor ({impostor_name}) အနိုင်ရရှိသည်!* (ရွာသားများကို လှည့်စားနိုင်ခဲ့သည်)\n"
        game["scores"][impostor_id] += 20
        win_type = "impostor"

    if win_type == "impostor":
        await context.bot.send_animation(chat_id=chat_id, animation=IMPOSTOR_WIN_GIF, caption=round_text, parse_mode="Markdown")
    else:
        await context.bot.send_animation(chat_id=chat_id, animation=CITIZEN_WIN_GIF, caption=round_text, parse_mode="Markdown")

    await asyncio.sleep(5)

    if chat_id not in active_games:
        return

    if game["current_round"] < game["max_rounds"]:
        game["current_round"] += 1
        await context.bot.send_message(chat_id=chat_id, text=f"⏳ *နောက်တစ်ဆင့် Round {game['current_round']} ကို စက္ကန့် ၁၀ အတွင်း စတင်ပါတော့မည်...*", parse_mode="Markdown")
        await asyncio.sleep(10)
        if chat_id in active_games:
            await start_round(chat_id, context)
    else:
        game["status"] = "ended"
        sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
        final_text = "🎉 *ပွဲစဉ်အပြီး သီးသန့် ရမှတ်စာရင်း (Leaderboard):*\n\n"
        for rank, (pid, score) in enumerate(sorted_scores, 1):
            pname = game["players"][pid]
            crown = "👑 " if rank == 1 else ""
            final_text += f"{rank}. {crown}*{pname}*: {score} Points\n"

        await context.bot.send_message(chat_id=chat_id, text=final_text, parse_mode="Markdown")

async def get_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ ဒီ Command ကို Bot Admin တစ်ဦးတည်းသာ အသုံးပြုပိုင်ခွင့် ရှိပါတယ်။")
        return

    stats_text = (
        "📊 *Jing Club Bot အသုံးပြုမှု အခြေအနေ*\n\n"
        f"👤 *စုစုပေါင်း အသုံးပြုသူ (Users):* {len(registered_users)} ယောက်\n"
        f"👥 *ရောက်ရှိနေသော Group အရေအတွက်:* {len(registered_groups)} ခု\n"
        f"🎮 *လက်ရှိ ဆော့လက်စ ပွဲစဉ်များ:* {len(active_games)} ပွဲ"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

if __name__ == "__main__":
    TOKEN = "8793211070:AAGvsWi4kHh3HorUtX0P3b4040aafHlnakE"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_private))
    app.add_handler(CommandHandler("newgame", new_game))
    app.add_handler(CommandHandler("Gamestart", game_start))
    app.add_handler(CommandHandler("endgame", end_game))
    app.add_handler(CommandHandler("vote", start_voting))
    app.add_handler(CommandHandler("stats", get_stats))
    app.add_handler(CallbackQueryHandler(join_button, pattern="^join_game$"))
    app.add_handler(CallbackQueryHandler(handle_imp_vote, pattern="^impvote_"))

    print("Jing Club - Impostor Bot with PM2 is running...")
    app.run_polling()
