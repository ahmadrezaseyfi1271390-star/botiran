# -*- coding: utf-8 -*-
"""
🤖 ربات ساخته‌شده با ایران‌بات
⚡ API مستقیم روبیکا — بدون rubka
📦 Flask + Requests + static-ffmpeg
"""

from flask import Flask, request, jsonify
import requests
import threading
import json
import os
import re
import time
import tempfile
from datetime import datetime

# ===== ffmpeg =====
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
    print("[FFMPEG] loaded successfully")
except Exception as e:
    print(f"[FFMPEG] load failed: {e}")

app = Flask(__name__)

TOKEN = "CEFCFD0LBGPXPPEEPPYZEWWIKTTFIVFFDTBPTDAZKLJRVCPEZOHRXLGBOCPEJXRH"
BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"
TIMEOUT = (10, 30)
UPLOAD_TIMEOUT = (10, 120)

# ============================
# 🧰 API
# ============================
def api(method, payload=None, timeout=TIMEOUT):
    payload = payload or {}
    url = f"{BASE}/{method}"
    try:
        r = requests.post(
            url, json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            print(f"[API] {method}: invalid response")
            return None
        if str(data.get("status", "")).upper() not in ("", "OK", "SUCCESS"):
            print(f"[API ERROR] {method}: {data}")
        return data
    except Exception as e:
        print(f"[API EXCEPTION] {method}: {e}")
        return None


def api_data(method, payload=None, timeout=TIMEOUT):
    result = api(method, payload, timeout)
    if not result:
        return None
    data = result.get("data")
    return data if data is not None else result


def get_me():
    return api_data("getMe")


def send_message(chat_id, text, keypad=None, inline_keypad=None, reply_to_message_id=None):
    body = {"chat_id": str(chat_id), "text": str(text or "")}
    if keypad is not None:
        body["chat_keypad"] = keypad
        body["chat_keypad_type"] = "New"
    if inline_keypad is not None:
        body["inline_keypad"] = inline_keypad
        body["inline_keypad_type"] = "New"
    if reply_to_message_id is not None:
        body["reply_to_message_id"] = reply_to_message_id
    return api_data("sendMessage", body)


def edit_message_text(chat_id, message_id, text):
    return api_data("editMessageText", {
        "chat_id": str(chat_id),
        "message_id": message_id,
        "text": str(text or "")
    })


def delete_message(chat_id, message_id):
    return api_data("deleteMessage", {
        "chat_id": str(chat_id),
        "message_id": message_id
    })


def get_chat(chat_id):
    return api_data("getChat", {"chat_id": str(chat_id)})


def get_chat_member(chat_id, user_id):
    return api_data("getChatMember", {
        "chat_id": str(chat_id),
        "user_id": str(user_id)
    })


# ============================
# 📁 فایل و رسانه
# ============================
MEDIA_METHODS = {
    "image": "sendImage",
    "video": "sendVideo",
    "music": "sendMusic",
    "voice": "sendVoice",
    "gif": "sendGif",
    "document": "sendFile",
}


def upload_file(chat_id, file_path):
    if not file_path or not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, "rb") as fh:
            r = requests.post(
                f"{BASE}/sendFile",
                files={"file": fh},
                data={"chat_id": str(chat_id)},
                timeout=UPLOAD_TIMEOUT
            )
        r.raise_for_status()
        result = r.json()
        data = result.get("data") or {}
        return data.get("file_id") or data.get("fileId") or result.get("file_id")
    except Exception as e:
        print(f"[UPLOAD ERROR] {e}")
        return None


def download_file(url, file_name="remote_file"):
    """دانلود فایل از URL و ذخیره توی temp"""
    if not url:
        return None
    try:
        safe = os.path.basename(file_name or "remote_file") or "remote_file"
        path = os.path.join(tempfile.gettempdir(), safe)
        with requests.get(url, stream=True, timeout=60, headers={"User-Agent": "IranBot/1.0"}) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1024 * 128):
                    if chunk:
                        f.write(chunk)
        return path
    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        return None


def download_rubika_file(file_id, file_name="voice_input"):
    """دانلود فایل از سرور روبیکا با file_id"""
    # روبیکا برای دانلود فایل، متد getFile نداره توی API رسمی
    # اما file_id رو می‌شه از روی پیام کاربر گرفت
    # این تابع فعلاً فایل رو از file_id نمی‌گیره، از URL استفاده می‌کنه
    return None


