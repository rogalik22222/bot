import logging
import os
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, ConversationHandler, ContextTypes
from database import get_user_role

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Константа для идентификатора роли пользователя
ROLE_DEVELOPER = 'developer'
FILE_PATH = 'bot.log'  # Указание полного пути к файлу


# Функция для отправки файла пользователю
async def send_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)

    if role == ROLE_DEVELOPER:
        # Проверка существования файла и его содержимого
        if not os.path.exists(FILE_PATH):
            logger.error(f"File {FILE_PATH} does not exist.")
            await update.message.reply_text("Файл с логами не найден.")
            return

        try:
            with open(FILE_PATH, 'rb') as file:
                file_content = file.read()

            # Отправка файла с указанием имени файла
            await update.message.reply_document(
                document=InputFile(file_content, filename="bot.log"),
                caption="Файл с логами:"
            )
        except Exception as e:
            logger.error(f"An error occurred while sending the file: {e}")
            await update.message.reply_text("Произошла ошибка при отправке файла.")
    else:
        await update.message.reply_text("Отказано в доступе")
