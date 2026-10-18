import re
import datetime
import os
import asyncio
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from google import genai
import openai
import anthropic

# ==========================================
# 1. إعداد المتغيرات البيئية والمفاتيح (Secure Environment Variables)
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")

gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"⚠️ Gemini Init Error: {e}")

openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"⚠️ OpenAI Init Error: {e}")

claude_client = None
if CLAUDE_API_KEY:
    try:
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    except Exception as e:
        print(f"⚠️ Claude Init Error: {e}")

# مسارات العمل السحابية المتوافقة مع Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE_PATH = os.path.join(BASE_DIR, "FlowFi_Database.xlsx")
INVOICES_DIR = os.path.join(BASE_DIR, "FlowFi_Invoices")
BACKUPS_DIR = os.path.join(BASE_DIR, "FlowFi_Backups")

os.makedirs(INVOICES_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# ==========================================
# 2. إدارة القيود والنسخ الاحتياطي
# ==========================================
def backup_database():
    if os.path.exists(EXCEL_FILE_PATH):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUPS_DIR, f"FlowFi_Database_Backup_{timestamp}.xlsx")
        try:
            df_dict = pd.read_excel(EXCEL_FILE_PATH, sheet_name=None)
            with pd.ExcelWriter(backup_path, engine='openpyxl') as writer:
                for sheet, df in df_dict.items():
                    df.to_excel(writer, sheet_name=sheet, index=False)
        except Exception as e:
            print(f"Backup Error: {e}")

def get_next_entry_number():
    if not os.path.exists(EXCEL_FILE_PATH):
        return "JE-1001"
    try:
        excel_file = pd.ExcelFile(EXCEL_FILE_PATH)
        max_id = 1000
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=sheet_name)
            if "رقم القيد" in df.columns:
                for val in df["رقم القيد"].dropna():
                    match = re.search(r'\d+', str(val))
                    if match:
                        num = int(match.group())
                        if num > max_id:
                            max_id = num
        return f"JE-{max_id + 1}"
    except Exception:
        return f"JE-{datetime.datetime.now().strftime('%H%M%S')}"

# ==========================================
# 3. التحليل المتقدم الموحد (Hybrid Triple AI Engine)
# ==========================================
async def parse_multimodal_input(text_prompt=None, image_bytes=None, audio_bytes=None):
    prompt_instruction = """
أنت المستشار المحاسبي الذكي لنظام إدارة متجر (FlowFi ERP).
قم بتحليل المدخلات المرفقة (نص، صورة فاتورة/إيصال، أو تسجيل صوتي) واستخرج البيانات بالترتيب الدقيق باللغة العربية:

قواعد اختيار التبويبات:
- المبيعات: ["Sales"]
- الموظفين والرواتب: ["Salaries", "Employee Database"]
- الموردين والمشتريات والمصاريف: ["Suppliers", "Expenses"]

صيغة الإجابة المطلوبة بالضبط:
التبويبات: [اسم التبويبات]
التفاصيل: [اسم أو وصف التفاصيل والأصناف والكميات بوضوح]
المبلغ: [المبلغ الإجمالي مع العملة]
طريقة الدفع: [كاش / كي نت / تحويل / آجل / غير محدد]
حالة السداد: [مدفوع / مستحق / ذمم]
"""

    res_text = ""
    
    if gemini_client:
        try:
            contents = [prompt_instruction]
            if image_bytes:
                contents.append({"mime_type": "image/jpeg", "data": image_bytes})
            if audio_bytes:
                contents.append({"mime_type": "audio/ogg", "data": audio_bytes})
            if text_prompt:
                contents.append(f"نص التاجر: {text_prompt}")

            response = gemini_client.models.generate_content(model='gemini-3.8-flash', contents=contents)
            res_text = response.text.strip()
        except Exception as e:
            print(f"Gemini Error: {e}")

    if not res_text and openai_client and text_prompt and not image_bytes and not audio_bytes:
        try:
            completion = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": prompt_instruction}, {"role": "user", "content": text_prompt}]
            )
            res_text = completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI Error: {e}")

    if not res_text and claude_client and text_prompt:
        try:
            message = claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                system=prompt_instruction,
                messages=[{"role": "user", "content": text_prompt}]
            )
            res_text = message.content[0].text.strip()
        except Exception as e:
            print(f"Claude Error: {e}")

    tabs = ["Suppliers", "Expenses"]
    if "Sales" in res_text:
        tabs = ["Sales"]
    elif "Salaries" in res_text:
        tabs = ["Salaries", "Employee Database"]

    details = text_prompt or "حركة مالية مسجلة"
    amount = "غير محدد"
    payment_method = "كاش"
    payment_status = "مدفوع"

    for line in res_text.split('\n'):
        if "التفاصيل:" in line:
            details = line.split("التفاصيل:")[1].strip().strip("[]")
        elif "المبلغ:" in line:
            amount = line.split("المبلغ:")[1].strip().strip("[]")
        elif "طريقة الدفع:" in line:
            payment_method = line.split("طريقة الدفع:")[1].strip().strip("[]")
        elif "حالة السداد:" in line:
            payment_status = line.split("حالة السداد:")[1].strip().strip("[]")

    if (amount == "غير محدد" or not amount) and text_prompt:
        nums = re.findall(r'\d+(?:\.\d+)?', text_prompt)
        if nums:
            amount = nums[0] + " دينار"

    return {
        "tabs": tabs,
        "details": details,
        "amount": amount,
        "payment_method": payment_method,
        "payment_status": payment_status,
        "full_text": text_prompt or "مستند/صوت مرفق"
    }

