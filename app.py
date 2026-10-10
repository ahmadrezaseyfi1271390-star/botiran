import json
import os
import re
from pyrubi import Client
from pyrubi.types import Message

# --- تنظیمات ---
DATA_FILE = "qa_data.json"
UPLOAD_DIR = "uploads"
ADMIN_PASSWORD = "1271390"
SESSION_NAME = "mySelf"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- توابع مدیریت داده ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- توابع فرمت‌دهی ---
def apply_formatting(text):
    # بولد
    text = re.sub(r'\*\*(.+?)\*\*', r'**\1**', text)
    # ایتالیک
    text = re.sub(r'__(.+?)__', r'__\1__', text)
    # زیرخط
    text = re.sub(r'--(.+?)--', r'--\1--', text)
    # اسپویلر
    text = re.sub(r'\|\|(.+?)\|\|', r'||\1||', text)
    # لینک: متن = تگ https://link
    text = re.sub(r'(.+?)\s*=\s*تگ\s+(https?://\S+)', r'[\1](\2)', text)
    return text

# --- مقداردهی اولیه ---
qa_data = load_data()
conversation_state = None
temp_question = ""

# --- ساخت کلاینت (از سشن rulog استفاده میکنه) ---
client = Client(SESSION_NAME)

# --- هندلر اصلی ---
@client.on_message()
def handler(message: Message):
    global qa_data, conversation_state, temp_question
    
    is_text = bool(message.text)
    is_file = bool(getattr(message, 'file', None)) or bool(getattr(message, 'photo', None)) or \
              bool(getattr(message, 'video', None)) or bool(getattr(message, 'gif', None))
    
    # --- حالت‌های چند مرحله‌ای ---
    if conversation_state == "waiting_password":
        if is_text and message.text == ADMIN_PASSWORD:
            conversation_state = None
            message.reply("✅ رمز صحیح است.\n\n"
                         "`&&&` - ذخیره سوال و جواب جدید\n"
                         "`####` - مشاهده لیست\n"
                         "`1 حذف سؤال` - حذف سوال شماره 1")
        else:
            conversation_state = None
            message.reply("❌ رمز اشتباه است.")
        return
    
    if conversation_state == "waiting_question":
        if not is_text:
            message.reply("❌ لطفاً یک متن (سوال) ارسال کنید.")
            return
        temp_question = message.text
        conversation_state = "waiting_answer"
        message.reply("✅ سوال ذخیره شد. حالا پیام جواب را ارسال کنید:\n"
                     "(می‌توانید متن، عکس، ویدیو یا فایل بفرستید)")
        return
    
    if conversation_state == "waiting_answer":
        if is_text:
            qa_data[temp_question] = {"type": "text", "content": message.text}
            save_data(qa_data)
            message.reply("✅ ذخیره شد.")
            conversation_state = None
            temp_question = ""
        elif is_file:
            try:
                # پیدا کردن فایل
                file_obj = None
                for attr in ['file', 'photo', 'video', 'gif']:
                    val = getattr(message, attr, None)
                    if val:
                        file_obj = val
                        break
                
                if file_obj is None:
                    message.reply("❌ فایل شناسایی نشد.")
                    return
                
                # اسم فایل
                file_name = f"file_{len(qa_data)}.dat"
                file_path = os.path.join(UPLOAD_DIR, file_name)
                
                # دانلود فایل
                try:
                    if hasattr(message, 'download'):
                        message.download(file_path)
                    elif hasattr(file_obj, 'download'):
                        file_obj.download(file_path)
                    else:
                        message.reply("❌ متد دانلود پیدا نشد.")
                        return
                except Exception as e:
                    message.reply(f"❌ خطا در دانلود: {str(e)}")
                    return
                
                qa_data[temp_question] = {"type": "file", "content": file_path}
                save_data(qa_data)
                message.reply("✅ فایل ذخیره شد.")
                conversation_state = None
                temp_question = ""
            except Exception as e:
                message.reply(f"❌ خطا: {str(e)}")
                conversation_state = None
                temp_question = ""
        else:
            message.reply("❌ لطفاً متن، عکس، ویدیو یا فایل ارسال کنید.")
        return
    
    # --- دستورات مدیریتی ---
    if is_text:
        text = message.text.strip()
        
        # بررسی دستورات
        if text in ["&&&", "####"] or re.match(r"^\d+\s+حذف\s+سؤال$", text):
            conversation_state = "waiting_password"
            message.reply("🔐 لطفاً رمز مدیریتی را وارد کنید:")
            return
        
        # --- پاسخ خودکار ---
        for question, answer_data in qa_data.items():
            if question in text:
                if answer_data["type"] == "text":
                    response = apply_formatting(answer_data["content"])
                    message.reply(response)
                elif answer_data["type"] == "file":
                    fp = answer_data["content"]
                    if os.path.exists(fp):
                        try:
                            if hasattr(message, 'reply_file'):
                                message.reply_file(fp)
                            elif hasattr(client, 'send_file'):
                                client.send_file(message.chat_id, fp)
                            else:
                                message.reply("⚠️ متد ارسال فایل پیدا نشد.")
                        except Exception as e:
                            message.reply(f"❌ خطا در ارسال فایل: {str(e)}")
                    else:
                        message.reply("⚠️ فایل یافت نشد.")
                return

# --- اجرا ---
if __name__ == "__main__":
    print("🤖 ربات شروع به کار کرد...")
    print(f"🔐 رمز مدیریتی: {ADMIN_PASSWORD}")
    client.run()
