import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Telegram Bot API Token
TOKEN = "8793211070:AAEZhwG6jLeOT7ndXHTS19wXKurRi8Vguy0"

# Victory Edit Video URLs
KIRA_VICTORY_VIDEO = "https://media.giphy.com/media/YmQLj2KxaNDkPmgO20/giphy.gif"
L_VICTORY_VIDEO = "https://media.giphy.com/media/E1ePbgx4L5L3y/giphy.gif"

# Game State Data
players = {}       # {user_id: {"name": str, "role": str, "alive": bool, "matsuda_shot": bool, "near_swap_used": bool}}
votes = {}         # {voter_id: target_id}
game_started = False
registration_open = False
countdown_task = None
game_phase = "NIGHT"  # NIGHT, DAY, VOTING
l_shield_active = True
protected_user_id = None
blocked_user_id = None
fake_note_swapped = False

# 10 Roles Pool
ROLES_POOL = [
    "Kira",            # 1. Death Note Owner
    "L",               # 2. Detective (Lind L. Tailor Decoy Shield Trap)
    "Misa Amane",      # 3. Second Kira (Shinigami Eyes)
    "Near",            # 4. Successor to L (Deduce & Fake Note Swap)
    "Mello",           # 5. Gangster (Block Ability)
    "Ryuk",            # 6. Shinigami (Chaos Role - 2 Votes)
    "Soichiro Yagami", # 7. Police Chief (Protect Ability)
    "Matsuda",         # 8. Yellow Box Hero (Survive & Final Shot)
    "Teru Mikami",     # 9. X-Kira
    "Kiyomi Takada"    # 10. Citizen / Spokesperson
]

async def check_win_conditions(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    global game_started, registration_open
    if not game_started:
        return True

    alive_kira_team = 0
    alive_police_team = 0

    for p_info in players.values():
        if p_info["alive"]:
            if p_info["role"] in ["Kira", "Misa Amane", "Teru Mikami"]:
                alive_kira_team += 1
            elif p_info["role"] in ["L", "Near", "Soichiro Yagami", "Matsuda", "Kiyomi Takada"]:
                alive_police_team += 1

    # Team Kira Win Condition
    if alive_police_team == 0 or alive_kira_team >= alive_police_team:
        game_started = False
        registration_open = False
        win_msg = (
            "📓 **GAME OVER - TEAM KIRA VICTORY!** 🏆\n\n"
            "*\"I am the God of the New World!\"*\n\n"
            "L နှင့် ရဲတပ်ဖွဲ့များအားလုံး သုတ်သင်ခံလိုက်ရပါပြီ။\n"
            "Light Yagami (KIRA) သည် ကမ္ဘာသစ်ကို စိုးမိုးအုပ်ချုပ်သွားပါတော့မည်... 💀"
        )
        await context.bot.send_message(chat_id=chat_id, text=win_msg, parse_mode="Markdown")
        try:
            await context.bot.send_animation(chat_id=chat_id, animation=KIRA_VICTORY_VIDEO, caption="🎬 **Kira's Supreme Victory Edit**")
        except Exception:
            pass
        return True

    # Team Police (L) Win Condition
    if alive_kira_team == 0:
        game_started = False
        registration_open = False
        win_msg = (
            "⚖️ **GAME OVER - TEAM POLICE / L VICTORY!** 🏆\n\n"
            "*\"Justice will prevail!\"*\n\n"
            "Kira နှင့် နောက်လိုက်များအားလုံး ဖမ်းဆီး/သုတ်သင်ခံလိုက်ရပါပြီ!\n"
            "L နှင့် ရဲတပ်ဖွဲ့မှ တရားဥပဒေစိုးမိုးရေးကို အောင်မြင်စွာ ထိန်းသိမ်းနိုင်ခဲ့ပါသည်... 🔍"
        )
        await context.bot.send_message(chat_id=chat_id, text=win_msg, parse_mode="Markdown")
        try:
            await context.bot.send_animation(chat_id=chat_id, animation=L_VICTORY_VIDEO, caption="🎬 **L's Mastermind Victory Edit**")
        except Exception:
            pass
        return True

    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📓 **Death Note 10-Role Interactive Game Bot**\n\n"
        "✅ သင့်ထံသို့ ဂိမ်းအတွင်း Role အချက်အလက်များနှင့် မဲပေးရန် ခလုတ်များ ရောက်ရှိပါမည်။",
        parse_mode="Markdown"
    )

