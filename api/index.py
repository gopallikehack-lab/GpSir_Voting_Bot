"""
GpSir Voting Bot — Telegram voting/giveaway bot
Webhook-based Flask app for Vercel serverless deployment.
Persistence: Upstash Redis REST API.
"""

import os
import json
import requests
from flask import Flask, request, jsonify

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ["BOT_USERNAME"]  # without @, e.g. GpSir_Voting_Bot

MAIN_CHANNEL_ID = os.environ["MAIN_CHANNEL_ID"]          # e.g. -1004297567227
MAIN_CHANNEL_LINK = os.environ["MAIN_CHANNEL_LINK"]      # e.g. https://t.me/+JnxnXtxpsmg2MjBl
MAIN_CHANNEL_NAME = os.environ.get("MAIN_CHANNEL_NAME", "Our Private Channel")
WELCOME_IMAGE_URL = os.environ.get(
    "WELCOME_IMAGE_URL",
    "https://i.ibb.co/mrTyzT9X/file-0000000009948208be7ce58b4a0918aa.png",
)

UPSTASH_URL = os.environ["UPSTASH_REDIS_REST_URL"]
UPSTASH_TOKEN = os.environ["UPSTASH_REDIS_REST_TOKEN"]

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Redis helpers (Upstash REST — single command per call)
# ---------------------------------------------------------------------------


def r(*args):
    resp = requests.post(
        UPSTASH_URL,
        headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        json=list(args),
        timeout=10,
    )
    data = resp.json()
    return data.get("result")


def hset(key, mapping):
    flat = []
    for k, v in mapping.items():
        flat.extend([k, v])
    if flat:
        r("HSET", key, *flat)


def hgetall(key):
    flat = r("HGETALL", key) or []
    it = iter(flat)
    return dict(zip(it, it))


def hget(key, field):
    return r("HGET", key, field)


def hincrby(key, field, amount=1):
    return r("HINCRBY", key, field, amount)


def sadd(key, member):
    return r("SADD", key, member)


def sismember(key, member):
    return r("SISMEMBER", key, member)


def smembers(key):
    return r("SMEMBERS", key) or []


def set_kv(key, value, ex=None):
    if ex:
        r("SET", key, value, "EX", ex)
    else:
        r("SET", key, value)


def get_kv(key):
    return r("GET", key)


def del_kv(key):
    r("DEL", key)


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------


def tg(method, **params):
    resp = requests.post(f"{TG_API}/{method}", json=params, timeout=10)
    return resp.json()


def send_message(chat_id, text, reply_markup=None, disable_preview=True):
    return tg(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=disable_preview,
        reply_markup=reply_markup,
    )


def send_photo(chat_id, photo_url, caption=None, reply_markup=None):
    return tg(
        "sendPhoto",
        chat_id=chat_id,
        photo=photo_url,
        caption=caption,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


def edit_message_text(chat_id, message_id, text, reply_markup=None):
    return tg(
        "editMessageText",
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )


def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    return tg(
        "editMessageReplyMarkup",
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
    )


def answer_callback(callback_id, text=None, show_alert=False):
    return tg(
        "answerCallbackQuery",
        callback_query_id=callback_id,
        text=text,
        show_alert=show_alert,
    )


def get_chat(chat_id):
    return tg("getChat", chat_id=chat_id)


def get_chat_member(chat_id, user_id):
    return tg("getChatMember", chat_id=chat_id, user_id=user_id)


def is_member(chat_id, user_id):
    res = get_chat_member(chat_id, user_id)
    if not res.get("ok"):
        return False
    status = res["result"]["status"]
    return status in ("member", "administrator", "creator")


def bot_is_admin(chat_id):
    me = tg("getMe")
    bot_id = me["result"]["id"]
    res = get_chat_member(chat_id, bot_id)
    if not res.get("ok"):
        return False, None
    status = res["result"]["status"]
    return status == "administrator", status


# ---------------------------------------------------------------------------
# Unicode font styling
# ---------------------------------------------------------------------------


def to_bold_italic(text):
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(0x1D468 + (ord(ch) - ord("A"))))
        elif "a" <= ch <= "z":
            out.append(chr(0x1D482 + (ord(ch) - ord("a"))))
        elif "0" <= ch <= "9":
            out.append(chr(0x1D7CE + (ord(ch) - ord("0"))))  # bold digits (no italic digit block)
        else:
            out.append(ch)
    return "".join(out)


