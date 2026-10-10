import json
import os
import re
from pyrubi import Client
from pyrubi.types import Message

# --- تنظیمات ---
DATA_FILE = "qa_data.json"
ADMINS_FILE = "admins.json"
UPLOAD_DIR = "uploads"
ADMIN_PASSWORD = "1271390"

# --- کلیدهای احراز هویت ---
AUTH_KEY = "rjqcaknnfqgqhzndpewvmkitxfrgomvu"
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIICWgIBAAKBgQCwZeG58xGYzujZkVbIFDkrAlof9Icoa+D4aLVyld5XVDKPmRwD
d3SkjHM3/lXBvdny5TRvF2p7QSTJzkGPnrm8f39EKZ9bjhpf2lyT+b6dlFWF8Snj
bXtwGUbdNhwuN1RGpdUy0jn2rmeZWyqYilWRMm0tlYN0uGSs2Fy1PBtATwIDAQAB
An8884eA5j1QmMWYGKIQ8D7mV0lD8Eqt1l8v6eUmTA7nSUgSYRulPqqLr0C4LCuH
tjDCiO6aqmGdH5CcDdJcQyBLd9CSKOCc7cUjOpSOHB+hyDzUm525VOqxEnvhuTXs
Rxj72bqlpd3qqCcyA4ZyGbMM6JbAuxPpKIP7akVY3tQBAkEAytKYxYTGJU7zna0U
Yke91DMu8Dm+Ahh3ol5wx4nM8540pEuVSfIlfTUJRs2kED42res0sBYb6vFQaWdF
NpQUAQJBAN6lqwl/snuOmThYfMI8Sx+BWpwbZCi+GxUKtvRTsY6HpAUPCI9fmQ6D
Bl/Ynn6vUqTbKL3j0SObzCgJON7ZFE8CQQCJnZjgs/UJzWcIfi5NfOX1PAFGJ7ef
jmBl//Q/v2UbiyWmsE4MDUuYh8rSiqceCkhpeySVsXqhz7hCvDo/DPwBAkAnJ1El
sXwsuE3/l6gQ7FN1reTGURbTB2Nx1tmHq/QskXPpo9QoinI7GBWV4100ABbzgMrw
YdDUh0BmxgBnSBuHAkArmOvCD1a71qMSNomfdyfx6wRfrMqYGfoojt7uG/J3NY5g
oiMhyMOHtZhSrKyWEsWuQR9UcHis+142gcezc4dh
-----END RSA PRIVATE KEY-----"""

os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- تابع امن ارسال پیام ---
def safe_reply(message, text):
    try:
        message.reply(text)
        return True
    except Exception:
        try:
            client.send_message(message.chat_id, text)
            return True
        except Exception:
            try:
                client.methods.sendText(
                    objectGuid=message.object_guid,
                    text=text,
                    messageId=message.message_id
                )
                return True
            except Exception:
                return False

# --- توابع داده ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_admins(admins_set):
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(admins_set), f, ensure_ascii=False)

def apply_formatting(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'**\1**', text)
    text = re.sub(r'__(.+?)__', r'__\1__', text)
    text = re.sub(r'--(.+?)--', r'--\1--', text)
    text = re.sub(r'\|\|(.+?)\|\|', r'||\1||', text)
    text = re.sub(r'(.+?)\s*=\s*تگ\s+(https?://\S+)', r'[\1](\2)', text)
    return text

qa_data = load_data()
admins = load_admins()
conversation_state = None
temp_question = ""

# --- متن راهنمای مدیر ---
ADMIN_HELP = """راهنمای مدیر:

1) ذخیره سوال جدید:
   &&& رو بفرست، بعد سوال رو بنویس، بعد جواب رو بفرست.

2) مشاهده لیست سوالات:
   #### رو بفرست.

3) حذف یک سوال:
   شماره سوال + حذف سؤال
   مثال: 1 حذف سؤال

4) خروج از حالت مدیر:
   خروج رو بفرست.

