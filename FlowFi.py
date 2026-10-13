import os
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_BOT_TOKEN = "8927028342:AAFmrHFBWIcOfpn4ix6AMFP6mNiG1n3vZ60"

# رابط الـ Web App الخاص بك
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzBW6BRJDxw_XxxwghNa0WijRUzkPnQQIzoGeOZgY83NPamAWe6_L4RfEk6p7CWKGRZ/exec"
SECRET_KEY = "FlowFi-1_Secret_2026"

def parse_message_locally(text: str):
    text_lower = text.lower()
    tab = "Expenses" 
    
    if any(k in text_lower for k in ["بيع", "مبيعات", "طلب", "طلبات", "sales", "order", "زبون", "فاتورة بيع", "سعر الواحدة", "شاورما"]):
        tab = "Sales"
    elif any(k in text_lower for k in ["راتب", "رواتب", "موظف", "salary", "salaries", "أجور", "اجور"]):
        tab = "Salaries"
    elif any(k in text_lower for k in ["منيو", "قائمة", "صنف", "صنف جديد", "menu", "item", "وجبة", "مشروب", "بطاطة", "شيبس"]):
        tab = "Menu"
    elif any(k in text_lower for k in ["مشتريات", "شراء", "مورد", "purchases", "stock", "بضاعة", "مواد خام"]):
        tab = "Purchases"
    elif any(k in text_lower for k in ["توصيل", "دليفري", "سائق", "delivery", "driver", "شحن"]):
        tab = "Deliveries"
    elif any(k in text_lower for k in ["عميل", "شكوى", "ملاحظة", "crm", "client", "feedback", "اتصال", "تواصل"]):
        tab = "CRM"
    elif any(k in text_lower for k in ["مصروف", "إيجار", "فاتورة", "expenses", "bill", "rent", "كهرباء", "ماء"]):
        tab = "Expenses"

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
        "secret_key": SECRET_KEY,
        "tab": tab,
        "row": [name_or_detail, f"{amount} {currency}".strip(), text]
    }

async def save_to_sheet(data, update: Update):
    if not data or "tab" not in data:
        await update.message.reply_text("⚠️ لم أتمكن من فهم أو تصنيف البيانات.")
        return

    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=data, timeout=20)
        
        if response.status_code != 200:
            await update.message.reply_text(f"⚠️ خطأ في الخادم (Code {response.status_code})")
            return
            
        res_json = response.json()
        
        if res_json.get("status") == "success":
            tab_name = data.get("tab")
            await update.message.reply_text(f"✅ تم حفظ البيانات بنجاح في قسم: `{tab_name}` 📊", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ مرفوض: لا تمتلك صلاحية الوصول لهذا البوت.")
    except Exception as e:
        await update.message.reply_text("⚠️ خطأ في الاتصال بالخدمة.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return
    
    data = parse_message_locally(user_text)
    await save_to_sheet(data, update)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))
    print("🚀 FlowFi WebApp Bot is up and running!")
    app.run_polling()
