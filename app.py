# -*- coding: utf-8 -*-
"""
🤖 ربات تبدیل آهنگ به ویس - API مستقیم روبیکا
📦 فقط Flask + Requests + ffmpeg
"""

from flask import Flask, request, jsonify
import requests
import threading
import os
import tempfile
import subprocess
import time
import json

app = Flask(__name__)

# ===== توکن ربات =====
TOKEN = "CEFCFD0LBGPXPPEEPPYZEWWIKTTFIVFFDTBPTDAZKLJRVCPEZOHRXLGBOCPEJXRH"
BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"

# ===== ffmpeg =====
import static_ffmpeg
static_ffmpeg.add_paths()
print("[✓] FFMPEG loaded")

# ===== وضعیت کاربران =====
# کاربرانی که منتظر ارسال فایل صوتی هستن
WAITING_VOICE = {}

# ===== فایل‌های ذخیره‌شده =====
SEEN_FILE = "seen.json"


# ============================
# 🧰 توابع API
# ============================
def api(method, payload=None):
    """درخواست به API روبیکا"""
    try:
        r = requests.post(
            f"{BASE}/{method}",
            json=payload or {},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        return r.json()
    except Exception as e:
        print(f"[API ERROR] {method}: {e}")
        return None


def send_message(chat_id, text, inline_keypad=None, reply_to=None):
    """ارسال پیام"""
    body = {"chat_id": str(chat_id), "text": str(text)}
    if inline_keypad:
        body["inline_keypad"] = inline_keypad
        body["inline_keypad_type"] = "New"
    if reply_to:
        body["reply_to_message_id"] = reply_to
    return api("sendMessage", body)


def upload_file(chat_id, file_path):
    """آپلود فایل به روبیکا"""
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                f"{BASE}/sendFile",
                files={"file": f},
                data={"chat_id": str(chat_id)},
                timeout=120
            )
        data = r.json()
        return data.get("data", {}).get("file_id")
    except Exception as e:
        print(f"[UPLOAD ERROR] {e}")
        return None


def send_voice(chat_id, file_id, reply_to=None):
    """ارسال ویس"""
    body = {"chat_id": str(chat_id), "file_id": str(file_id)}
    if reply_to:
        body["reply_to_message_id"] = reply_to
    return api("sendVoice", body)


# ============================
# 🎤 تبدیل به ویس
# ============================
def download_file(url, filename):
    """دانلود فایل از URL"""
    try:
        path = os.path.join(tempfile.gettempdir(), filename)
        r = requests.get(url, stream=True, timeout=60)
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        return None


def convert_to_ogg(input_path):
    """تبدیل هر فرمت صوتی به ogg/opus"""
    try:
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"voice_{int(time.time())}.ogg"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",                    # بدون ویدیو
            "-c:a", "libopus",        # کدک opus
            "-b:a", "48k",            # بیتریت
            "-ac", "1",               # mono
            "-ar", "48000",           # sample rate
            "-vbr", "on",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )
        
        if result.returncode != 0:
            print(f"[FFMPEG ERROR] {result.stderr.decode()[:300]}")
            return None
        
        if os.path.exists(output_path):
            return output_path
        return None
        
    except Exception as e:
        print(f"[CONVERT ERROR] {e}")
        return None


