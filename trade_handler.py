import os
import time
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from config import COOKIES, API_KEY
# Состояния разговора
DATE_FROM, DATE_TO, NICKNAMES = range(3)
from database import *



# Функция для начала разговора и запроса даты начала
async def check_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)
    if role == 'tech' or role == 'admin' or role == 'developer':
        await update.message.reply_text('Введите дату начала (в формате ДД.ММ.ГГГГ):')
        return DATE_FROM
    else:
        await update.message.reply_text("Отказано в доступе")
        return ConversationHandler.END

# Функция для запроса даты окончания
async def date_from(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['date_from'] = update.message.text
    await update.message.reply_text('Введите дату окончания (в формате ДД.ММ.ГГГГ):')
    return DATE_TO

# Функция для запроса никнеймов
async def date_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['date_to'] = update.message.text
    await update.message.reply_text('Введите никнеймы (можно в столбик несколько):')
    return NICKNAMES

# Функция для сбора никнеймов
async def nicknames(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nicknames_text = update.message.text
    await update.message.reply_text('Начинаю проверку передач')
    if '\n' in nicknames_text:
        nicknames = [nick.strip() for nick in nicknames_text.split('\n')]
    else:
        nicknames = [nick.strip() for nick in nicknames_text.split(',')]
    context.user_data['nicknames'] = nicknames

    date_from = context.user_data['date_from']
    date_to = context.user_data['date_to']

    # Проверка инвентаря для каждого никнейма
    for nick in nicknames:
        await check_inventory(update, context, nick, date_from, date_to)
    return ConversationHandler.END

# Функция для проверки инвентаря
async def check_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE, nick: str, date_from: str, date_to: str) -> None:
    # Настройка Selenium
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # только если необходимо
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=service, options=options)

    # Преобразование даты в формат ГГГГ-ММ-ДД для URL
    date_from_formatted = datetime.strptime(date_from, '%d.%m.%Y').strftime('%Y-%m-%d')
    date_to_formatted = datetime.strptime(date_to, '%d.%m.%Y').strftime('%Y-%m-%d')

    url = f"https://rodina.logsparser.info/?server_number=5&type%5B%5D=inventory_give&sort=desc&&type%5B%5D=money_remove&player={nick}&min_period={date_from_formatted}+00%3A00%3A00&max_period={date_to_formatted}+23%3A59%3A59&limit=1000"
    driver.get(url)
    for cookie in COOKIES:
        driver.add_cookie(cookie)
    driver.get(url)
    time.sleep(10)  # Adjust sleep time accordingly
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    rows = list(soup.find_all('tr'))

    log_lines = []
    for row in rows:
        cells = row.find_all('td')[:-2]  # Skip the last two <td> elements
        if cells:
            log_line = ' '.join(cell.get_text().strip() for cell in cells)
            log_lines.append(log_line)

    inventory_data = parse_inventory(log_lines)

    file_path = f"{nick}_inventory.txt"
    with open(file_path, 'w', encoding='utf8') as file:
        for item in inventory_data:
            file.write(f"{item}\n")

    driver.quit()

    # Проверка, что файл не пустой
    if os.path.getsize(file_path) > 0:
        with open(file_path, 'rb') as file:
            await update.message.reply_document(document=file)
    else:
        await update.message.reply_text(f"Нет данных для никнейма {nick} за указанный период.")

    os.remove(file_path)

# Функция для анализа логов
def parse_inventory(log_lines):
    inventory_data = []

    for line in log_lines:
        parts = line.split(' ')
        if len(parts) < 2:
            continue  # Пропустить строки с некорректным форматом

        # Assuming parts is a list like: [date, time, player, action, item, ..., amount, reason]
        date_time = parts[0] + ' ' + parts[1]
        player = parts[2]
        action = ' '.join(parts[3:5])  # Adjust this depending on the exact structure
        item = ' '.join(parts[5:-2])
        amount = parts[-2]
        reason = parts[-1]

        inventory_data.append(f"{date_time} {player} {action} {item} {amount} {reason}")

    return inventory_data

# Функция для отмены разговора
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Команда отменена.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main() -> None:
    app = ApplicationBuilder().token(API_KEY).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('trade', check_start)],
        states={
            DATE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_from)],
            DATE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_to)],
            NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, nicknames)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
