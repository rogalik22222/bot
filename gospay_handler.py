from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import os
from config import COOKIES, API_KEY
from database import get_user_role
from database import *
# Conversation states
import logging
DATE_FROM, DATE_TO, FRACTION = range(3)

logger = logging.getLogger()

# Function to start the conversation and ask for the start date
async def check_start(update: Update, context: CallbackContext) -> int:
    if not is_authorized(update.message.from_user.id):
        await update.message.reply_text("Отказано в доступе")
        return ConversationHandler.END

    await update.message.reply_text('Введите дату начала (в формате ДД.ММ.ГГГГ):')
    return DATE_FROM

def is_authorized(user_id: int) -> bool:
    role = get_user_role(user_id)
    return role in ['sled', 'tech', 'admin', 'developer']

async def date_from_gos(update: Update, context: CallbackContext) -> int:
    context.user_data['date_from'] = update.message.text
    await update.message.reply_text('Введите дату окончания (в формате ДД.ММ.ГГГГ):')
    return DATE_TO

async def date_to_gos(update: Update, context: CallbackContext) -> int:
    context.user_data['date_to'] = update.message.text
    await prompt_fraction_selection(update)
    return FRACTION

async def prompt_fraction_selection(update: Update):
    fractions = [
        "Городская+полиция", "Полиция+округа", "Городская+больница", "Правительство",
        "Центр+лицензирования", "Новостное+агентство", "Казанская+банда", "Больница+округа",
        "Черная+кошка", "Санитары", "Солнцевская+братва", "Русская+Мафия",
        "Украинская+Мафия", "Кавказская+Мафия", "ФСБ", "Армия", "Тюрьма+строгого+режима"
    ]
    reply_keyboard = [[fraction] for fraction in fractions]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text('Выберите фракцию из списка:', reply_markup=reply_markup)

async def get_fraction(update: Update, context: CallbackContext) -> int:
    context.user_data['fraction'] = update.message.text
    await update.message.reply_text('Начинаю проверку')
    await check_fraction(update, context)
    return ConversationHandler.END

async def check_fraction(update: Update, context: CallbackContext):
    fraction, date_from, date_to = get_check_parameters(context)
    user = update.message.from_user
    driver = setup_selenium_driver()
    url = build_url(date_from, date_to, fraction, update, context)
    html = fetch_page_source(driver, url)
    log_lines = extract_log_lines(html)
    inventory_data = parse_inventory(log_lines)
    logger.info(f"Пользователь {user.username} ({user.id}) Начал проверку снятия денег с казны фракции игрока: {fraction} с {date_from} по {date_to}")
    await send_otchet(update, fraction, inventory_data, context)

    driver.quit()

def get_check_parameters(context: CallbackContext):
    return context.user_data['fraction'], context.user_data['date_from'], context.user_data['date_to']

def setup_selenium_driver():
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # only if necessary
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def build_url(date_from: str, date_to: str, fraction: str, update: Update, context: CallbackContext) -> str:
    user_id = update.message.from_user.id
    aserver = get_server(user_id)
    date_from_formatted = datetime.strptime(date_from, '%d.%m.%Y').strftime('%Y-%m-%d')
    date_to_formatted = datetime.strptime(date_to, '%d.%m.%Y').strftime('%Y-%m-%d')
    return (f"https://rodina.logsparser.info/?server_number={aserver}&type%5B%5D=money_add&sort=desc"
            f"&min_period={date_from_formatted}+00%3A00%3A00&max_period={date_to_formatted}+23%3A59%3A59"
            f"&limit=1000&dynamic%5B61%5D=+снял+со+счета+организации+{fraction}")

def fetch_page_source(driver, url: str) -> str:
    driver.get(url)
    for cookie in COOKIES:
        driver.add_cookie(cookie)
    driver.get(url)
    time.sleep(10)  # Adjust sleep time accordingly
    return driver.page_source

def extract_log_lines(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    rows = list(soup.find_all('tr'))
    log_lines = []
    for row in rows:
        cells = row.find_all('td')[:-2]  # Skip the last two <td> elements
        if cells:
            log_line = ' '.join(cell.get_text().strip() for cell in cells)
            log_lines.append(log_line)
    return log_lines

def parse_inventory(log_lines):
    # Placeholder function to parse logs
    return log_lines

async def send_otchet(update: Update, fraction: str, inventory_data, context: CallbackContext):
    user = update.message.from_user
    from main import start
    file_path = f"{fraction}.txt"
    with open(file_path, 'w', encoding='utf8') as file:
        for item in inventory_data:
            file.write(f"{item}\n")
    if os.path.getsize(file_path) > 0:
        with open(file_path, 'rb') as file:
            await update.message.reply_document(document=file)
        logger.info(f"Пользователь {user.username} ({user.id}) Получил файл с проверки снятия казны фракции")
    else:
        await update.message.reply_text(f"Нет данных для фракции {fraction} за указанный период.")
    await start(update, context)
    os.remove(file_path)