def process_voice(message):
    """پردازش کامل: دانلود، تبدیل، ارسال"""
    chat_id = message.get("chat_id")
    sender_id = str(message.get("sender_id", ""))
    file = message.get("file", {})
    file_url = file.get("url") or file.get("file_url")
    file_name = file.get("file_name", "audio.mp3")
    
    if not file_url:
        send_message(chat_id, "❌ لینک فایل پیدا نشد!")
        WAITING_VOICE.pop(sender_id, None)
        return
    
    send_message(chat_id, "⏳ در حال تبدیل...")
    
    # دانلود
    input_path = download_file(file_url, file_name)
    if not input_path:
        send_message(chat_id, "❌ دانلود فایل ناموفق بود")
        WAITING_VOICE.pop(sender_id, None)
        return
    
    # تبدیل
    output_path = convert_to_ogg(input_path)
    if not output_path:
        send_message(chat_id, "❌ تبدیل فایل ناموفق بود")
        try: os.remove(input_path)
        except: pass
        WAITING_VOICE.pop(sender_id, None)
        return
    
    # آپلود
    file_id = upload_file(chat_id, output_path)
    if not file_id:
        send_message(chat_id, "❌ آپلود فایل ناموفق بود")
        try:
            os.remove(input_path)
            os.remove(output_path)
        except: pass
        WAITING_VOICE.pop(sender_id, None)
        return
    
    # ارسال ویس
    result = send_voice(chat_id, file_id, reply_to=message.get("message_id"))
    
    # پاک‌سازی
    try:
        os.remove(input_path)
        os.remove(output_path)
    except: pass
    
    WAITING_VOICE.pop(sender_id, None)
    
    if result and result.get("status") == "OK":
        send_message(chat_id, "✅ ویس شما ارسال شد!")
    else:
        send_message(chat_id, "❌ خطا در ارسال ویس")


# ============================
# 📨 پردازش پیام‌ها
# ============================
def handle_update(update):
    try:
        # پیام معمولی
        if "update" not in update:
            return
        
        upd = update["update"]
        if upd.get("type") != "NewMessage":
            return
        
        msg = upd.get("new_message", {})
        chat_id = upd.get("chat_id")
        text = str(msg.get("text", "")).strip()
        sender_id = str(msg.get("sender_id", ""))
        file = msg.get("file", {})
        button_id = (msg.get("aux_data") or {}).get("button_id")
        
        if not chat_id:
            return
        
        print(f"[MSG] {text} | file: {bool(file)} | button: {button_id}")
        
        # دکمه شیشه‌ای
        if button_id == "voice_btn":
            WAITING_VOICE[sender_id] = True
            send_message(chat_id, "🎤 فایل صوتی خود را ارسال کنید:")
            return
        
        # دستور /start
        if text == "/start":
            # کیبورد شیشه‌ای
            keypad = {
                "rows": [{
                    "buttons": [{
                        "id": "voice_btn",
                        "type": "Simple",
                        "button_text": "🎤 تبدیل به ویس"
                    }]
                }]
            }
            send_message(
                chat_id,
                "سلام! 👋\n\nبرای تبدیل آهنگ به ویس، روی دکمه زیر بزن:",
                inline_keypad=keypad
            )
            return
        
        # دستور /voice
        if text in ["/voice", "ویس"]:
            WAITING_VOICE[sender_id] = True
            send_message(chat_id, "🎤 فایل صوتی خود را ارسال کنید:")
            return
        
        # اگه کاربر منتظر ارسال ویس باشه
        if WAITING_VOICE.get(sender_id):
            if file:
                threading.Thread(
                    target=process_voice,
                    args=(msg,),
                    daemon=True
                ).start()
                return
            else:
                send_message(chat_id, "❌ لطفاً یک فایل صوتی ارسال کنید")
                return
        
        # پیام ناشناخته
        if text:
            send_message(chat_id, "دستور ناشناخته. /start رو بزن.")
    
    except Exception as e:
        print(f"[HANDLE ERROR] {e}")


# ============================
# 🌐 Webhook
# ============================
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return "IranBot is running!", 200
    
    try:
        data = request.get_json(silent=True) or {}
        threading.Thread(target=handle_update, args=(data,), daemon=True).start()
    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
    
    return jsonify({"status": "OK"}), 200


@app.route("/test")
def test():
    return jsonify({"status": "OK", "message": "IranBot works!"})


# ============================
# ▶️ اجرا
# ============================
if __name__ == "__main__":
    # تست توکن
    me = api("getMe")
    if me and me.get("status") == "OK":
        bot_info = me.get("data", {}).get("bot", {})
        print(f"[✓] Bot: {bot_info.get('bot_title')} (@{bot_info.get('username')})")
    else:
        print(f"[✗] Token error: {me}")
    
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
