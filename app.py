# -*- coding: utf-8 -*-
"""
🤖 ربات تبدیل آهنگ به ویس - API مستقیم روبیکا
📦 Flask + Requests + static-ffmpeg
🎯 دکمه‌های اینلاین نمایشی (بدون کالبک)
"""

from flask import Flask, request, jsonify
import requests
import threading
import os
import tempfile
import subprocess
import time
import json
import re
from datetime import datetime

app = Flask(__name__)

# ===== توکن ربات =====
TOKEN = "CEFCFD0LBGPXPPEEPPYZEWWIKTTFIVFFDTBPTDAZKLJRVCPEZOHRXLGBOCPEJXRH"
BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"

# ===== ffmpeg =====
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
    print("[✓] FFMPEG loaded")
except Exception as e:
    print(f"[✗] FFMPEG error: {e}")


# ============================
# 🧰 توابع API
# ============================
def api(method, payload=None):
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
    body = {"chat_id": str(chat_id), "text": str(text)}
    if inline_keypad:
        body["inline_keypad"] = inline_keypad
        body["inline_keypad_type"] = "New"
    if reply_to:
        body["reply_to_message_id"] = reply_to
    return api("sendMessage", body)


def edit_message(chat_id, message_id, text, inline_keypad=None):
    body = {
        "chat_id": str(chat_id),
        "message_id": message_id,
        "text": str(text)
    }
    if inline_keypad:
        body["inline_keypad"] = inline_keypad
        body["inline_keypad_type"] = "Edit"
    return api("editMessageText", body)


def upload_file(chat_id, file_path):
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
    body = {"chat_id": str(chat_id), "file_id": str(file_id)}
    if reply_to:
        body["reply_to_message_id"] = reply_to
    return api("sendVoice", body)


# ============================
# 🕐 اطلاعات زمان
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


def get_now_info():
    now = datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    pmonths = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
               "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
    
    return {
        "time": now.strftime("%H:%M:%S"),
        "date": f"{jd} {pmonths[jm-1]} {jy}",
        "weekday": weekdays[now.weekday()],
        "full": f"{now.strftime('%H:%M:%S')} - {jd} {pmonths[jm-1]} {jy}"
    }


# ============================
# 🎵 اطلاعات فایل صوتی
# ============================
def get_audio_info(file_path, original_name=""):
    info = {
        "duration": "?",
        "duration_sec": 0,
        "format": "?",
        "size": 0,
        "name": original_name or "audio",
        "artist": "نامشخص",
        "title": ""
    }
    
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout.decode())
            
            fmt = data.get("format", {})
            duration = float(fmt.get("duration", 0))
            info["duration_sec"] = int(duration)
            info["duration"] = format_duration(duration)
            info["format"] = fmt.get("format_name", "?").upper().split(",")[0]
            info["size"] = int(fmt.get("size", 0))
            
            tags = fmt.get("tags", {})
            artist = tags.get("artist") or tags.get("ARTIST") or ""
            title = tags.get("title") or tags.get("TITLE") or ""
            
            if artist:
                info["artist"] = artist
            if title:
                info["title"] = title
    except Exception as e:
        print(f"[FFPROBE ERROR] {e}")
    
    # اگه metadata نبود، از اسم فایل استخراج کن
    if original_name:
        base_name = os.path.splitext(original_name)[0]
        if " - " in base_name:
            parts = base_name.split(" - ", 1)
            if info["artist"] == "نامشخص":
                info["artist"] = parts[0].strip()
            if not info["title"]:
                info["title"] = parts[1].strip()
        else:
            if not info["title"]:
                info["title"] = base_name
    
    if not info["title"]:
        info["title"] = info["name"]
    
    # کوتاه‌سازی برای نمایش
    info["name_short"] = info["name"][:35] + ("..." if len(info["name"]) > 35 else "")
    info["artist_short"] = info["artist"][:30] + ("..." if len(info["artist"]) > 30 else "")
    info["title_short"] = info["title"][:35] + ("..." if len(info["title"]) > 35 else "")
    
    return info


def format_duration(seconds):
    seconds = int(seconds)
    mins = seconds // 60
    secs = seconds % 60
    if mins >= 60:
        hours = mins // 60
        mins = mins % 60
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def format_size(bytes_size):
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.1f} MB"


# ============================
# 🎨 ساخت کیبورد نمایشی
# ============================
def make_start_keypad():
    """کیبورد نمایشی برای پیام استارت"""
    now = get_now_info()
    rows = [
        {"buttons": [{"id": "show_time", "type": "Simple", "button_text": f"🕐 ساعت: {now['time']}"}]},
        {"buttons": [{"id": "show_date", "type": "Simple", "button_text": f"📅 تاریخ: {now['date']}"}]},
        {"buttons": [{"id": "show_day", "type": "Simple", "button_text": f"📆 روز: {now['weekday']}"}]},
    ]
    return {"rows": rows}


def make_loading_keypad(info):
    """کیبورد نمایشی در حال تبدیل"""
    rows = [
        {"buttons": [{"id": "load_1", "type": "Simple", "button_text": f"📁 {info['name_short']}"}]},
        {"buttons": [{"id": "load_2", "type": "Simple", "button_text": f"🎤 {info['artist_short']}"}]},
        {"buttons": [{"id": "load_3", "type": "Simple", "button_text": f"⏱️ {info['duration']}  |  📊 {format_size(info['size'])}"}]},
    ]
    return {"rows": rows}


