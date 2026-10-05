from flask import Flask, request, jsonify
import requests
import threading

app = Flask(__name__)

TOKEN = "CEFCFD0ECUJKKLJTVKOPNCVNBUKJBVQZVJIJUQCSYCOPCUQYHFDIEHORVRRRAXCU"
BASE = f"https://botapi.rubika.ir/v3/{TOKEN}"

# ===== کش برای پاسخ‌های تکراری =====
response_cache = {}

def send_async(chat_id, text):
    """ارسال پیام در پس‌زمینه تا Webhook سریع جواب بده"""
    def _send():
        try:
            requests.post(
                f"{BASE}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=5
            )
        except Exception as e:
            print(f"Send error: {e}")
    
    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()

@app.route("/", methods=["POST", "GET"])
def webhook():
    # ===== پاسخ فوری به HEAD (برای UptimeRobot) =====
    if request.method == "GET":
        return "OK", 200
    
    try:
        data = request.json
        update = data.get("update", {})
        
        if update.get("type") == "NewMessage":
            msg = update.get("new_message", {})
            text = msg.get("text", "").strip()
            chat_id = update.get("chat_id")
            
            if not chat_id:
                return jsonify({"status": "OK"}), 200
            
            # ===== پاسخ‌های آماده (سریع) =====
            if text == "/start":
                reply = "سلام! به ربات خوش اومدی 🌹"
            elif text == "/help":
                reply = "📖 راهنما:\n/start - شروع\n/help - راهنما"
            elif text:
                reply = f"دریافت شد: {text}"
            else:
                reply = None
            
            if reply:
                # ارسال در پس‌زمینه = Webhook سریع جواب می‌ده
                send_async(chat_id, reply)
    
    except Exception as e:
        print(f"Error: {e}")
    
    # ===== جواب فوری به روبیکا =====
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