# ==========================================
# 4. معالجة رسائل تيليجرام
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    user_text = message.text or message.caption or ""
    image_bytes = None
    audio_bytes = None

    if message.voice:
        voice_file = await message.voice.get_file()
        audio_bytes = await voice_file.download_as_bytearray()
    elif message.photo:
        photo_file = await message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()

    user_text_lower = user_text.lower().strip()
    question_keywords = ["من", "ما", "كم", "متى", "آخر", "اعطيني", "اعطني", "وين", "إيش", "ايش", "تقرير", "بحث", "هل", "كيف", "تنبيه", "ميزانية", "رسم"]
    is_question = (any(q in user_text_lower for q in question_keywords) or user_text.endswith("؟") or user_text.endswith("?")) and not any(k in user_text_lower for k in ["موظف", "راتب", "شراء", "مصروف", "إيجار", "صندوق", "مبيعات", "مورد", "فاتورة", "بيع"])

    if is_question and not image_bytes and not audio_bytes:
        excel_context = ""
        if os.path.exists(EXCEL_FILE_PATH):
            excel_file = pd.ExcelFile(EXCEL_FILE_PATH)
            for sn in excel_file.sheet_names:
                df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=sn)
                if not df.empty:
                    excel_context += f"\n--- {sn} ---\n{df.to_string(index=False)}\n"
        
        prompt = f"بيانات المتجر:\n{excel_context}\n\nسؤال التاجر:\n{user_text}\n\nقدم تحليلاً مالياً شاملاً ومختصراً باللغة العربية."
        try:
            if openai_client:
                res = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                ans = res.choices[0].message.content
            elif gemini_client:
                res = gemini_client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
                ans = res.text
            else:
                ans = "⚠️ يتعذر الاتصال بمحركات الذكاء الاصطناعي حالياً."
            await message.reply_text(ans)
        except Exception as e:
            await message.reply_text(f"⚠️ خطأ: {e}")
    else:
        parsed_data = await parse_multimodal_input(
            text_prompt=user_text if user_text else None,
            image_bytes=bytes(image_bytes) if image_bytes else None,
            audio_bytes=bytes(audio_bytes) if audio_bytes else None
        )
        
        target_tabs = parsed_data["tabs"]
        entry_number = get_next_entry_number()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        invoice_ref = "لا يوجد"
        if image_bytes:
            invoice_filename = f"{entry_number}_Invoice.jpg"
            saved_img_path = os.path.join(INVOICES_DIR, invoice_filename)
            with open(saved_img_path, "wb") as f:
                f.write(image_bytes)
            invoice_ref = invoice_filename

        row_dict = {
            "رقم القيد": entry_number,
            "التاريخ والوقت": current_time,
            "التفاصيل": parsed_data.get("details"),
            "المبلغ": parsed_data.get("amount"),
            "طريقة الدفع": parsed_data.get("payment_method"),
            "حالة السداد": parsed_data.get("payment_status"),
            "النص الكامل": user_text or f"صورة/صوت ({invoice_ref})"
        }

        try:
            new_row_df = pd.DataFrame([row_dict])
            saved_tabs = []
            
            for tab_name in target_tabs:
                if os.path.exists(EXCEL_FILE_PATH):
                    with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                        try:
                            existing_df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=tab_name)
                            cols = ["رقم القيد", "التاريخ والوقت", "التفاصيل", "المبلغ", "طريقة الدفع", "حالة السداد", "النص الكامل"]
                            for c in cols:
                                if c not in existing_df.columns:
                                    existing_df[c] = ""
                            existing_df = existing_df[cols]
                            updated_df = pd.concat([existing_df, new_row_df[cols]], ignore_index=True)
                            updated_df.to_excel(writer, sheet_name=tab_name, index=False)
                        except ValueError:
                            new_row_df.to_excel(writer, sheet_name=tab_name, index=False)
                else:
                    with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl') as writer:
                        new_row_df.to_excel(writer, sheet_name=tab_name, index=False)
                saved_tabs.append(tab_name)

            backup_database()

            tabs_str = " و ".join(saved_tabs)
            await message.reply_text(
                f"✅ تم التوثيق والقيد بنجاح عبر السحابة!\n"
                f"🔖 رقم القيد: {entry_number}\n"
                f"📂 التبويبات: {tabs_str}\n"
                f"📝 التفاصيل: {parsed_data.get('details')}\n"
                f"💰 المبلغ: {parsed_data.get('amount')} | 💳 الدفع: {parsed_data.get('payment_method')}\n"
                f"🤖 المحركات النشطة: Gemini + OpenAI + Claude"
            )
        except Exception as e:
            await message.reply_text(f"⚠️ خطأ أثناء الحفظ: {e}")

# ==========================================
# 5. التشغيل السحابي الرئيسي 24/7
# ==========================================
async def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is missing!")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE) & (~filters.COMMAND), handle_message))
    
    print("🚀 FlowFi Multi-AI Cloud Engine is starting...")
    
    connected = False
    while not connected:
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            print("✅ FlowFi ERP is live and running 24/7!")
            connected = True
        except Exception as e:
            print(f"⚠️ Retrying connection: {e}")
            await asyncio.sleep(5)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