def vip(title):
    return f"『 {title} 』"


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def kb(rows):
    return {"inline_keyboard": rows}


def btn_url(text, url):
    return {"text": text, "url": url}


def btn_cb(text, data):
    return {"text": text, "callback_data": data}


# ---------------------------------------------------------------------------
# State helpers (per-user conversation state, stored in Redis with TTL)
# ---------------------------------------------------------------------------


def set_state(user_id, step, data=None):
    payload = {"step": step, "data": data or {}}
    set_kv(f"state:{user_id}", json.dumps(payload), ex=3600)


def get_state(user_id):
    raw = get_kv(f"state:{user_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def clear_state(user_id):
    del_kv(f"state:{user_id}")


# ---------------------------------------------------------------------------
# Owner / entry data helpers
# ---------------------------------------------------------------------------


def owner_key(owner_id):
    return f"owner:{owner_id}"


def entry_key(owner_id, voter_id):
    return f"entry:{owner_id}:{voter_id}"


def entries_set_key(owner_id):
    return f"entries:{owner_id}"


def voted_set_key(owner_id, voter_id):
    return f"voted:{owner_id}:{voter_id}"


def entry_link(owner_id):
    return f"https://t.me/{BOT_USERNAME}?start=entry_{owner_id}"


def support_link(owner_id, voter_id):
    return f"https://t.me/{BOT_USERNAME}?start=support_{owner_id}_{voter_id}"


def entry_card_text(owner, entry):
    votes = entry.get("votes", "0")
    return (
        f"{vip(owner.get('title', 'Giveaway'))}\n\n"
        f"👤 <b>Name:</b> {entry.get('name')}\n"
        f"🔗 <b>Username:</b> {entry.get('username')}\n"
        f"🗳 <b>Votes:</b> <b>{votes}</b>\n\n"
        f"✅ Vote only counts if you're a member of this channel!"
    )


def entry_card_keyboard(owner_id, voter_id):
    return kb(
        [
            [btn_cb("🗳 Vote", f"vote:{owner_id}:{voter_id}")],
            [btn_url("➕ Add Your Name", entry_link(owner_id))],
            [
                btn_url(
                    "📤 Share This Post",
                    "https://t.me/share/url?url="
                    + support_link(owner_id, voter_id)
                    + "&text=Vote for me in the giveaway!",
                )
            ],
        ]
    )


# ---------------------------------------------------------------------------
# Core flow: /start and force-join
# ---------------------------------------------------------------------------


def user_display_name(user):
    name = user.get("first_name", "")
    if user.get("last_name"):
        name += " " + user["last_name"]
    return name.strip() or "Friend"


def prompt_main_join(chat_id, user, resume_payload=""):
    name = user_display_name(user)
    styled = to_bold_italic(name)
    caption = (
        f"✨ {vip('Welcome')} ✨\n\n"
        f"👋 Hey <b>{styled}</b>!\n\n"
        f"Before you can use this bot, please join our official channel:\n"
        f"<b>{MAIN_CHANNEL_NAME}</b>\n\n"
        f"Once you've joined, tap ✅ below."
    )
    markup = kb(
        [
            [btn_url("📢 Join Channel", MAIN_CHANNEL_LINK)],
            [btn_cb("✅ I've Joined", f"joinchk:{resume_payload}")],
        ]
    )
    send_photo(chat_id, WELCOME_IMAGE_URL, caption=caption, reply_markup=markup)


def show_main_menu(chat_id, user):
    name = to_bold_italic(user_display_name(user))
    text = (
        f"🎉 {vip('GpSir Voting Bot')}\n\n"
        f"Welcome, <b>{name}</b>!\n\n"
        f"Use this bot to run a voting giveaway in your own channel — "
        f"members join your channel, add their name, and get votes from others.\n\n"
        f"Ready to set one up?"
    )
    markup = kb([[btn_cb("🎉 Start Giveaway Setup", "setup")]])
    send_message(chat_id, text, reply_markup=markup)


def handle_start(user, payload):
    uid = user["id"]
    if not is_member(MAIN_CHANNEL_ID, uid):
        prompt_main_join(uid, user, resume_payload=payload)
        return
    route_start_payload(user, payload)


def route_start_payload(user, payload):
    uid = user["id"]
    if payload.startswith("entry_"):
        owner_id = payload.split("_", 1)[1]
        begin_entry_flow(user, owner_id)
    elif payload.startswith("support_"):
        _, owner_id, voter_id = payload.split("_", 2)
        show_entry_in_bot(uid, owner_id, voter_id)
    else:
        show_main_menu(uid, user)


# ---------------------------------------------------------------------------
# Giveaway setup (owner side)
# ---------------------------------------------------------------------------


def begin_setup(uid):
    set_state(uid, "await_channel")
    send_message(
        uid,
        "📌 <b>Step 1 — Connect your channel</b>\n\n"
        "1. Add me as <b>admin</b> to the channel you want to run voting in.\n"
        "2. Then send me that channel's @username or numeric ID here.\n\n"
        "Send /cancel anytime to stop.",
    )


def handle_channel_input(uid, text):
    chat_ref = text.strip()
    chat_info = get_chat(chat_ref)
    if not chat_info.get("ok"):
        send_message(uid, "❌ I couldn't find that channel. Double-check the @username or ID and try again.")
        return
    chat_id = chat_info["result"]["id"]
    title = chat_info["result"].get("title", "Your Channel")

    is_admin, status = bot_is_admin(chat_id)
    if not is_admin:
        send_message(
            uid,
            f"❌ I'm not an admin in <b>{title}</b> yet (status: {status or 'not a member'}).\n"
            f"Please add me as admin there, then send the channel again.",
        )
        return

    hset(owner_key(uid), {"channel_id": chat_id, "channel_title": title, "ended": "0"})
    set_state(uid, "await_title")
    send_message(
        uid,
        f"✅ Confirmed! I'm an admin in <b>{title}</b>.\n\n"
        f"📌 <b>Step 2 — Giveaway title</b>\n\n"
        f"Send me the title/name for this giveaway (e.g. \"Best Creator Award\").",
    )


def handle_title_input(uid, text):
    title = text.strip()[:200]
    owner = hgetall(owner_key(uid))
    if not owner:
        clear_state(uid)
        send_message(uid, "⚠️ Something went wrong — please run /start and try setup again.")
        return

    hset(owner_key(uid), {"title": title})
    clear_state(uid)

    link = entry_link(uid)
    send_message(
        uid,
        f"🎉 {vip(title)} is live!\n\n"
        f"Share this link — anyone who joins your channel and taps it gets added "
        f"as a candidate, with a post in your channel for others to vote on:\n\n"
        f"{link}\n\n"
        f"Run /endvoting anytime to close voting and post final results.",
    )

    announce = (
        f"{vip(title)}\n\n"
        f"🗳 Voting is now open! Tap below to add your name and get votes from "
        f"fellow channel members.\n\n"
        f"⚠️ You must be a member of this channel to add your name or to vote."
    )
    tg(
        "sendMessage",
        chat_id=owner.get("channel_id"),
        text=announce,
        parse_mode="HTML",
        reply_markup=kb([[btn_url("➕ Add Your Name", link)]]),
    )


# ---------------------------------------------------------------------------
# Entry flow (participant side)
# ---------------------------------------------------------------------------


def begin_entry_flow(user, owner_id):
    uid = user["id"]
    owner = hgetall(owner_key(owner_id))
    if not owner or not owner.get("channel_id"):
        send_message(uid, "⚠️ This giveaway link is invalid or no longer active.")
        return
    if owner.get("ended") == "1":
        send_message(uid, f"⏹ {vip(owner.get('title', 'This giveaway'))} has already ended.")
        return

    existing = hgetall(entry_key(owner_id, uid))
    if existing:
        send_message(
            uid,
            f"ℹ️ You're already entered in {vip(owner.get('title'))}!\n\n"
            f"Share your post so others can vote for you:\n{support_link(owner_id, uid)}",
        )
        return

    channel_id = owner["channel_id"]
    channel_title = owner.get("channel_title", "the channel")
    if not is_member(channel_id, uid):
        set_state(uid, "await_entry_join", {"owner_id": owner_id})
        send_message(
            uid,
            f"📢 To add your name to {vip(owner.get('title'))}, you must first join:\n"
            f"<b>{channel_title}</b>\n\n"
            f"Join, then tap ✅ below.",
            reply_markup=kb(
                [
                    [btn_cb("✅ I've Joined", f"entryjoinchk:{owner_id}")],
                ]
            ),
        )
        return

    confirm_entry(uid, owner_id, owner)


def confirm_entry(uid, owner_id, owner):
    send_message(
        uid,
        f"📝 Ready to add your name to {vip(owner.get('title'))} in "
        f"<b>{owner.get('channel_title')}</b>?",
        reply_markup=kb([[btn_cb("➕ Confirm — Add My Name", f"entryconfirm:{owner_id}")]]),
    )


def create_entry(user, owner_id):
    uid = user["id"]
    owner = hgetall(owner_key(owner_id))
    if not owner:
        return
    name = user_display_name(user)
    username = f"@{user['username']}" if user.get("username") else "(no username)"

    entry = {"name": name, "username": username, "votes": "0"}
    hset(entry_key(owner_id, uid), entry)
    sadd(entries_set_key(owner_id), uid)

    card_text = entry_card_text(owner, entry)
    markup = entry_card_keyboard(owner_id, uid)
    res = tg(
        "sendMessage",
        chat_id=owner["channel_id"],
        text=card_text,
        parse_mode="HTML",
        reply_markup=markup,
    )
    if res.get("ok"):
        hset(entry_key(owner_id, uid), {"msg_id": res["result"]["message_id"]})

    send_message(
        uid,
        f"✅ Your name has been added to {vip(owner.get('title'))} in "
        f"<b>{owner.get('channel_title')}</b>!\n\n"
        f"📤 Share this link to get votes:\n{support_link(owner_id, uid)}\n\n"
        f"Want to run your own voting giveaway too?",
        reply_markup=kb([[btn_cb("🎉 Start Giveaway Setup", "setup")]]),
    )


def show_entry_in_bot(uid, owner_id, voter_id):
    owner = hgetall(owner_key(owner_id))
    entry = hgetall(entry_key(owner_id, voter_id))
    if not owner or not entry:
        send_message(uid, "⚠️ This post is no longer available.")
        return
    text = entry_card_text(owner, entry) + f"\n\n📍 In: {owner.get('channel_title')}"
    send_message(uid, text, reply_markup=entry_card_keyboard(owner_id, voter_id))


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------


def process_vote(cq, owner_id, voter_entry_id):
    voter = cq["from"]
    vid = voter["id"]
    owner = hgetall(owner_key(owner_id))
    entry = hgetall(entry_key(owner_id, voter_entry_id))

    if not owner or not entry:
        answer_callback(cq["id"], "⚠️ This giveaway is no longer available.", show_alert=True)
        return
    if owner.get("ended") == "1":
        answer_callback(cq["id"], "⏹ Voting has ended.", show_alert=True)
        return
    if str(vid) == str(voter_entry_id):
        answer_callback(cq["id"], "🙅 You can't vote for yourself!", show_alert=True)
        return
    if not is_member(owner["channel_id"], vid):
        answer_callback(
            cq["id"],
            f"❌ Join {owner.get('channel_title')} first, then vote again!",
            show_alert=True,
        )
        return
    if sismember(voted_set_key(owner_id, voter_entry_id), vid):
        answer_callback(cq["id"], "✅ You've already voted for this person!", show_alert=True)
        return

    sadd(voted_set_key(owner_id, voter_entry_id), vid)
    new_votes = hincrby(entry_key(owner_id, voter_entry_id), "votes", 1)
    entry["votes"] = new_votes

    msg_id = entry.get("msg_id")
    if msg_id:
        edit_message_text(
            owner["channel_id"],
            int(msg_id),
            entry_card_text(owner, entry),
            reply_markup=entry_card_keyboard(owner_id, voter_entry_id),
        )
    answer_callback(cq["id"], "🗳 Vote counted! Thanks 🎉")


# ---------------------------------------------------------------------------
# End voting
# ---------------------------------------------------------------------------


def handle_endvoting(uid):
    owner = hgetall(owner_key(uid))
    if not owner or not owner.get("channel_id"):
        send_message(uid, "⚠️ You haven't set up a giveaway yet.")
        return
    if owner.get("ended") == "1":
        send_message(uid, "ℹ️ Voting is already closed.")
        return

    voter_ids = smembers(entries_set_key(uid))
    results = []
    for vidx in voter_ids:
        entry = hgetall(entry_key(uid, vidx))
        if entry:
            results.append((entry.get("name", "?"), entry.get("username", ""), int(entry.get("votes", 0)), entry.get("msg_id")))

    results.sort(key=lambda x: x[2], reverse=True)
    hset(owner_key(uid), {"ended": "1"})

    medals = ["🥇", "🥈", "🥉"]
    lines = [vip(owner.get("title", "Final Results")), ""]
    if not results:
        lines.append("No entries were submitted.")
    for i, (name, username, votes, _) in enumerate(results):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} <b>{name}</b> {username} — <b>{votes}</b> votes")
    final_text = "\n".join(lines)

    tg("sendMessage", chat_id=owner["channel_id"], text=final_text, parse_mode="HTML")
    send_message(uid, f"🔒 Voting closed!\n\n{final_text}")

    for _, _, _, msg_id in results:
        if msg_id:
            edit_message_reply_markup(
                owner["channel_id"],
                int(msg_id),
                reply_markup=kb([[btn_cb("🔒 Voting Ended", "noop")]]),
            )


