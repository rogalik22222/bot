import logging
import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, ContextTypes
from database import get_user_role

# Настройка логгера
logger = logging.getLogger()

# Константа для идентификатора роли пользователя
ROLE_DEVELOPER = 'developer'
FILE_PATH = 'bot.log'  # Указание полного пути к файлу

# Настройка переменной для хранения идентификатора пользователя


# Функция для отправки файла пользователю
async def send_file(update, context):
    developer_user_id = update.message.from_user.id

    if developer_user_id is None:
        logger.warning("Нет прав")
        return

    if not os.path.exists(FILE_PATH):
        logger.error(f"Файл {FILE_PATH} не существует.")
        return

    try:
        with open(FILE_PATH, 'rb') as file:
            file_content = file.read()

        # Отправка файла с указанием имени файла
        await context.bot.send_document(
            chat_id=developer_user_id,
            document=InputFile(file_content, filename="bot.log"),
            caption="Файл с логами:"
        )
        logger.info(f"FФайл {FILE_PATH} Успешно отправлен")

        # Очищаем файл после отправки
        with open(FILE_PATH, 'w') as file:
            file.write("")


    except Exception as e:
        logger.error(f"An error occurred while sending the file: {e}")

# Команда для установки идентификатора разработчика
async def set_developer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global developer_user_id
    user_id = update.message.from_user.id
    role = get_user_role(user_id)

    if role == ROLE_DEVELOPER:
        developer_user_id = user_id
        await update.message.reply_text("Ваш идентификатор установлен для отправки логов.")
    else:
        await update.message.reply_text("Отказано в доступе")

