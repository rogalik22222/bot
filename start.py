import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, CallbackContext
from report_handler import date_from_report, date_to_report, nicknames_report, cancel_report
from invite_handler import *
from online_handler import (
    check_start as online_check_start,
    date_from as online_date_from,
    date_to as online_date_to,
    nicknames as online_nicknames,
    online_cancel,
)
from trade_handler import (
    check_start as trade_check_start,
    date_from as trade_date_from,
    date_to as trade_date_to,
    nicknames as trade_nicknames,
    cancel as trade_cancel,
)
from check_handler import get_conversation_handler, check_start as c_start
from account_handler import accountc_handler, account_start, NICKNAMES
from accountban_handler import accountcc_handler, account_start as a_start
from database import init_db, add_user, get_user_role, update_user_role, get_all_users, delete_user
from dostups import *
import sqlite3
from config import *
from accountban_handler import accountcc_handler, account_start as acc_start
from uval_handler import *
from gospay_handler import check_start as gos_start, date_from_gos,  date_to_gos, get_fraction, FRACTION


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)

    if not role:
        await update.message.reply_text(
            "Вы не зарегистрированы. Используйте /register для регистрации."
        )
        return
    elif role == "removed":
        await update.message.reply_text(
            "Ваш аккаунт был удалён, обратитесь к создателю для решения проблемы"
        )
        return

    reply_keyboard = [
        ["Работа с аккаунтами🤖", "Для следящих☠️"],
        ["Управление аккаунтами🔧"],
        ["Проверка кандидатов1️⃣3️⃣$"],
    ]

    # Настройка кнопок на основе роли
    if role == "sled":
        reply_keyboard = [
            ["Проверить онлайн⏰", "Проверить привязки🔗", "Для следящих☠️"],
        ]
        reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True
        )

    elif role == "admin":
        reply_keyboard = [
            ["Работа с аккаунтами🤖", "Для следящих☠️"  ],
            ["Проверка кандидатов1️⃣3️⃣"],
        ]
        reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True
        )

    elif role == "tech":
        reply_keyboard = [
            ["Работа с аккаунтами🤖", "Для следящих☠️"  ],
        ]
        reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True
        )

    elif role == "developer":
        reply_keyboard = [
            ["Работа с аккаунтами🤖", "Для следящих☠️"],
            ["Управление аккаунтами🔧", "Проверка кандидатов1️⃣3️⃣"],

        ]
        reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True
        )
    elif role == "registered" or not role:
        reply_keyboard = [["/start"]]
        reply_markup = ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True
        )

    await update.message.reply_text(
        "Выберите действие:", reply_markup=reply_markup
    )