import os
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from config import COOKIES
from dostups import *
import logging
DATE_FROM, DATE_TO, NICKNAMES = range(3)
logger = logging.getLogger()

async def check_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    roles = get_user_role(user_id)
    if roles in ['sled', 'tech', 'admin', 'developer']:
        await update.message.reply_text('Введите дату начала (в формате ДД.ММ.ГГГГ):')
        return DATE_FROM
    await update.message.reply_text('Отказано в доступе')
    return ConversationHandler.END

async def date_from(update: Update, context: CallbackContext) -> int:
    context.user_data['date_from'] = update.message.text
    await update.message.reply_text('Введите дату окончания (в формате ДД.ММ.ГГГГ):')
    return DATE_TO

async def date_to(update: Update, context: CallbackContext) -> int:
    context.user_data['date_to'] = update.message.text
    await update.message.reply_text('Введите никнеймы (можно в столбик несколько):')
    return NICKNAMES

async def nicknames(update: Update, context: CallbackContext) -> int:
    nicknames_text = update.message.text
    await update.message.reply_text('Начал проверку онлайна в логах')
    user = update.message.from_user

    if '\n' in nicknames_text:
        nicknames = [nick.strip() for nick in nicknames_text.split('\n')]
    else:
        nicknames = [nick.strip() for nick in nicknames_text.split(',')]
    context.user_data['nicknames'] = nicknames

    date_from = context.user_data['date_from']
    date_to = context.user_data['date_to']

    combined_log = f"Онлайн с {date_from} до {date_to}\n"
    logger.info(
        f"Пользователь {user.username} ({user.id}) Начал проверку онлайна игрока(ов) {nicknames} c {date_from} по {date_to}")
    for nick in nicknames:
        log = await check_online(update, context, nick, date_from, date_to)
        if log:
            combined_log += f"\n{nick}\n{log}\n"

    file_path = "online_logs.txt"
    with open(file_path, 'w', encoding='utf8') as file:
        file.write(combined_log)

    with open(file_path, 'rb') as file:
        await update.message.reply_document(document=file)
        logger.info(
            f"Пользователь {user.username} ({user.id}) Получил файл с онлайном ника(ов) {nicknames} c {date_from} по {date_to}")

    os.remove(file_path)
    return ConversationHandler.END

async def check_online(update: Update, context: CallbackContext, nick: str, min_per: str, max_per: str) -> str:
    from database import get_server
    user_id = update.message.from_user.id
    aserver = get_server(user_id)
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # только если необходимо
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=service, options=options)

    min_per_formatted = datetime.strptime(min_per, '%d.%m.%Y').strftime('%Y-%m-%d')
    max_per_formatted = datetime.strptime(max_per, '%d.%m.%Y').strftime('%Y-%m-%d')

    url = f"https://rodina.logsparser.info/?server_number={aserver}&type%5B%5D=disconnect&sort=desc&player={nick}&min_period={min_per_formatted}+00%3A00%3A00&max_period={max_per_formatted}+23%3A58%3A58&limit=1000"

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
        cells = row.find_all('td')[:-2]
        if cells:
            log_lines.append(' '.join(cell.get_text().strip() for cell in cells))

    driver.quit()

    max_play_time = parse_log(log_lines)

    if max_play_time:
        log = ""
        for date, max_time in max_play_time.items():
            log += f"{date.strftime('%d.%m.%Y')} {max_time}\n"
        return log
    else:
        return f"Нет данных для никнейма {nick} за указанный период."

def parse_log(log_lines):
    max_play_time = {}

    for line in log_lines:
        parts = line.split(',')
        if len(parts) < 2:
            continue

        date_str = parts[0].split()
        if len(date_str) < 2:
            continue

        date_str = date_str[0] + " " + date_str[1]

        play_time_day = None
        for part in parts:
            if 'время игры за день:' in part:
                play_time_day_str = part.strip().split(': ')[1]
                try:
                    play_time_day = datetime.strptime(play_time_day_str, '%H:%M:%S').time()
                except ValueError:
                    continue
                break

        if play_time_day is None:
            continue
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
        except ValueError:
            continue

        if date not in max_play_time:
            max_play_time[date] = play_time_day
        else:
            if play_time_day > max_play_time[date]:
                max_play_time[date] = play_time_day

    return max_play_time

async def online_cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Команда отменена.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