def make_final_keypad(info):
    """کیبورد نمایشی نهایی"""
    rows = [
        {"buttons": [{"id": "fin_1", "type": "Simple", "button_text": f"🎵 {info['title_short']}"}]},
        {"buttons": [{"id": "fin_2", "type": "Simple", "button_text": f"🎤 {info['artist_short']}"}]},
        {"buttons": [{"id": "fin_3", "type": "Simple", "button_text": f"⏱️ {info['duration']}  |  📊 {format_size(info['size'])}"}]},
        {"buttons": [{"id": "fin_4", "type": "Simple", "button_text": f"🎧 فرمت نهایی: OGG/Opus"}]},
    ]
    return {"rows": rows}


# ============================
# 🎤 تبدیل به ویس
# ============================
def download_file(url, filename):
    try:
        # اسم فایل رو تمیز کن
        safe_name = re.sub(r'[^\w\s\-\.]', '_', filename)[:80]
        path = os.path.join(tempfile.gettempdir(), safe_name)
        r = requests.get(url, stream=True, timeout=120)
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        return None


def convert_to_ogg(input_path):
    try:
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"voice_{int(time.time())}.ogg"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",
            "-c:a", "libopus",
            "-b:a", "48k",
            "-ac", "1",
            "-ar", "48000",
            "-vbr", "on",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180
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
    """پردازش کامل"""
    chat_id = message.get("chat_id")
    file = message.get("file", {})
    file_url = file.get("url") or file.get("file_url")
    file_name = file.get("file_name", "audio.mp3")
    original_msg_id = message.get("message_id")
    
    if not file_url:
        send_message(chat_id, "❌ لینک فایل پیدا نشد!")
        return
    
    # ۱. پیام در حال دانلود
    loading_result = send_message(
        chat_id,
        "🎧 در حال دریافت فایل...\n\n⏳ لطفاً صبر کنید",
        inline_keypad={"rows": [{"buttons": [{"id": "loading", "type": "Simple", "button_text": "⏳ در حال دانلود..."}]}]},
        reply_to=original_msg_id
    )
    
    status_msg_id = None
    if loading_result and loading_result.get("status") == "OK":
        status_msg_id = loading_result.get("data", {}).get("message_id")
    
    # ۲. دانلود
    input_path = download_file(file_url, file_name)
    if not input_path:
        if status_msg_id:
            edit_message(chat_id, status_msg_id, "❌ دانلود فایل ناموفق بود")
        return
    
    # ۳. اطلاعات فایل
    info = get_audio_info(input_path, file_name)
    loading_kb = make_loading_keypad(info)
    
    # ۴. آپدیت با اطلاعات
    if status_msg_id:
        edit_message(
            chat_id, status_msg_id,
            f"🎧 در حال تبدیل...\n\n📁 {info['name_short']}",
            inline_keypad=loading_kb
        )
    
    # ۵. تبدیل
    output_path = convert_to_ogg(input_path)
    if not output_path:
        if status_msg_id:
            edit_message(
                chat_id, status_msg_id,
                "❌ تبدیل فایل ناموفق بود",
                inline_keypad=loading_kb
            )
        try: os.remove(input_path)
        except: pass
        return
    
    # ۶. آپلود
    if status_msg_id:
        edit_message(
            chat_id, status_msg_id,
            "📤 در حال آپلود ویس...",
            inline_keypad=loading_kb
        )
    
    file_id = upload_file(chat_id, output_path)
    if not file_id:
        if status_msg_id:
            edit_message(
                chat_id, status_msg_id,
                "❌ آپلود فایل ناموفق بود",
                inline_keypad=loading_kb
            )
        try:
            os.remove(input_path)
            os.remove(output_path)
        except: pass
        return
    
    # ۷. ارسال ویس
    send_voice(chat_id, file_id, reply_to=original_msg_id)
    
    # ۸. پیام نهایی
    if status_msg_id:
        final_kb = make_final_keypad(info)
        edit_message(
            chat_id, status_msg_id,
            f"✅ ویس شما ارسال شد!\n\n🎵 {info['title_short']}",
            inline_keypad=final_kb
        )
    
    # پاک‌سازی
    try:
        os.remove(input_path)
        os.remove(output_path)
    except: pass


# ============================
# 📨 پردازش پیام‌ها
# ============================
def handle_update(data):
    try:
        # فقط پیام‌های معمولی (بدون inline callback)
        if "update" not in data:
            return
        
        upd = data["update"]
        if upd.get("type") != "NewMessage":
            return
        
        msg = upd.get("new_message", {})
        chat_id = upd.get("chat_id")
        text = str(msg.get("text", "")).strip()
        file = msg.get("file", {})
        
        if not chat_id:
            return
        
        print(f"[MSG] text={text[:30]} | file={bool(file)}")
        
        # ===== دستور /start =====
        if text == "/start":
            now = get_now_info()
            start_text = (
                f"سلام! 👋\n\n"
                f"🎵 برای تبدیل آهنگ به ویس، فایل صوتی خود را بفرست.\n\n"
                f"📝 فقط کافیه فایل رو بفرستی، بقیه‌اش با من!"
            )
            send_message(
                chat_id,
                start_text,
                inline_keypad=make_start_keypad()
            )
            return
        
        # ===== فایل ورودی =====
        if file:
            threading.Thread(
                target=process_voice,
                args=(msg,),
                daemon=True
            ).start()
            return
        
        # ===== دستور ناشناخته =====
        if text:
            send_message(chat_id, "🎵 لطفاً یک فایل صوتی بفرست.\n\nیا /start رو بزن.")
    
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
    me = api("getMe")
    if me and me.get("status") == "OK":
        bot_info = me.get("data", {}).get("bot", {})
        print(f"[✓] Bot: {bot_info.get('bot_title')} (@{bot_info.get('username')})")
    else:
        print(f"[✗] Token error: {me}")
    
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
