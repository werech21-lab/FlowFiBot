import os
import re
import gspread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_BOT_TOKEN = "8927028342:AAFmrHFBWIcOfpn4ix6AMFP6mNiG1n3vZ60"

# --- الاتصال الآمن والمباشر بملف credentials.json ---
gc = None
try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(base_dir, "credentials.json")
    gc = gspread.service_account(filename=creds_path)
    print("✅ تم تحميل بيانات الاعتماد بنجاح!")
except Exception as e:
    print(f"❌ خطأ في تحميل ملف الاعتماد: {e}")

SHEET_MAPPING = {
    "sales": "Sales",
    "expenses": "Expenses",
    "salaries": "Salaries",
    "menu": "Menu",
    "purchases": "Purchases",
    "deliveries": "Deliveries",
    "crm": "CRM"
}

def get_target_sheet(tab_name):
    if not gc:
        return None, "لم يتم تهيئة الاتصال بـ gspread"
    
    sheet_title = SHEET_MAPPING.get(tab_name, "Expenses")
    try:
        # محاولة فتح الشيت الموجود
        sh = gc.open(sheet_title)
        return sh.sheet1, None
    except gspread.exceptions.SpreadsheetNotFound:
        try:
            # إذا لم يكن موجوداً، قم بإنشائه تلقائياً
            sh = gc.create(sheet_title)
            return sh.sheet1, None
        except Exception as create_err:
            return None, str(create_err)
    except Exception as e:
        return None, str(e)

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

    target_sheet, err_msg = get_target_sheet(tab_name)

    if target_sheet:
        try:
            target_sheet.append_row(row_values)
            await update.message.reply_text(f"✅ تم حفظ البيانات وتوزيعها بنجاح في قسم: `{tab_name.upper()}` 📊", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"⚠️ خطأ أثناء الكتابة: {e}")
    else:
        # إرسال السبب التقني الحقيقي لنعرفه فوراً
        await update.message.reply_text(f"⚠️ خطأ ربط الشيت: {err_msg}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return
    
    data = parse_message_locally(user_text)
    await save_to_sheet(data, update)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))
    print("🚀 FlowFi Bot is up and running!")
    app.run_polling()