def convert_to_voice(input_path):
    """تبدیل هر فرمت صوتی به ویس ogg/opus برای روبیکا"""
    if not input_path or not os.path.isfile(input_path):
        return None
    try:
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"voice_{int(time.time())}.ogg"
        )
        # از ffmpeg برای تبدیل به ogg/opus استفاده می‌کنیم
        import subprocess
        command = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",                      # بدون ویدیو
            "-c:a", "libopus",          # کدک Opus
            "-b:a", "48k",              # بیتریت
            "-vbr", "on",
            "-compression_level", "10",
            "-ac", "1",                 # mono
            "-ar", "48000",             # sample rate
            output_path
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )
        if result.returncode != 0:
            print(f"[FFMPEG ERROR] {result.stderr.decode('utf-8', errors='ignore')[:500]}")
            return None
        if not os.path.isfile(output_path):
            print("[FFMPEG ERROR] output file not created")
            return None
        return output_path
    except Exception as e:
        print(f"[CONVERT ERROR] {e}")
        return None


def send_voice(chat_id, voice_path, text="", reply_to_message_id=None):
    """آپلود و ارسال ویس"""
    try:
        # 1) آپلود فایل
        file_id = upload_file(chat_id, voice_path)
        if not file_id:
            print("[VOICE] upload failed")
            return None

        # 2) ارسال به عنوان voice
        body = {
            "chat_id": str(chat_id),
            "file_id": str(file_id),
        }
        if text:
            body["text"] = str(text)
        if reply_to_message_id is not None:
            body["reply_to_message_id"] = reply_to_message_id

        return api_data("sendVoice", body)
    except Exception as e:
        print(f"[VOICE SEND ERROR] {e}")
        return None


def send_file(chat_id, file_id, file_type="document", text="", file_name="", reply_to_message_id=None, url=None):
    try:
        fid = file_id
        if not fid and url:
            local = download_file(url, file_name)
            if local:
                fid = upload_file(chat_id, local)
                try:
                    os.remove(local)
                except Exception:
                    pass
        if not fid:
            print("[FILE ERROR] file_id and url both empty")
            return None
        method = MEDIA_METHODS.get(str(file_type or "document").lower(), "sendFile")
        body = {"chat_id": str(chat_id), "file_id": str(fid)}
        if text:
            body["text"] = str(text)
        if file_name:
            body["file_name"] = str(file_name)
        if reply_to_message_id is not None:
            body["reply_to_message_id"] = reply_to_message_id
        return api_data(method, body)
    except Exception as e:
        print(f"[FILE SEND ERROR] {e}")
        return None


# ============================
# 📊 کاربران و آمار
# ============================
users_count = {}
message_send_counts = {}
message_sender_counts = {}
seen_message_ids = set()
SEEN_FILE = "seen_messages.json"
USERS_FILE = "users.json"
STATS_FILE = "stats.json"

stats_data = {
    "total_messages": 0,
    "total_commands": 0,
    "total_buttons": 0,
    "started_at": datetime.now().isoformat()
}


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[JSON LOAD ERROR] {path}: {e}")
    return default


def save_json(path, value):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[JSON SAVE ERROR] {path}: {e}")


seen_message_ids = set(map(str, load_json(SEEN_FILE, [])))
users_count = load_json(USERS_FILE, {})
stats_data = load_json(STATS_FILE, stats_data)


def save_seen():
    save_json(SEEN_FILE, list(seen_message_ids)[-2000:])


def save_stats():
    save_json(STATS_FILE, stats_data)


def track_user(sender_id, message=None):
    uid = str(sender_id or "")
    if not uid:
        return
    if uid not in users_count:
        users_count[uid] = {
            "first_seen": datetime.now().isoformat(),
            "count": 0,
            "last_seen": datetime.now().isoformat(),
            "name": ""
        }
    users_count[uid]["count"] = int(users_count[uid].get("count", 0)) + 1
    users_count[uid]["last_seen"] = datetime.now().isoformat()
    if message:
        first_name = message.get("first_name") or message.get("sender_name") or ""
        if first_name:
            users_count[uid]["name"] = str(first_name)
    save_json(USERS_FILE, users_count)
    if message:
        text = normalize(message.get("text", ""))
        if text:
            message_send_counts[text] = message_send_counts.get(text, 0) + 1
            message_sender_counts.setdefault(text, set()).add(uid)


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


