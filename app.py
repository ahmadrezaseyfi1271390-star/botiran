from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TOKEN = "CEFCFD0ECUJKKLJTVKOPNCVNBUKJBVQZVJIJUQCSYCOPCUQYHFDIEHORVRRRAXCU"

def send(chat_id, text):
    try:
        requests.post(
            f"https://botapi.rubika.ir/v3/{TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print("Send error:", e)

@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return "IranBot is running!", 200
    
    try:
        data = request.json
        update = data.get("update", {})
        
        if update.get("type") == "NewMessage":
            msg = update.get("new_message", {})
            text = msg.get("text", "")
            chat_id = update.get("chat_id")
            
            if text == "/start":
                send(chat_id, "سلام! به ربات خوش اومدی 🌹")
            elif text == "/help":
                send(chat_id, "راهنما:\n/start - شروع\n/help - راهنما")
            elif text:
                send(chat_id, f"دریافت شد: {text}")
    except Exception as e:
        print("Error:", e)
    
    return jsonify({"status": "OK"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
