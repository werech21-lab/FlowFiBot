import os
import json
import re
import gspread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_BOT_TOKEN = "8927028342:AAFmrHFBWIcOfpn4ix6AMFP6mNiG1n3vZ60"

SHEETS = {}
try:
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        gc = gspread.service_account_from_dict(creds_dict)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.path.join(base_dir, "credentials.json")
        gc = gspread.service_account(filename=creds_path)
    
    sheet_mapping = {
        "salaries": "Salaries",
        "sales": "Sales",
        "menu": "Menu",
        "expenses": "Expenses",
        "purchases": "Purchases",
        "deliveries": "Deliveries",
        "crm": "CRM"
    }
    
    for key, name in sheet_mapping.items():
        try:
            SHEETS[key] = gc.open(name).sheet1
        except Exception as sheet_err:
            print(f"⚠️ تنبيه: لم يتم فتح شيت '{name}': {sheet_err}")
            try:
                new_sheet = gc.create(name)
                SHEETS[key] = new_sheet.sheet1
                print(تم إنشاء شيت جديد: {name})
            except Exception as create_err:
                print(f"❌ فشل إنشاء شيت '{name}': {create_err}")
                
    print("✅ تم الاتصال بجميع ملفات Google Sheets بنجاح!")
except Exception as e:
    print(f"❌ خطأ فادح في الاتصال بجوجل شيتس: {e}")

def parse_message_locally(text: str):
    text_lower = text.lower()
    tab = "expenses" 
    
    if any(k in text_lower for k in ["بيع", "مبيعات", "طلب", "طلبات", "sales", "order", "زبون", "فاتورة بيع", "سعر الواحدة", "شاورما"]):
        tab = "sales"
    elif any(k in text_lower for k in ["راتب", "رواتب", "موظف", "salary", "salaries", "أجور", "اجور"]):
        tab = "salaries"
    elif any(k in text_lower for k in ["منيو", "قائمة", "صنف", "صنف جديد", "menu", "item", "وجبة", "مشروب", "بطاطة", "شيبس"]):
        tab = "menu"
    elif any(k in text_lower for k in ["مشتريات", "شراء", "مورد", "purchases", "stock", "بضاعة", "مواد خام"]):
        tab = "purchases"
    elif any(k in text_lower for k in ["توصيل", "دليفري", "سائق", "delivery", "driver", "شحن"]):
        tab = "deliveries"
    elif any(k in text_lower for k in ["عميل", "شكوى", "ملاحظة", "crm", "client", "feedback", "اتصال", "تواصل"]):
        tab = "crm"
    elif any(k in text_lower for k in ["مصروف", "إيجار", "فاتورة", "expenses", "bill", "rent", "كهرباء", "ماء"]):
        tab = "expenses"

    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    amount = numbers[0] if numbers else ""
    
    currency = ""
    for curr in ["دينار", "دولار", "ريال", "درهم", "usd", "kwd", "sar", "aed"]:
        if curr in text_lower:
            currency = curr
            break

    clean_text = text
    words_to_remove = ["ضيف", "اضف", "أضف", "راتب", "مبلغ", "مصروف", "شراء", "مشتريات", "طلب", "طلبات", "صنف", "منيو", "توصيل", "عميل", "بيع", "مبيعات", "سعر", "الواحدة", "دينار", "دولار", "ريال", "درهم"]
    for w in words_to_remove:
        clean_text = clean_text.replace(w, "")
    for num in numbers:
        clean_text = clean_text.replace(num, "")
    
    name_or_detail = clean_text.strip()

    return {
        "tab": tab,
        "row": [name_or_detail, amount, currency, text]
    }

async def save_to_sheet(data, update: Update):
    if not data or "tab" not in data:
        await update.message.reply_text("⚠️ لم أتمكن من فهم أو تصنيف البيانات.")
        return

    tab_name = data.get("tab", "").lower()
    row_values = data.get("row", [])

    target_sheet = SHEETS.get(tab_name)
    
    if target_sheet:
        try:
            target_sheet.append_row(row_values)
            await update.message.reply_text(f"✅ تم حفظ البيانات وتوزيعها بنجاح في قسم: `{tab_name.upper()}` 📊", parse_mode="Markdown")
        except Exception as e:
            # إرسال سبب الخطأ الحقيقي مباشرة في تليجرام لنراه بوضوح
            await update.message.reply_text(f"⚠️ خطأ أثناء الكتابة: {str(e)}")
    else:
        await update.message.reply_text(f"⚠️ الشيت غير موجود في الذاكرة (القائم: {list(SHEETS.keys())})")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return
    
    data = parse_message_locally(user_text)
    await save_to_sheet(data, update)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))
    print("🚀 FlowFi Cloud Bot (Debug Mode) is up and running!")
    app.run_polling()