# ============================
# 🏷️ تگ‌ها
# ============================
def gregorian_to_jalali(gy, gm, gd):
    gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + gdm[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm = days // 31 + 1 if days < 186 else (days - 186) // 30 + 7
    jd = days % 31 + 1 if days < 186 else (days - 186) % 30 + 1
    return jy, jm, jd


def process_tags(text, message=None, bot_info=None):
    if text is None:
        return ""
    text = str(text)
    now = datetime.now()
    message = message or {}
    uid = str(message.get("sender_id") or message.get("user_id") or "")
    chat_id = str(message.get("chat_id") or "")
    sender = message.get("sender") or {}
    first_name = str(
        message.get("first_name")
        or message.get("sender_name")
        or sender.get("first_name")
        or sender.get("name")
        or ""
    )
    username = str(message.get("username") or sender.get("username") or "")
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    pmonths = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
    bot_info = bot_info or {}

    vals = {
        "تایم": now.strftime("%H:%M:%S"),
        "time": now.strftime("%H:%M:%S"),
        "ساعت": now.strftime("%H:%M:%S"),
        "hour": now.strftime("%H:%M:%S"),
        "تاریخ": now.strftime("%Y-%m-%d"),
        "date": now.strftime("%Y-%m-%d"),
        "تاریخ و ساعت": now.strftime("%Y-%m-%d %H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "روز هفته": weekdays[now.weekday()],
        "weekday": now.strftime("%A"),
        "تاریخ شمسی": f"{jy:04d}/{jm:02d}/{jd:02d}",
        "persian_date": f"{jy:04d}/{jm:02d}/{jd:02d}",
        "ماه شمسی": pmonths[jm - 1],
        "persian_month": pmonths[jm - 1],
        "سال شمسی": str(jy),
        "persian_year": str(jy),
        "نام کاربر": first_name,
        "user_name": first_name,
        "نام کاربری": username,
        "username": username,
        "ایدی کاربر": uid,
        "user_id": uid,
        "ایدی چت": chat_id,
        "chat_id": chat_id,
        "نام ربات": bot_info.get("bot_title", ""),
        "bot_name": bot_info.get("bot_title", ""),
        "نام کاربری ربات": bot_info.get("username", ""),
        "bot_username": bot_info.get("username", ""),
        "تعداد نفرات": str(len(users_count)),
        "user_count": str(len(users_count)),
        "users_count": str(len(users_count)),
    }

    for k, v in vals.items():
        ek = re.escape(k)
        text = re.sub(r"\{\s*" + ek + r"\s*\}", str(v), text, flags=re.I)
        text = re.sub(r"\{\s*(?:تگ|tag)\s*" + ek + r"\s*\}", str(v), text, flags=re.I)

    def rand_num(m):
        try:
            a, b = [int(x.strip()) for x in m.group(1).split("-", 1)]
            return str(__import__("random").randint(min(a, b), max(a, b)))
        except Exception:
            return m.group(0)

    text = re.sub(
        r"\{\s*(?:تگ|tag)?\s*(?:عدد تصادفی|random_number)\s*=\s*([^}]+)\}",
        rand_num, text, flags=re.I
    )
    return text


# ============================
# ⌨️ کیبورد
# ============================
def make_chat_keypad(items, resize=True, one_time=False):
    rows = []
    for row in items:
        buttons = []
        for item in row:
            if isinstance(item, dict):
                buttons.append(item)
            else:
                buttons.append({"id": str(item[0]), "type": "Simple", "button_text": str(item[1])})
        if buttons:
            rows.append({"buttons": buttons})
    return {
        "chat_keypad": {
            "rows": rows,
            "resize_keyboard": bool(resize),
            "one_time_keyboard": bool(one_time),
        },
        "chat_keypad_type": "New",
    }


def make_inline_keypad(items):
    rows = []
    for row in items:
        buttons = []
        for item in row:
            if isinstance(item, dict):
                buttons.append(item)
            else:
                buttons.append({"id": str(item[0]), "type": "Simple", "button_text": str(item[1])})
        if buttons:
            rows.append({"buttons": buttons})
    return {"rows": rows}


# ============================
# 🔒 عضویت اجباری
# ============================
FORCE_JOIN_ENABLED = False
FORCE_JOIN_CHANNELS = []
FORCE_JOIN_MESSAGE = "برای استفاده از ربات لطفاً در کانال‌های زیر عضو شوید:"

# ============================
# ⚙️ تنظیمات ربات
# ============================
START_MESSAGE = "خوش اومدید 🌹"
BUTTONS = []
COMMANDS = []
INLINE_BUTTONS = []
KEYBOARD_PACKAGES = []
INLINE_PACKAGES = []

# ============================
# 🎤 Voice mode (آهنگ به ویس)
# ============================
VOICE_MODE_USERS = {}  # {uid: True/False}
VOICE_MODE_PROMPT = "🎤 فایل صوتی خود را ارسال کنید تا به ویس تبدیل شود:"
VOICE_MODE_SUCCESS = "✅ فایل شما به ویس تبدیل شد!"
VOICE_MODE_ERROR = "❌ خطا در تبدیل فایل. لطفاً دوباره امتحان کنید."


def set_voice_mode(uid, enabled):
    if enabled:
        VOICE_MODE_USERS[str(uid)] = True
    else:
        VOICE_MODE_USERS.pop(str(uid), None)


def is_voice_mode(uid):
    return str(uid) in VOICE_MODE_USERS


# ============================
# 📨 پیام‌های ورودی
# ============================
LAST_RESPONSE_IDS = {}
BOT_INFO = {}


def is_user_joined(user_id):
    if not FORCE_JOIN_ENABLED or not FORCE_JOIN_CHANNELS:
        return True
    uid = str(user_id or "").strip()
    if not uid:
        return False
    for channel in FORCE_JOIN_CHANNELS:
        chat_id = str(channel.get("id") or channel.get("channel_id") or "").strip()
        if not chat_id:
            continue
        try:
            result = get_chat_member(chat_id, uid) or {}
            member = result.get("chat_member") if isinstance(result, dict) else None
            if not isinstance(member, dict):
                member = result
            status = str(
                member.get("status")
                or member.get("join_status")
                or member.get("state")
                or ""
            ).strip().lower()
            joined = status in (
                "joined", "member", "administrator", "admin",
                "owner", "creator", "active", "in_channel",
                "present", "true", "1"
            )
            if not joined:
                return False
        except Exception as e:
            print("[FORCE JOIN CHECK ERROR]", chat_id, e)
            return False
    return True


def force_join_keypad():
    return {
        "rows": [
            {"buttons": [
                {"id": "fj_check", "type": "Simple", "button_text": "✅ عضو شدم"}
            ]}
        ]
    }


def force_join_message_text(message):
    base = process_tags(FORCE_JOIN_MESSAGE, message, BOT_INFO)
    links = []
    for channel in FORCE_JOIN_CHANNELS:
        name = str(channel.get("name") or channel.get("id") or "کانال").strip()
        url = str(channel.get("link") or "").strip()
        if url:
            links.append(f"{name}: {url}")
    return base + ("\n\n" + "\n".join(links) if links else "")


def make_keyboard_for(destination_type, destination_id="default"):
    selected = None
    order = 3
    for pkg in KEYBOARD_PACKAGES:
        if (
            pkg.get("destinationType", pkg.get("destination_type")) == destination_type
            and str(pkg.get("destinationId", pkg.get("destination_id", "default"))) == str(destination_id or "default")
        ):
            selected = set(pkg.get("itemIds", pkg.get("item_ids", [])))
            order = max(1, min(5, int(pkg.get("order", 1) or 1)))
            break
    raw = [x for x in BUTTONS if selected is None or x.get("id") in selected]
    rows = []
    for i in range(0, len(raw), order):
        rows.append([(x.get("id"), x.get("text", "")) for x in raw[i:i + order]])
    return make_chat_keypad(rows) if rows else None


def make_inline_for(destination_type, destination_id="default"):
    selected = None
    for pkg in INLINE_PACKAGES:
        if (
            pkg.get("destinationType", pkg.get("destination_type")) == destination_type
            and str(pkg.get("destinationId", pkg.get("destination_id", "default"))) == str(destination_id or "default")
        ):
            selected = set(pkg.get("itemIds", pkg.get("item_ids", [])))
            break
    raw = [x for x in INLINE_BUTTONS if selected is None or x.get("id") in selected]
    rows = []
    for x in raw:
        rows.append([{"id": "inline_" + str(x.get("id")), "type": "Simple", "button_text": str(x.get("text", ""))}])
    return make_inline_keypad(rows) if rows else None


def extract_message(update):
    u = update or {}
    msg = u.get("new_message") or u.get("message") or {}
    if not isinstance(msg, dict):
        msg = {}
    if not msg.get("chat_id"):
        msg["chat_id"] = u.get("chat_id") or (u.get("chat") or {}).get("chat_id")
    if not msg.get("sender_id"):
        msg["sender_id"] = u.get("sender_id") or (u.get("sender") or {}).get("user_id")
    return msg


def extract_update_message_id(update):
    msg = extract_message(update)
    return msg.get("message_id") or update.get("message_id")


def send_configured(item, message, destination_type=None, destination_id="default"):
    chat_id = message.get("chat_id")
    if not chat_id:
        return None

    text = process_tags(
        item.get("textFileText") if item.get("responseType") == "text_file" and item.get("textFileText")
        else item.get("response", ""),
        message, BOT_INFO
    )

    if item.get("responseType") not in ("file", "text_file"):
        kb = make_keyboard_for(destination_type, destination_id) if destination_type else None
        ikb = make_inline_for(destination_type, destination_id) if destination_type else None
        return send_message(chat_id, text, kb, ikb, message.get("message_id"))

    fid = item.get("fileId") or item.get("file_id")
    url = item.get("fileUrl") or ""
    if not fid and not url:
        print(f"[FILE CONFIG ERROR] for {item.get('fileName', '')}")
        return send_message(chat_id, "❌ فایل تنظیم‌شده پیدا نشد")

    return send_file(
        chat_id, fid, item.get("fileType", "document"),
        text, item.get("fileName", ""), message.get("message_id"),
        url=url
    )


# ============================
# 🎤 پردازش ویس
# ============================
def handle_voice_conversion(message):
    """وقتی کاربر فایل صوتی فرستاد، به ویس تبدیل کن"""
    chat_id = message.get("chat_id")
    uid = str(message.get("sender_id") or "")
    file = message.get("file") or {}

    if not chat_id:
        return

    file_id = file.get("file_id")
    file_name = file.get("file_name") or "audio"
    if not file_id:
        send_message(chat_id, "❌ فایلی دریافت نشد")
        set_voice_mode(uid, False)
        return

    send_message(chat_id, "⏳ در حال تبدیل به ویس...")

    # دانلود فایل از روبیکا
    # روبیکا متد getFile نداره، پس باید از file_id استفاده کنیم
    # ولی برای دانلود، نیاز به URL داریم. روبیکا معمولاً URL فایل رو توی پیام می‌ده
    file_url = file.get("url") or file.get("file_url") or file.get("download_url")
    if not file_url:
        # اگه URL نداشت، نمی‌تونیم دانلود کنیم
        # ولی خوشبختانه روبیکا توی file_id خودش URL رو داره
        # راه‌حل: از file_id به عنوان URL استفاده می‌کنیم (اگه روبیکا پشتیبانی کنه)
        send_message(chat_id, "❌ لینک دانلود فایل پیدا نشد. لطفاً فایل را دوباره ارسال کنید.")
        set_voice_mode(uid, False)
        return

    # دانلود
    local_input = download_file(file_url, file_name)
    if not local_input:
        send_message(chat_id, VOICE_MODE_ERROR)
        set_voice_mode(uid, False)
        return

    # تبدیل
    voice_path = convert_to_voice(local_input)
    if not voice_path:
        send_message(chat_id, VOICE_MODE_ERROR)
        try:
            os.remove(local_input)
        except Exception:
            pass
        set_voice_mode(uid, False)
        return

    # آپلود و ارسال
    result = send_voice(chat_id, voice_path, text="", reply_to_message_id=message.get("message_id"))

    # پاک‌سازی
    for p in (local_input, voice_path):
        try:
            if p and os.path.isfile(p):
                os.remove(p)
        except Exception:
            pass

    if result:
        send_message(chat_id, VOICE_MODE_SUCCESS)
    else:
        send_message(chat_id, VOICE_MODE_ERROR)

    set_voice_mode(uid, False)


# ============================
# 🎯 پردازش پیام‌ها
# ============================
def handle_command(message, command):
    clean = command.get("text", "").lstrip("/").strip()
    text = message.get("text", "").strip()
    if text.lstrip("/").strip().lower() != clean.lower():
        return False
    if not is_user_joined(str(message.get("sender_id") or "")):
        send_message(
            message.get("chat_id"),
            force_join_message_text(message),
            inline_keypad=force_join_keypad()
        )
        return True
    stats_data["total_commands"] = stats_data.get("total_commands", 0) + 1
    save_stats()
    send_configured(command, message, "command", command.get("id", "default"))
    return True


def handle_button(message, button_id):
    # دکمه بررسی عضویت
    if button_id == "fj_check":
        uid = str(message.get("sender_id") or "")
        if is_user_joined(uid):
            send_message(message.get("chat_id"), "✅ عضویت بررسی شد.")
        else:
            send_message(message.get("chat_id"), "❌ هنوز عضو نیستی.",
                         inline_keypad=force_join_keypad())
        return True

    for button in BUTTONS:
        if str(button.get("id")) != str(button_id):
            continue

        if not is_user_joined(str(message.get("sender_id") or "")):
            send_message(
                message.get("chat_id"),
                force_join_message_text(message),
                inline_keypad=force_join_keypad()
            )
            return True

        stats_data["total_buttons"] = stats_data.get("total_buttons", 0) + 1
        save_stats()

        mode = button.get("replyMode", "simple")
        chat_id = str(message.get("chat_id") or "")
        destination_key = str(button.get("id", "default"))
        response_key = (chat_id, destination_key)

        if mode == "delete" and message.get("message_id"):
            try:
                delete_message(message.get("chat_id"), message.get("message_id"))
            except Exception as e:
                print("[DELETE ERROR]", e)

        if mode == "edit":
            edit_text = process_tags(button.get("response", ""), message, BOT_INFO)
            previous_id = LAST_RESPONSE_IDS.get(response_key)
            if previous_id:
                try:
                    edited = edit_message_text(message.get("chat_id"), previous_id, edit_text)
                    if edited:
                        return True
                except Exception as e:
                    print("[EDIT ERROR]", e)
            sent = send_configured(button, message, "button", destination_key)
            try:
                data = sent.get("data") if isinstance(sent, dict) else sent
                if not isinstance(data, dict):
                    data = {}
                sent_id = data.get("message_id") or (sent.get("message_id") if isinstance(sent, dict) else None)
                if sent_id:
                    LAST_RESPONSE_IDS[response_key] = sent_id
            except Exception as e:
                print("[EDIT STORE ERROR]", e)
            return True

        send_configured(button, message, "button", destination_key)
        return True

    return False


def handle_update(update):
    try:
        if not isinstance(update, dict):
            return

        # inline callback
        if "inline_message" in update:
            inline = update.get("inline_message") or {}
            msg = {
                "chat_id": inline.get("chat_id"),
                "sender_id": inline.get("sender_id"),
                "message_id": inline.get("message_id"),
                "text": "",
            }
            aux = inline.get("aux_data") or {}
            button_id = aux.get("button_id")
            if button_id:
                handle_button(msg, button_id)
            return

        utype = str(update.get("type") or "")
        if utype and utype != "NewMessage":
            return

        message = extract_message(update)
        if not message.get("chat_id"):
            return

        track_user(message.get("sender_id"), message)
        stats_data["total_messages"] = stats_data.get("total_messages", 0) + 1
        save_stats()

        # فقط پیام‌های جدید
        mid = extract_update_message_id(update)
        if mid is not None:
            smid = str(mid)
            if smid in seen_message_ids:
                return
            seen_message_ids.add(smid)
            save_seen()

        text = str(message.get("text") or "").strip()
        aux = message.get("aux_data") or {}
        button_id = aux.get("button_id")

        if button_id:
            handle_button(message, button_id)
            return

        # ===== state: voice mode =====
        uid = str(message.get("sender_id") or "")
        file = message.get("file") or {}

        if is_voice_mode(uid):
            if file.get("file_id"):
                threading.Thread(
                    target=handle_voice_conversion,
                    args=(message,),
                    daemon=True
                ).start()
                return
            else:
                send_message(message.get("chat_id"), "❌ لطفاً یک فایل صوتی ارسال کنید.")
                return

        # ===== دستورات =====
        if text.lower() in ("/start", "start"):
            if not is_user_joined(uid):
                send_message(
                    message.get("chat_id"),
                    force_join_message_text(message),
                    inline_keypad=force_join_keypad()
                )
                return
            kb = make_keyboard_for("start", "default")
            ikb = make_inline_for("start", "default")
            send_message(
                message.get("chat_id"),
                process_tags(START_MESSAGE, message, BOT_INFO),
                kb, ikb, message.get("message_id")
            )
            return

        # ===== دستور /voice =====
        if text.lower() in ("/voice", "/ویس", "ویس", "صدا به ویس"):
            set_voice_mode(uid, True)
            send_message(message.get("chat_id"), VOICE_MODE_PROMPT)
            return

        # ===== دستورات سفارشی =====
        for command in COMMANDS:
            if handle_command(message, command):
                return

        # ===== فایل ورودی (وقتی voice mode فعال نیست) =====
        if file.get("file_id"):
            print(f"[INCOMING FILE] {file.get('file_name', '')} => {file.get('file_id')}")

        # ===== دکمه‌های متنی =====
        for button in BUTTONS:
            if normalize(button.get("text")) == normalize(text):
                handle_button(message, button.get("id"))
                return

        if text:
            send_message(message.get("chat_id"), "دستور ناشناخته")

    except Exception as e:
        print("[UPDATE ERROR]", e)


# ============================
# 🌐 Webhook + Admin
# ============================
@app.route("/", methods=["POST", "GET"])
def webhook():
    try:
        if request.method == "GET":
            return "IranBot is running!", 200
        data = request.get_json(silent=True) or {}
        threading.Thread(target=handle_update, args=(data,), daemon=True).start()
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        print("[WEBHOOK ERROR]", e)
        return jsonify({"status": "OK"}), 200


@app.route("/broadcast", methods=["POST"])
def broadcast():
    """ارسال پیام همزمان به همه کاربران"""
    try:
        data = request.get_json(silent=True) or {}
        text = str(data.get("text") or "").strip()
        if not text:
            return jsonify({"status": "ERROR", "message": "text required"}), 400

        uids = list(users_count.keys())
        if not uids:
            return jsonify({"status": "OK", "sent": 0, "failed": 0})

        sent = [0]
        failed = [0]
        lock = threading.Lock()

        def send_one(uid):
            try:
                result = send_message(uid, text)
                with lock:
                    if result:
                        sent[0] += 1
                    else:
                        failed[0] += 1
            except Exception as e:
                print(f"[BROADCAST ERROR] {uid}: {e}")
                with lock:
                    failed[0] += 1

        threads = []
        for uid in uids:
            t = threading.Thread(target=send_one, args=(uid,), daemon=True)
            t.start()
            threads.append(t)
            # محدودیت: حداکثر ۲۰ تا همزمان
            if len(threads) >= 20:
                for th in threads:
                    th.join(timeout=5)
                threads = []

        for th in threads:
            th.join(timeout=5)

        return jsonify({
            "status": "OK",
            "total": len(uids),
            "sent": sent[0],
            "failed": failed[0]
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500


@app.route("/stats", methods=["GET"])
def stats():
    """آمار ربات"""
    return jsonify({
        "status": "OK",
        "data": {
            "total_users": len(users_count),
            "total_messages": stats_data.get("total_messages", 0),
            "total_commands": stats_data.get("total_commands", 0),
            "total_buttons": stats_data.get("total_buttons", 0),
            "started_at": stats_data.get("started_at"),
            "force_join_enabled": FORCE_JOIN_ENABLED,
            "buttons_count": len(BUTTONS),
            "commands_count": len(COMMANDS),
        }
    })


@app.route("/users", methods=["GET"])
def users_list():
    """لیست کاربران (بدون اطلاعات حساس)"""
    limit = int(request.args.get("limit", 100))
    users_list_data = []
    for uid, info in list(users_count.items())[:limit]:
        users_list_data.append({
            "user_id": uid,
            "name": info.get("name", ""),
            "count": info.get("count", 0),
            "first_seen": info.get("first_seen", ""),
            "last_seen": info.get("last_seen", ""),
        })
    return jsonify({
        "status": "OK",
        "total": len(users_count),
        "showing": len(users_list_data),
        "users": users_list_data
    })


@app.route("/voice-test", methods=["GET"])
def voice_test():
    """تست ffmpeg"""
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        version_line = result.stdout.decode("utf-8", errors="ignore").split("\n")[0]
        return jsonify({
            "status": "OK",
            "ffmpeg": version_line
        })
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        })


# ============================
# ▶️ اجرا
# ============================
if __name__ == "__main__":
    BOT_INFO = get_me() or {}
    print("🤖 ایرانبات — Direct Rubika API")
    print(f"👤 bot: {BOT_INFO.get('bot_title', '?')}")
    print(f"👥 users: {len(users_count)}")
    print(f"🎤 voice mode: enabled")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
