# -*- coding: utf-8 -*-
"""
ربات تلگرام فروشگاه اریو (ARIO)
قابلیت‌ها:
  1. ثبت کامل سفارش مشتری (نام، تلفن، آدرس، محصول، رنگ، سایز، تعداد، رسید پرداخت)
  2. ثبت تاریخ تولد مشتری و ارسال خودکار کد تخفیف در ماه تولد
  3. اطلاع‌رسانی سفارش جدید به ادمین

نویسنده: ساخته‌شده برای فروشگاه ARIO
"""

import json
import logging
import os
from datetime import datetime, date

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ============================================================
#                       تنظیمات اصلی
# ============================================================
# توکن ربات رو از @BotFather بگیر و اینجا جایگزین کن
BOT_TOKEN = os.environ.get("ARIO_BOT_TOKEN", "8989037865:AAEl5cX9Akdltt95CF5ujHHTozeekBk7skk")

# آیدی عددی ادمین‌ها (می‌تونی یک نفر یا چند نفر رو اضافه کنی) که سفارش‌های
# جدید براشون ارسال می‌شه. برای گرفتن آیدی عددی هر نفر، اون شخص باید به ربات
# @userinfobot پیام بده و عددی که می‌گیره رو به تو بده.
#
# برای چند ادمین، آیدی‌ها رو با کاما (,) از هم جدا کن، مثلاً:
# ARIO_ADMIN_CHAT_IDS=123456789,987654321
_admin_ids_raw = os.environ.get("ARIO_ADMIN_CHAT_IDS", "5592475327,8924074276")
ADMIN_CHAT_IDS = [
    x.strip() for x in _admin_ids_raw.split(",") if x.strip() and x.strip() != "PUT_YOUR_NUMERIC_CHAT_ID_HERE"
]

# فایلی که اطلاعات سفارش‌ها و مشتری‌ها توش ذخیره می‌شه
DATA_FILE = os.path.join(os.path.dirname(__file__), "ario_data.json")

# محصولات موجود فروشگاه (می‌تونی خودت ویرایش کنی)
PRODUCTS = {
    "1": {"name": "سویشرت Rhude - قهوه‌ای", "price": 1700000},
    "2": {"name": "سویشرت Rhude - سبز", "price": 1700000},
    "3": {"name": "هودی Masterpiece - سرمه‌ای", "price": 1700000},
    "4": {"name": "هودی Masterpiece - طوسی", "price": 1700000},
}

SIZES = ["S", "M", "L", "XL"]

# درصد تخفیف تولد
BIRTHDAY_DISCOUNT_PERCENT = 15

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
#                   مراحل مکالمه (Conversation States)
# ============================================================
(
    NAME,
    PHONE,
    ADDRESS,
    PRODUCT,
    SIZE,
    QUANTITY,
    RECEIPT,
    BIRTHDAY,
    CONFIRM,
) = range(9)


# ============================================================
#                     توابع کمکی ذخیره‌سازی
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"orders": [], "customers": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
#                     شروع مکالمه سفارش
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "سلام 🖤 به ربات سفارش‌گیری ARIO خوش اومدی!\n\n"
        "برای ثبت سفارش جدید، لطفاً اسم و فامیلت رو بنویس:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("شماره تماست رو بنویس (مثلاً 09123456789):")
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text(
        "آدرس کامل رو بنویس (شهر، خیابان، پلاک، کدپستی):"
    )
    return ADDRESS


async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text.strip()

    product_list = "\n".join(
        f"{key}. {p['name']} - {p['price']:,} تومان" for key, p in PRODUCTS.items()
    )
    await update.message.reply_text(
        f"کدوم محصول رو می‌خوای؟ شماره‌شو بفرست:\n\n{product_list}"
    )
    return PRODUCT