# Get Keyboard Buttons for Registration Panel
def get_registration_keyboard(bot_username):
    keyboard = [
        [InlineKeyboardButton("➕ Join Game (ပါဝင်မည်)", callback_data="join_game_action")],
        [InlineKeyboardButton("▶️ Start Match (ဂိမ်းစတင်ရန်)", callback_data="start_match_action")],
        [InlineKeyboardButton("🤖 Bot DM တွင် /start နှိပ်ရန် (မဖြစ်မနေ)", url=f"https://t.me/{bot_username}?start=help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /startgame Command to open registration in Group
async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global registration_open, game_started, players, countdown_task
    if game_started or registration_open:
        return await update.message.reply_text("⚠️ ဂိမ်း လက်ရှိ လည်ပတ်နေပြီးဖြစ်ပါသည်။")

    players.clear()
    registration_open = True
    countdown_task = None

    bot_username = (await context.bot.get_me()).username
    reply_markup = get_registration_keyboard(bot_username)

    await update.message.reply_text(
        "📓 **DEATH NOTE GAME - လူစာရင်း ကောက်ယူခြင်း**\n\n"
        "🎮 ဂိမ်းထဲ ပါဝင်လိုသူများ အောက်ပါ **'Join Game'** ခလုတ်ကို နှိပ်ပါ!\n\n"
        "⚠️ **အရေးကြီးသတိပေးချက်:**\n"
        "ဂိမ်း မစမီ အောက်ပါ **'Bot DM တွင် /start နှိပ်ရန်'** ခလုတ်ကို နှိပ်၍ Bot ကို Private Chat တွင် အရင် `/start` ပေးထားရပါမည်။\n\n"
        "*(လူစုံပါက '▶️ Start Match' ခလုတ်ကို နှိပ်၍ ဂိမ်း စတင်ပါ)*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def start_30s_countdown(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ **ဂိမ်းစတင်ရန် ပြင်ဆင်နေပါပြီ!**\n\nဂိမ်းပွဲသည် **စက္ကန့် ၃၀** အတွင်း အလိုအလျောက် စတင်တော့မည် ဖြစ်သည်။ DM တွင် `/start` နှိပ်ထားပြီးပြီဖြစ်ကြောင်း သေချာပါစေ။"
    )
    await asyncio.sleep(30)
    await execute_game_start(context, chat_id)

async def execute_game_start(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    global game_started, registration_open, l_shield_active, fake_note_swapped, game_phase
    if game_started:
        return

    registration_open = False
    game_started = True
    game_phase = "NIGHT"
    l_shield_active = True
    fake_note_swapped = False
    player_ids = list(players.keys())
    random.shuffle(player_ids)

    assigned_roles = ROLES_POOL[:len(player_ids)]
    random.shuffle(assigned_roles)

    kira_name = ""
    for i, p_id in enumerate(player_ids):
        players[p_id]["role"] = assigned_roles[i]
        if assigned_roles[i] == "Kira":
            kira_name = players[p_id]["name"]

    await context.bot.send_message(
        chat_id=chat_id,
        text="🎮 **Death Note ဇာတ်ကောင် ၁၀ မျိုး ဂိမ်း စတင်ပါပြီ!**\n\n🌙 **Night Phase (ညဘက်):** Role များအား DM သို့ ပို့ပေးလိုက်ပါပြီ။ စွမ်းရည်များ သုံးနိုင်ပါပြီ။"
    )

    role_messages = {
        "Kira": "📓 **Kira (Light Yagami)**\n`/kill <Username> <အကြောင်းအရင်း>` ဖြင့် သတ်ပါ။",
        "L": "🔍 **L (Detective)**\n`/investigate <Username>` ဖြင့် စုံစမ်းပါ။",
        "Misa Amane": f"👁 **Misa Amane**\n`/eyes <Username>` ဖြင့် Role အမှန် ကြည့်ပါ။ (Kira မှာ @{kira_name} ဖြစ်သည်)",
        "Near": "🧩 **Near (N)**\n`/deduce <Username>` သို့မဟုတ် `/swap_note` သုံးပါ။",
        "Mello": "🍫 **Mello**\n`/block <Username>` ဖြင့် စွမ်းရည် ပိတ်ပါ။",
        "Ryuk": "🍎 **Ryuk**\n`/view_role <Username>` ဖြင့် Role ကြည့်ပါ။ မဲပေးပွဲတွင် ၂ မဲ ရမည်။",
        "Soichiro Yagami": "🛡 **Soichiro Yagami**\n`/protect <Username>` ဖြင့် ကာကွယ်ပေးပါ။",
        "Matsuda": "🔫 **Matsuda**\nDeath Note ထိပါက `/final_shot <Username>` သုံးပါ။",
        "Teru Mikami": "⚖ **Teru Mikami**\nKira သေလျှင် အစားဝင်မည်။",
        "Kiyomi Takada": "🎤 **Kiyomi Takada**\nသာမန် ပြည်သူ/သတင်းထောက် ဖြစ်သည်။"
    }

    for p_id in player_ids:
        role = players[p_id]["role"]
        try:
            await context.bot.send_message(chat_id=p_id, text=role_messages[role], parse_mode="Markdown")
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ @{players[p_id]['name']} ထံ စာပို့မရပါ။ Bot ကို Private တွင် /start လုပ်ထားပေးပါ။")

# Handle Inline Button Clicks for Joining & Starting
async def button_click_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global countdown_task
    query = update.callback_query
    user = query.from_user

    # Handle "Join Game" Button
    if query.data == "join_game_action":
        if not registration_open:
            return await query.answer("❌ လူစာရင်း ကောက်ယူမှု ပိတ်ထားပါသည်!", show_alert=True)

        if user.id in players:
            return await query.answer("⚠️ သင် ပါဝင်ပြီးသား ဖြစ်ပါသည်!", show_alert=True)

        if len(players) >= 10:
            return await query.answer("❌ ကစားသမား ၁၀ ယောက် ပြည့်သွားပါပြီ!", show_alert=True)

        players[user.id] = {
            "name": user.username or user.first_name,
            "role": None,
            "alive": True,
            "matsuda_shot": False,
            "near_swap_used": False
        }

        await query.answer(f"✅ @{user.username or user.first_name} ဂိမ်းထဲ ပါဝင်လိုက်ပါပြီ!")
        
        msg_text = (
            f"📓 **DEATH NOTE GAME - လူစာရင်း ကောက်ယူခြင်း**\n\n"
            f"📋 **လက်ရှိ ပါဝင်သူများ ({len(players)}/10):**\n"
        )
        for i, p_info in enumerate(players.values(), 1):
            msg_text += f"{i}. @{p_info['name']}\n"

        msg_text += (
            "\n⚠️ **အရေးကြီးသတိပေးချက်:**\n"
            "ဂိမ်း မစမီ Bot DM ထဲတွင် `/start` အရင် နှိပ်ထားပေးကြပါ!"
        )

        bot_username = (await context.bot.get_me()).username
        reply_markup = get_registration_keyboard(bot_username)

        await query.edit_message_text(text=msg_text, reply_markup=reply_markup, parse_mode="Markdown")

        # Trigger 30s Countdown automatically when 10 players join
        if len(players) == 10 and countdown_task is None:
            countdown_task = asyncio.create_task(start_30s_countdown(context, update.effective_chat.id))

    # Handle "Start Match" Button
    elif query.data == "start_match_action":
        if game_started:
            return await query.answer("⚠️ ဂိမ်း စတင်ထားပြီးဖြစ်ပါသည်!", show_alert=True)

        if len(players) < 3:
            return await query.answer("❌ ဂိမ်း စတင်ရန် အနည်းဆုံး ကစားသမား ၃ ယောက် လိုအပ်ပါသည်!", show_alert=True)

        if countdown_task is not None:
            return await query.answer("⚠️ Countdown စတင်နေပြီ ဖြစ်ပါသည်!", show_alert=True)

        await query.answer("▶️ ဂိမ်းပွဲ စတင်ရန် စောင့်ဆိုင်းနေပါသည်...")
        countdown_task = asyncio.create_task(start_30s_countdown(context, update.effective_chat.id))

# Start Voting Phase Command
async def start_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_phase, votes
    if not game_started:
        return await update.message.reply_text("⚠️ ဂိမ်း စတင်ခြင်း မရှိသေးပါ။")

    game_phase = "VOTING"
    votes.clear()

    keyboard = []
    for p_id, p_info in players.items():
        if p_info["alive"]:
            keyboard.append([InlineKeyboardButton(f"🗳 Vote @{p_info['name']}", callback_data=f"vote_{p_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "☀️ **DAY & VOTING PHASE (မဲပေးပွဲ စတင်ပါပြီ)**\n\n"
        "🗳 **မဲပေးရန် ခလုတ်များကို အသက်ရှင်ဆဲ ကစားသမားများ၏ DM (Private Chat) သို့ ပို့ပေးလိုက်ပါပြီ!**\n"
        "Bot DM ထဲသို့ သွား၍ Kira ဟု သံသယရှိသူအား လျှို့ဝှက် မဲပေးကြပါ။\n\n"
        "*(မဲပေးပြီးပါက /end_vote ရိုက်၍ မဲစာရင်း အနိဂုံးချုပ်ပါ)*",
        parse_mode="Markdown"
    )

    for p_id, p_info in players.items():
        if p_info["alive"]:
            try:
                await context.bot.send_message(
                    chat_id=p_id,
                    text="🗳 **Kira ဟု သံသယရှိသူအား လျှို့ဝှက် မဲပေးပါ:**",
                    reply_markup=reply_markup
                )
            except Exception:
                pass

# Handle Inline Button Clicks for Voting
async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    voter = query.from_user

    if not game_started or game_phase != "VOTING":
        return await query.answer("❌ ယခုအချိန်တွင် မဲပေး၍ မရသေးပါ!", show_alert=True)

    if voter.id not in players or not players[voter.id]["alive"]:
        return await query.answer("❌ သေဆုံးသွားသော ကစားသမားများ မဲပေးပိုင်ခွင့် မရှိပါ!", show_alert=True)

    target_id = int(query.data.split("_")[1])
    votes[voter.id] = target_id
    
    target_name = players[target_id]["name"]
    await query.answer(f"✅ သင်သည် @{target_name} အား မဲပေးလိုက်ပါပြီ!", show_alert=True)
    await query.edit_message_text(f"✅ သင်သည် **@{target_name}** အား လျှို့ဝှက် မဲပေးခဲ့ပြီး ဖြစ်ပါသည်။")

# End Voting and Execute Player
async def end_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_phase
    if not game_started or game_phase != "VOTING":
        return await update.message.reply_text("⚠️ မဲပေးပွဲ စတင်ထားခြင်း မရှိပါ။")

    if not votes:
        game_phase = "NIGHT"
        return await update.message.reply_text("🗳 မည်သူမျှ မဲမပေးခဲ့ကြသဖြင့် မဲပေးပွဲ ပယ်ဖျက်လိုက်ပါပြီ။ 🌙 Night Phase သို့ ပြန်လည် ရောက်ရှိပါပြီ။")

    tally = {}
    for voter_id, target_id in votes.items():
        weight = 2 if players[voter_id]["role"] == "Ryuk" else 1
        tally[target_id] = tally.get(target_id, 0) + weight

    lynched_id = max(tally, key=tally.get)
    max_votes = tally[lynched_id]

    players[lynched_id]["alive"] = False
    lynched_name = players[lynched_id]["name"]
    lynched_role = players[lynched_id]["role"]

    await update.message.reply_text(
        f"⚖️ **မဲပေးပွဲ ရလဒ် အနိဂုံးချုပ်:**\n\n"
        f"@{lynched_name} သည် စုစုပေါင်း မဲအရေအတွက် **{max_votes} မဲ** ဖြင့် ကွပ်မျက်ခြင်း ခံလိုက်ရပါပြီ! 💀\n"
        f"*(သူ၏ Role အမှန်မှာ: **{lynched_role}** ဖြစ်သည်)*",
        parse_mode="Markdown"
    )

    is_over = await check_win_conditions(context, update.effective_chat.id)
    if not is_over:
        game_phase = "NIGHT"
        await update.message.reply_text("🌙 **Night Phase (ညဘက်) သို့ ပြန်လည် ရောက်ရှိပါပြီ!** DM တွင် စွမ်းရည်များ သုံးနိုင်ပါပြီ။")

# Night Commands Logic
async def kill_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global l_shield_active, fake_note_swapped
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Kira":
        return

    if user.id == blocked_user_id:
        return await update.message.reply_text("❌ သင့်စွမ်းရည်ကို Mello မှ ပိတ်ပင်ထားသဖြင့် ယခုည သတ်ဖြတ်၍ မရပါ။")

    if fake_note_swapped:
        fake_note_swapped = False
        return await update.message.reply_text("❌ Near မှ Death Note အား စာအုပ်အတုဖြင့် ခိုးလဲထားသဖြင့် သတ်ဖြတ်မှု မအောင်မြင်ပါ။")

    if not context.args:
        return await update.message.reply_text("⚠️ `/kill <Username> <အကြောင်းအရင်း>` ဟု ရိုက်ပါ")

    target_name = context.args[0].replace("@", "").lower()
    cause_of_death = " ".join(context.args[1:]) if len(context.args) > 1 else "နှလုံးရပ်နား၍ သေဆုံးသည်"

    target_id = None
    target_role = None
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name and p_info["alive"]:
            target_id = p_id
            target_role = p_info["role"]
            break

    if target_id:
        if target_id == protected_user_id:
            return await update.message.reply_text(f"🛡 @{players[target_id]['name']} အား Soichiro မှ ကာကွယ်ပေးထားသဖြင့် မသေဆုံးပါ။")

        if target_role == "L" and l_shield_active:
            l_shield_active = False
            await update.message.reply_text(
                f"⚠️ **ထောင်ချောက်ထဲ သက်ဆင်းသွားခဲ့ပါပြီ!**\n\n"
                f"သင် သတ်လိုက်သောသူမှာ L မဟုတ်ဘဲ **Lind L. Tailor** ဖြစ်နေပါသည်!\n"
                f"L ထံသို့ သင်၏ Identity အလိုအလျောက် ပေါက်ကြားသွားခဲ့ပါပြီ။"
            )
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🚨 **Lind L. Tailor Shield အလုပ်လုပ်သွားပါပြီ!**\n\nKira ၏ Username ဖြစ်နိုင်ခြေ: @{user.username or user.first_name}"
            )
            return

        if target_role == "Matsuda":
            players[target_id]["matsuda_shot"] = True
            await update.message.reply_text(f"📓 @{players[target_id]['name']} ၏ အမည်ကို Death Note ထဲ ရေးမှတ်လိုက်ပါပြီ...")
            await context.bot.send_message(
                chat_id=target_id,
                text="💥 **သင့်အား Death Note ဖြင့် တိုက်ခိုက်ခံလိုက်ရပါပြီ!**\n\n`/final_shot <Username>` ဖြင့် Kira အား ပြန်လည် ပစ်ခတ်ပါ!"
            )
            return

        players[target_id]["alive"] = False
        await update.message.reply_text(
            f"📓 **Death Note အလုပ်လုပ်သွားပါပြီ!**\n\n"
            f"@{players[target_id]['name']} သည် **'{cause_of_death}'** ကြောင့် သေဆုံးသွားခဲ့ပါပြီ... 💀"
        )
        await check_win_conditions(context, update.effective_chat.id)
    else:
        await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ သို့မဟုတ် သေဆုံးပြီးသား ဖြစ်ပါသည်။")

async def investigate_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "L":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/investigate <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name:
            role = p_info["role"]
            res = "KIRA ဖြစ်သည်! 🚨" if role in ["Kira", "Teru Mikami"] else "KIRA မဟုတ်ပါ (Innocent) 🟢"
            return await update.message.reply_text(f"🔍 **စုံစမ်းမှု ရလဒ်:** @{p_info['name']} သည် {res}")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def misa_eyes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Misa Amane":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/eyes <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name:
            return await update.message.reply_text(f"👁 **Shinigami Eyes ရလဒ်:**\n\n@{p_info['name']} ၏ ဇာတ်ကောင်အမှန်မှာ **{p_info['role']}** ဖြစ်သည်။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def deduce_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Near":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/deduce <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name:
            team = "Team Kira 🔴" if p_info["role"] in ["Kira", "Misa Amane", "Teru Mikami"] else "Team Police/Neutral 🟢"
            return await update.message.reply_text(f"🧩 **Near's Deduction Result:** @{p_info['name']} သည် {team} ဖြစ်သည်။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def swap_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global fake_note_swapped
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Near":
        return

    if players[user.id].get("near_swap_used"):
        return await update.message.reply_text("⚠ စာအုပ်အတု အစားထိုးခြင်းကို ၁ ကြိမ်သာ သုံးခွင့်ရှိပါသည်။")

    players[user.id]["near_swap_used"] = True
    fake_note_swapped = True
    await update.message.reply_text("🧩 **Fake Note Swap Success!**\n\nယခုည Kira ၏ Death Note အား စာအုပ်အတုဖြင့် ခိုးလဲလိုက်ပါပြီ။")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global blocked_user_id
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Mello":
        return

    if not context.args:
        return await update.message.reply_text(f"👁 **Shinigami Eyes ရလဒ်:**\n\n@{p_info['name']} ၏ ဇာတ်ကောင်အမှန်မှာ **{p_info['role']}** ဖြစ်သည်။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def deduce_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Near":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/deduce <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name:
            team = "Team Kira 🔴" if p_info["role"] in ["Kira", "Misa Amane", "Teru Mikami"] else "Team Police/Neutral 🟢"
            return await update.message.reply_text(f"🧩 **Near's Deduction Result:** @{p_info['name']} သည် {team} ဖြစ်သည်။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def swap_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global fake_note_swapped
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Near":
        return

    if players[user.id].get("near_swap_used"):
        return await update.message.reply_text("⚠ စာအုပ်အတု အစားထိုးခြင်းကို ၁ ကြိမ်သာ သုံးခွင့်ရှိပါသည်။")

    players[user.id]["near_swap_used"] = True
    fake_note_swapped = True
    await update.message.reply_text("🧩 **Fake Note Swap Success!**\n\nယခုည Kira ၏ Death Note အား စာအုပ်အတုဖြင့် ခိုးလဲလိုက်ပါပြီ။")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global blocked_user_id
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Mello":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/block <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name and p_info["alive"]:
            blocked_user_id = p_id
            return await update.message.reply_text(f"🍫 @{p_info['name']} ၏ စွမ်းရည်ကို ယခုညအတွက် ပိတ်ပင်လိုက်ပါပြီ။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def view_role_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Ryuk":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/view_role <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name:
            return await update.message.reply_text(f"🍎 **Ryuk Sight:** @{p_info['name']} ၏ Role မှာ **{p_info['role']}** ဖြစ်သည်။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def protect_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global protected_user_id
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Soichiro Yagami":
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/protect <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name and p_info["alive"]:
            protected_user_id = p_id
            return await update.message.reply_text(f"🛡 @{p_info['name']} အား ယခုည ကာကွယ်ပေးထားလိုက်ပါပြီ။")
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

async def final_shot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not game_started or players.get(user.id, {}).get("role") != "Matsuda" or not players[user.id].get("matsuda_shot"):
        return

    if not context.args:
        return await update.message.reply_text("⚠️ `/final_shot <Username>` ဟု ရိုက်ပါ။")

    target_name = context.args[0].replace("@", "").lower()
    for p_id, p_info in players.items():
        if p_info["name"].lower() == target_name and p_info["alive"]:
            players[user.id]["alive"] = False
            if p_info["role"] in ["Kira", "Teru Mikami"]:
                p_info["alive"] = False
                await update.message.reply_text(f"💥 **Matsuda ၏ နောက်ဆုံး သေနတ်ချက်!**\n\n@{p_info['name']} (KIRA) အား ပစ်သတ်နိုင်ခဲ့ပြီး @{players[user.id]['name']} ပါ သေဆုံးသွားခဲ့ပါပြီ!")
                await check_win_conditions(context, update.effective_chat.id)
            else:
                await update.message.reply_text(f"💥 Matsuda မှ @{p_info['name']} အား ပစ်ခတ်ခဲ့သော်လည်း Kira မဟုတ်ခဲ့ပါ။ Matsuda သေဆုံးသွားခဲ့ပါပြီ...")
                await check_win_conditions(context, update.effective_chat.id)
            return
    await update.message.reply_text("❌ ထိုသူကို ရှာမတွေ့ပါ။")

def main():
    app = Application.builder().token(TOKEN).build()

    # Handlers Registration
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", start_game_command))
    app.add_handler(CommandHandler("start_vote", start_vote))
    app.add_handler(CommandHandler("end_vote", end_vote))
    
    app.add_handler(CallbackQueryHandler(button_click_callback, pattern="^(join_game_action|start_match_action)$"))
    app.add_handler(CallbackQueryHandler(vote_callback, pattern="^vote_"))
    
    app.add_handler(CommandHandler("kill", kill_user))
    app.add_handler(CommandHandler("investigate", investigate_user))
    app.add_handler(CommandHandler("eyes", misa_eyes))
    app.add_handler(CommandHandler("deduce", deduce_user))
    app.add_handler(CommandHandler("swap_note", swap_note))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("view_role", view_role_user))
    app.add_handler(CommandHandler("protect", protect_user))
    app.add_handler(CommandHandler("final_shot", final_shot))

    print("📓 Death Note Interactive Button Game Bot Run လျက်ရှိပါသည်...")
    app.run_polling()

if __name__ == "__main__":
    main()
