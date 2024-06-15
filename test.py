import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
from report_handler import date_from_report, date_to_report, nicknames_report, cancel_report
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
from dostups import tech_d, admin_d, full_d, registered_d, sled_d, developer_d
import sqlite3
from config import *


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

DATE_FROM, DATE_TO, NICKNAMES, SERVER, NICKNAME, DELETE_USER = range(6)


async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    await start(update, context)
    return ConversationHandler.END


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
        ["Выгрузка репорта📖", "Проверить онлайн⏰"],
        ["Проверить привязки🔗", "Проверить передачи🤑"],
        ["Проверить твинки🤡", "Проверка кандидатов1️⃣3️⃣"],
        ["Управление аккаунтами🔧"],
        ["/cancel"],
    ]

    # Настройка кнопок на основе роли
    if role == "sled":
        reply_keyboard = [["Выгрузка репорта📖", "Проверить онлайн⏰"], ["/cancel"]]
    elif role == "admin":
        reply_keyboard = [
            ["Выгрузка репорта📖", "Проверить онлайн⏰"],
            ["Проверить привязки🔗", "Проверить передачи🤑"],
            ["Проверить твинки🤡", "Проверка кандидатов1️⃣3️⃣"],
            ["/cancel"],
        ]
    elif role == "developer":
        reply_keyboard = [
            ["Выгрузка репорта📖", "Проверить онлайн⏰"],
            ["Проверить привязки🔗", "Проверить передачи🤑"],
            ["Проверить твинки🤡", "Проверка кандидатов1️⃣3️⃣"],
            ["Управление аккаунтами🔧"],
            ["/cancel"],
        ]
    elif role == "registered":
        reply_keyboard = [["Чё смотришь, пока без доступа"]]

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        ),
    )


async def register_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)

    if role == "registered":
        await update.message.reply_text(
            "Вы уже зарегистрированы и ожидаете подтверждения."
        )
        await start(update, context)
        return ConversationHandler.END

    # Проверяем, есть ли уже заявка
    if role is not None:
        await update.message.reply_text(
            "Ваша заявка уже отправлена на регистрацию. Ожидайте подтверждения."
        )
        await start(update, context)
        return ConversationHandler.END

    await update.message.reply_text("Напишите ваш Nick_name:")
    return NICKNAME


async def register_nickname(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)

    # Если уже есть заявка, использовать сохраненные данные
    if role == "registered":
        await update.message.reply_text(
            "Вы уже зарегистрированы и ожидаете подтверждения."
        )
        await start(update, context)
        return ConversationHandler.END

    nickname = update.message.text
    context.user_data["nickname"] = nickname

    # Сохраняем никнейм в базу данных для новой заявки
    await update.message.reply_text("Сервер от 1 до 7:")
    return SERVER


async def register_server(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)

    # Если уже есть заявка, использовать сохраненные данные
    if role == "registered":
        await update.message.reply_text(
            "Вы уже зарегистрированы и ожидаете подтверждения."
        )
        await start(update, context)
        return ConversationHandler.END

    server = update.message.text
    nickname = context.user_data.get("nickname")

    try:
        add_user(user_id, nickname, "registered", int(server))
        logging.info(f"Вы зарегистрированы и ожидаете подтверждения.")
    except sqlite3.IntegrityError:
        await update.message.reply_text(
            f"Ваш ник:{nickname},Заявка подана на сервер:{server}"
        )

    await start(update, context)
    return ConversationHandler.END


async def manage_accounts(update: Update, context: CallbackContext) -> None:
    reply_keyboard = [
        ["Список заявок", "Удалить пользователя"],
        ["Назад"],
    ]

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        ),
    )


async def list_pending_users(update: Update, context: CallbackContext):
    pending_users = get_all_users()  # Fetch users with 'registered' status
    pending_users = [user for user in pending_users if user[2] == "registered"]

    if not pending_users:
        await update.message.reply_text("Нет ожидающих заявок.")
        return

    for user in pending_users:
        await update.message.reply_text(
            f"User ID: {user[0]}\nNickname: {user[1]}\nServer: {user[3]}",
            reply_markup=ReplyKeyboardMarkup(
                [[f"Одобрить {user[0]}", f"Отказать {user[0]}", "Назад"]],
                one_time_keyboard=True,
            ),
        )