async def get_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice not in PRODUCTS:
        await update.message.reply_text(
            "❌ شماره نامعتبره. لطفاً یکی از شماره‌های بالا رو بفرست."
        )
        return PRODUCT

    context.user_data["product_key"] = choice
    context.user_data["product_name"] = PRODUCTS[choice]["name"]
    context.user_data["product_price"] = PRODUCTS[choice]["price"]

    keyboard = ReplyKeyboardMarkup([SIZES], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("سایز مورد نظرت چیه؟", reply_markup=keyboard)
    return SIZE


async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    size = update.message.text.strip().upper()
    if size not in SIZES:
        await update.message.reply_text("❌ سایز نامعتبره. یکی از گزینه‌های داده‌شده رو انتخاب کن.")
        return SIZE

    context.user_data["size"] = size
    await update.message.reply_text(
        "چند عدد می‌خوای؟ (فقط عدد بفرست، مثلاً 1)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return QUANTITY


async def get_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ لطفاً یه عدد معتبر بفرست (مثلاً 1 یا 2).")
        return QUANTITY

    context.user_data["quantity"] = int(text)
    total = context.user_data["product_price"] * context.user_data["quantity"]
    context.user_data["total_price"] = total

    await update.message.reply_text(
        f"مبلغ قابل پرداخت: {total:,} تومان\n\n"
        "بعد از واریز، لطفاً عکس رسید پرداخت رو همینجا ارسال کن:"
    )
    return RECEIPT


async def get_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        # آخرین (بزرگ‌ترین) نسخه عکس رو ذخیره می‌کنیم
        file_id = update.message.photo[-1].file_id
        context.user_data["receipt_file_id"] = file_id
    else:
        await update.message.reply_text("❌ لطفاً رسید رو به‌صورت عکس ارسال کن.")
        return RECEIPT

    await update.message.reply_text(
        "تاریخ تولدت رو به فرم روز/ماه بنویس (مثلاً 15/06) تا تو ماه تولدت "
        f"کد تخفیف {BIRTHDAY_DISCOUNT_PERCENT}٪ برات بفرستیم 🎂\n\n"
        "اگه نمی‌خوای این اطلاعات رو بدی، بنویس: رد شو"
    )
    return BIRTHDAY


async def get_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "رد شو":
        context.user_data["birthday"] = text
    else:
        context.user_data["birthday"] = None

    summary = build_order_summary(context.user_data)
    keyboard = ReplyKeyboardMarkup(
        [["✅ تایید نهایی", "❌ لغو"]], one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text(
        f"لطفاً اطلاعات رو چک کن:\n\n{summary}", reply_markup=keyboard
    )
    return CONFIRM


def build_order_summary(d):
    return (
        f"👤 نام: {d.get('name')}\n"
        f"📞 تلفن: {d.get('phone')}\n"
        f"📍 آدرس: {d.get('address')}\n"
        f"🛍 محصول: {d.get('product_name')}\n"
        f"📏 سایز: {d.get('size')}\n"
        f"🔢 تعداد: {d.get('quantity')}\n"
        f"💰 مبلغ کل: {d.get('total_price'):,} تومان\n"
        f"🎂 تولد: {d.get('birthday') or 'ثبت نشد'}"
    )


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text != "✅ تایید نهایی":
        await update.message.reply_text(
            "سفارش لغو شد. هر وقت خواستی دوباره با /start شروع کن.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    data = load_data()
    user = update.effective_user

    order = {
        "order_id": len(data["orders"]) + 1,
        "telegram_user_id": user.id,
        "telegram_username": user.username,
        "name": context.user_data.get("name"),
        "phone": context.user_data.get("phone"),
        "address": context.user_data.get("address"),
        "product_name": context.user_data.get("product_name"),
        "size": context.user_data.get("size"),
        "quantity": context.user_data.get("quantity"),
        "total_price": context.user_data.get("total_price"),
        "receipt_file_id": context.user_data.get("receipt_file_id"),
        "birthday": context.user_data.get("birthday"),
        "created_at": datetime.now().isoformat(),
        "status": "در انتظار تایید",
    }
    data["orders"].append(order)

    # ذخیره یا آپدیت اطلاعات مشتری برای سیستم تخفیف تولد
    if context.user_data.get("birthday"):
        data["customers"][str(user.id)] = {
            "name": context.user_data.get("name"),
            "birthday": context.user_data.get("birthday"),
            "last_discount_year_sent": None,
        }

    save_data(data)

    await update.message.reply_text(
        "✅ سفارشت با موفقیت ثبت شد!\n"
        "به‌محض تایید رسید پرداخت، براش پیام میدیم و ارسال می‌کنیم 🖤\n\n"
        "ممنون که از ARIO خرید کردی.",
        reply_markup=ReplyKeyboardRemove(),
    )

    # اطلاع‌رسانی به همه‌ی ادمین‌ها (یک یا چند نفر) با دکمه تایید سفارش
    summary = build_order_summary(order)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ تایید شد", callback_data=f"confirm_{order['order_id']}")]]
    )
    admin_messages = []
    for admin_id in ADMIN_CHAT_IDS:
        try:
            msg = await context.bot.send_message(
                chat_id=admin_id,
                text=f"🆕 سفارش جدید (#{order['order_id']}):\n\n{summary}\n\n🔴 وضعیت: در انتظار تایید",
                reply_markup=keyboard,
            )
            admin_messages.append({"chat_id": admin_id, "message_id": msg.message_id})
            if order.get("receipt_file_id"):
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=order["receipt_file_id"],
                    caption=f"رسید پرداخت سفارش #{order['order_id']}",
                )
        except Exception as e:
            logger.error(f"خطا در ارسال سفارش به ادمین {admin_id}: {e}")

    # آیدی پیام‌های ادمین‌ها رو ذخیره می‌کنیم تا موقع تایید، همه‌شون آپدیت بشن
    data = load_data()
    for o in data["orders"]:
        if o["order_id"] == order["order_id"]:
            o["admin_messages"] = admin_messages
            break
    save_data(data)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سفارش لغو شد. هر وقت خواستی با /start دوباره شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ============================================================
#         مدیریت کلیک روی دکمه "تایید شد" (برای چند ادمین)
# ============================================================
async def handle_confirm_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # به تلگرام میگه کلیک دریافت شد

    order_id = int(query.data.split("_")[1])
    admin_user = query.from_user

    data = load_data()
    order = next((o for o in data["orders"] if o["order_id"] == order_id), None)

    if not order:
        await query.answer("❌ این سفارش پیدا نشد.", show_alert=True)
        return

    # اگه قبلاً یه ادمین دیگه تاییدش کرده باشه
    if order.get("status") == "تایید شد":
        confirmer = order.get("confirmed_by", "یکی از ادمین‌ها")
        await query.answer(f"این سفارش قبلاً توسط {confirmer} تایید شده ✅", show_alert=True)
        return

    # ثبت تایید
    admin_name = admin_user.full_name or admin_user.username or "ادمین"
    order["status"] = "تایید شد"
    order["confirmed_by"] = admin_name
    order["confirmed_at"] = datetime.now().isoformat()
    save_data(data)

    summary = build_order_summary(order)
    new_text = (
        f"🆕 سفارش (#{order_id}):\n\n{summary}\n\n"
        f"✅ وضعیت: تایید شد توسط {admin_name}"
    )

    # پیام رو تو چت همه ادمین‌ها آپدیت می‌کنیم و دکمه رو حذف می‌کنیم
    for msg_info in order.get("admin_messages", []):
        try:
            await context.bot.edit_message_text(
                chat_id=msg_info["chat_id"],
                message_id=msg_info["message_id"],
                text=new_text,
            )
        except Exception as e:
            logger.error(f"خطا در آپدیت پیام ادمین: {e}")


# ============================================================
#              بررسی روزانه تولد و ارسال کد تخفیف
# ============================================================
async def check_birthdays(context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع هر روز اجرا می‌شه و چک می‌کنه امروز تولد کدوم مشتری‌هاست.
    اگه امروز روز تولد کسی بود، کد تخفیف براش ارسال می‌شه.
    فرمت ذخیره‌شده تاریخ تولد: روز/ماه (مثلاً 15/06)
    """
    data = load_data()
    today = date.today()
    today_str = f"{today.day:02d}/{today.month:02d}"
    current_year = today.year

    changed = False
    for user_id, customer in data["customers"].items():
        bday = customer.get("birthday")
        if not bday:
            continue

        if bday == today_str and customer.get("last_discount_year_sent") != current_year:
            code = f"BDAY{user_id[-4:]}"
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=(
                        f"🎉 تولدت مبارک {customer.get('name', '')}! 🎂\n\n"
                        f"از طرف ARIO یه هدیه برات داریم:\n"
                        f"کد تخفیف {BIRTHDAY_DISCOUNT_PERCENT}٪ ویژه تولدت:\n\n"
                        f"🎁 {code}\n\n"
                        "این کد رو موقع سفارش بعدی به ادمین بگو 🖤"
                    ),
                )
                customer["last_discount_year_sent"] = current_year
                changed = True
                logger.info(f"کد تخفیف تولد برای {user_id} ارسال شد.")
            except Exception as e:
                logger.error(f"خطا در ارسال پیام تولد به {user_id}: {e}")

    if changed:
        save_data(data)


# ============================================================
#                         راه‌اندازی ربات
# ============================================================
def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        print("⚠️  لطفاً اول توکن ربات رو تو متغیر BOT_TOKEN یا ARIO_BOT_TOKEN قرار بده.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_size)],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_quantity)],
            RECEIPT: [MessageHandler(filters.PHOTO, get_receipt)],
            BIRTHDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthday)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_confirm_button, pattern=r"^confirm_\d+$"))

    # هر روز ساعت 10 صبح چک می‌کنه تولد کیه امروز
    job_queue = app.job_queue
    job_queue.run_daily(check_birthdays, time=datetime.strptime("10:00", "%H:%M").time())

    print("🚀 ربات ARIO روشن شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