# ---------------------------------------------------------------------------
# Update dispatch
# ---------------------------------------------------------------------------


def handle_message(msg):
    chat = msg["chat"]
    if chat["type"] != "private":
        return
    user = msg["from"]
    uid = user["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        clear_state(uid)
        handle_start(user, payload)
        return

    if text.startswith("/endvoting"):
        handle_endvoting(uid)
        return

    if text.startswith("/cancel"):
        clear_state(uid)
        send_message(uid, "❌ Cancelled.")
        return

    state = get_state(uid)
    if not state:
        return
    step = state["step"]
    if step == "await_channel":
        handle_channel_input(uid, text)
    elif step == "await_title":
        handle_title_input(uid, text)


def handle_callback(cq):
    data = cq.get("data", "")
    user = cq["from"]
    uid = user["id"]

    if data == "noop":
        answer_callback(cq["id"])
        return

    if data.startswith("joinchk:"):
        payload = data.split(":", 1)[1]
        if is_member(MAIN_CHANNEL_ID, uid):
            answer_callback(cq["id"], "✅ Joined! Let's go.")
            route_start_payload(user, payload)
        else:
            answer_callback(cq["id"], "❌ You haven't joined yet.", show_alert=True)
        return

    if data == "setup":
        answer_callback(cq["id"])
        begin_setup(uid)
        return

    if data.startswith("entryjoinchk:"):
        owner_id = data.split(":", 1)[1]
        owner = hgetall(owner_key(owner_id))
        if owner and is_member(owner["channel_id"], uid):
            answer_callback(cq["id"], "✅ Joined!")
            clear_state(uid)
            confirm_entry(uid, owner_id, owner)
        else:
            answer_callback(cq["id"], "❌ You haven't joined that channel yet.", show_alert=True)
        return

    if data.startswith("entryconfirm:"):
        owner_id = data.split(":", 1)[1]
        answer_callback(cq["id"], "✅ Adding you now...")
        create_entry(user, owner_id)
        return

    if data.startswith("vote:"):
        _, owner_id, voter_entry_id = data.split(":", 2)
        process_vote(cq, owner_id, voter_entry_id)
        return

    answer_callback(cq["id"])


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": BOT_USERNAME})


@app.route("/api/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}
    try:
        if "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception as e:  # noqa: BLE001
        print("Error handling update:", e)
    return jsonify({"ok": True})