async def approve_user(update: Update, context: CallbackContext):
    user_id = int(context.matches[0].group(1))
    if get_user_role(update.message.from_user.id) != "developer":
        await update.message.reply_text("У вас нет прав для одобрения пользователей.")
        return
    update_user_role(user_id, "sled")
    await update.message.reply_text(
        f"Пользователь {user_id} одобрен и теперь имеет роль 'sled'."
    )


async def reject_user(update: Update, context: CallbackContext):
    user_id = int(context.matches[0].group(1))
    if get_user_role(update.message.from_user.id) != "admin":
        await update.message.reply_text("У вас нет прав для отклонения пользователей.")
        return
    update_user_role(user_id, "removed")
    await update.message.reply_text(
        f"Пользователь {user_id} отклонен и теперь имеет роль 'removed'."
    )


async def delete_user_start(update: Update, context: CallbackContext):
    await update.message.reply_text("Введите ID пользователя для удаления:")
    return DELETE_USER


async def delete_user_main(update: Update, context: CallbackContext):
    user_id = int(update.message.text)
    try:
        delete_user(user_id)
        await update.message.reply_text(f"Пользователь {user_id} удален.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при удалении пользователя: {e}")

    return ConversationHandler.END


async def list_users(update: Update, context: CallbackContext) -> None:
    users = get_all_users()
    response = "Список пользователей:\n"
    for user in users:
        response += f"ID: {user[0]}, Nickname: {user[1]}, Role: {user[2]}, Server: {user[3]}\n"
    await update.message.reply_text(response)


async def change_role(update: Update, context: CallbackContext) -> None:
    if get_user_role(update.message.from_user.id) != "admin":
        await update.message.reply_text("У вас нет прав для изменения роли пользователей.")
        return

    try:
        user_id, new_role = context.args
        user_id = int(user_id)
        update_user_role(user_id, new_role)
        await update.message.reply_text(f"Роль пользователя {user_id} изменена на {new_role}.")
    except ValueError:
        await update.message.reply_text("Использование: /change_role <user_id> <new_role>")


async def back_to_main(update: Update, context: CallbackContext) -> None:
    await start(update, context)


def main() -> None:
    init_db()

    application = Application.builder().token(API_KEY).build()

    report_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Выгрузка репорта📖$") & admin_d, date_from_report)],
        states={
            DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_from_report)],
            DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_to_report)],
            NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, nicknames_report)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    online_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Проверить онлайн⏰$") & developer_d, online_check_start)],
        states={
            DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, online_date_from)],
            DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, online_date_to)],
            NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, online_nicknames)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    trade_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Проверить передачи🤑$") & full_d, trade_check_start)],
        states={
            DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, trade_date_from)],
            DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, trade_date_to)],
            NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, trade_nicknames)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    register_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_nickname)],
            SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_server)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    delete_user_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Удалить пользователя$") & full_d, delete_user_start)],
        states={
            DELETE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user_main)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


    accban_handler = accountcc_handler()
    check_handler = get_conversation_handler()
    account_handler = accountc_handler()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list_users", list_users, filters=full_d))
    application.add_handler(CommandHandler("change_role", change_role, filters=full_d))
    application.add_handler(register_handler)
    application.add_handler(MessageHandler(filters.Regex("^Назад$"), back_to_main))
    application.add_handler(MessageHandler(filters.Regex("^Управление аккаунтами🔧$") & full_d, manage_accounts))

    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Список заявок$"), list_pending_users)],
        states={},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    application.add_handler(MessageHandler(filters.Regex("^Одобрить (\d+)$") & full_d, approve_user))
    application.add_handler(MessageHandler(filters.Regex("^Отказать (\д+)$") & full_d, reject_user))

    application.add_handler(delete_user_handler)

    application.add_handler(report_handler)
    application.add_handler(online_handler)
    application.add_handler(trade_handler)
    application.add_handler(check_handler)
    application.add_handler(account_handler)
    application.add_handler(accban_handler)

    application.run_polling()



if __name__ == "__main__":
    main()