نکته: پاسخ به سوالات برای همه کاربران آزاد است."""

# --- ساخت کلاینت ---
client = Client(auth=AUTH_KEY, private=PRIVATE_KEY)

@client.on_message()
def handler(message: Message):
    global qa_data, admins, conversation_state, temp_question

    try:
        sender_id = getattr(message, 'sender_id', None) or getattr(message, 'sender_guid', None)

        is_text = bool(message.text)
        is_file = bool(getattr(message, 'file', None)) or bool(getattr(message, 'photo', None)) or \
                  bool(getattr(message, 'video', None)) or bool(getattr(message, 'gif', None))

        # --- حالت‌های چند مرحله‌ای (فقط برای مدیرها) ---
        if conversation_state == "waiting_question":
            if sender_id not in admins:
                return
            if not is_text:
                safe_reply(message, "لطفاً متن سوال را بفرست.")
                return
            temp_question = message.text
            conversation_state = "waiting_answer"
            safe_reply(message, "سوال ذخیره شد. حالا جواب را بفرست:")
            return

        if conversation_state == "waiting_answer":
            if sender_id not in admins:
                return
            if is_text:
                qa_data[temp_question] = {"type": "text", "content": message.text}
                save_data(qa_data)
                safe_reply(message, "ذخیره شد.")
            elif is_file:
                try:
                    file_obj = None
                    for attr in ['file', 'photo', 'video', 'gif']:
                        if getattr(message, attr, None):
                            file_obj = getattr(message, attr)
                            break
                    if file_obj is None:
                        safe_reply(message, "فایل شناسایی نشد.")
                        return
                    file_name = f"file_{len(qa_data)}.dat"
                    file_path = os.path.join(UPLOAD_DIR, file_name)
                    if hasattr(message, 'download'):
                        message.download(file_path)
                    elif hasattr(file_obj, 'download'):
                        file_obj.download(file_path)
                    else:
                        safe_reply(message, "متد دانلود پیدا نشد.")
                        return
                    qa_data[temp_question] = {"type": "file", "content": file_path}
                    save_data(qa_data)
                    safe_reply(message, "فایل ذخیره شد.")
                except Exception as e:
                    safe_reply(message, f"خطا: {e}")
            else:
                safe_reply(message, "لطفاً متن یا فایل بفرست.")
            conversation_state = None
            temp_question = ""
            return

        if not is_text:
            return

        text = message.text.strip()

        # --- 1. بررسی رمز: هر کسی رمز رو بفرسته، مدیر میشه ---
        if text == ADMIN_PASSWORD:
            if sender_id not in admins:
                admins.add(sender_id)
                save_admins(admins)
                safe_reply(message, "شما به عنوان مدیر انتخاب شدید.\n\n" + ADMIN_HELP)
            else:
                safe_reply(message, "شما قبلاً به عنوان مدیر انتخاب شده‌اید.\n\n" + ADMIN_HELP)
            return

        # --- 2. خروج از حالت مدیر ---
        if text == "خروج" and sender_id in admins:
            admins.discard(sender_id)
            save_admins(admins)
            safe_reply(message, "از حالت مدیر خارج شدی.")
            return

        # --- 3. راهنما (فقط برای مدیرها) ---
        if text in ["راهنما", "help", "/help"] and sender_id in admins:
            safe_reply(message, ADMIN_HELP)
            return

        # --- 4. دستورات مدیریتی (فقط برای مدیرها) ---
        if sender_id in admins:
            if text == "&&&":
                conversation_state = "waiting_question"
                safe_reply(message, "لطفا سؤال را وارد کنید")
                return

            if text == "####":
                if not qa_data:
                    safe_reply(message, "هیچ سوالی ذخیره نشده است.")
                else:
                    list_text = "لیست سوال و جواب‌ها:\n" + "-" * 20 + "\n"
                    for idx, (q, a) in enumerate(qa_data.items(), 1):
                        if a["type"] == "text":
                            list_text += f"{idx}. سؤال: {q}\n   جواب: {a['content']}\n"
                        else:
                            list_text += f"{idx}. سؤال: {q}\n   جواب: [فایل]\n"
                    safe_reply(message, list_text)
                return

            delete_match = re.match(r"^(\d+)\s+حذف\s+سؤال$", text)
            if delete_match:
                idx = int(delete_match.group(1))
                if 1 <= idx <= len(qa_data):
                    keys = list(qa_data.keys())
                    q_del = keys[idx - 1]
                    if qa_data[q_del]["type"] == "file":
                        fp = qa_data[q_del]["content"]
                        if os.path.exists(fp):
                            os.remove(fp)
                    del qa_data[q_del]
                    save_data(qa_data)
                    safe_reply(message, f"سؤال «{q_del}» حذف شد.")
                else:
                    safe_reply(message, "شماره نامعتبر است.")
                return

        # --- 5. پاسخ خودکار به همه کاربران ---
        for question, answer_data in qa_data.items():
            if question in text:
                if answer_data["type"] == "text":
                    safe_reply(message, apply_formatting(answer_data["content"]))
                elif answer_data["type"] == "file":
                    fp = answer_data["content"]
                    if os.path.exists(fp):
                        try:
                            if hasattr(message, 'reply_file'):
                                message.reply_file(fp)
                            elif hasattr(client, 'send_file'):
                                client.send_file(message.chat_id, fp)
                        except Exception as e:
                            safe_reply(message, f"خطا: {e}")
                    else:
                        safe_reply(message, "فایل یافت نشد.")
                return

    except Exception as e:
        print(f"Handler error: {e}")

# --- اجرا ---
if __name__ == "__main__":
    print("ربات شروع به کار کرد...")
    client.run()
