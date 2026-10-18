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

# تهيئة العملاء الذكيين بشكل آمن
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"⚠️ Gemini Client Init Error: {e}")

openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"⚠️ OpenAI Client Init Error: {e}")

claude_client = None
if CLAUDE_API_KEY:
    try:
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    except Exception as e:
        print(f"⚠️ Claude Client Init Error: {e}")

# مسارات التخزين
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop") if os.path.exists(os.path.join(os.path.expanduser("~"), "Desktop")) else "."
EXCEL_FILE_PATH = os.path.join(DESKTOP_PATH, "FlowFi_Database.xlsx")
INVOICES_DIR = os.path.join(DESKTOP_PATH, "FlowFi_Invoices")
BACKUPS_DIR = os.path.join(DESKTOP_PATH, "FlowFi_Backups")

os.makedirs(INVOICES_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# ==========================================
# 2. وظائف إدارة القيود والنسخ الاحتياطي
# ==========================================
def backup_database():
    """إنشاء نسخة احتياطية من قاعدة البيانات"""
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
    """توليد رقم قيد تسلسلي فريد"""
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
قم بتحليل المدخلات المرفقة (نص، صورة فاتورة/إيصال، أو تسجيل صوتي) بذكاء واستخرج البيانات التالية بالترتيب الدقيق باللغة العربية:

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
    
    # 1. المحاولة الأولى عبر Gemini (ممتاز للصور والصوتيات)
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
            print(f"Gemini Engine Fallback: {e}")

    # 2. المحاولة الثانية عبر OpenAI (للنصوص والتحليل الفوري)
    if not res_text and openai_client and text_prompt and not image_bytes and not audio_bytes:
        try:
            completion = openai_client.chat.completions.
