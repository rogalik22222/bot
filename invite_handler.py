import os
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from config import COOKIES
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import logging
from dostups import *
import time
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем этапы разговора
DATE_FROM, DATE_TO, NICKNAMES = range(3)

# Функция для проверки корректности формата даты
def validate_date(date_str):
    try:
        datetime.strptime(date_str, '%d.%m.%Y')
        return True
    except ValueError:
        return False

async def date_from_invites(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    roles = get_user_role(user_id)

    if roles in ['sled', 'tech', 'admin', 'developer']:
        min_date = update.message.text.strip()
        if not validate_date(min_date):
            await update.message.reply_text("Пожалуйста,начальную дату в формате ДД.ММ.ГГГГ:")
            return DATE_FROM

        context.user_data['min_date'] = min_date
        await update.message.reply_text("Введите конечную дату в формате ДД.ММ.ГГГГ:")
        return DATE_TO

    await update.message.reply_text('Отказано в доступе')
    return ConversationHandler.END



async def date_to_invites(update: Update, context: CallbackContext) -> int:
    max_date = update.message.text.strip()
    if not validate_date(max_date):
        await update.message.reply_text("Пожалуйста, введите дату в правильном формате ДД.ММ.ГГГГ:")
        return DATE_TO

    context.user_data['max_date'] = max_date
    await update.message.reply_text("Введите ники игроков (по одному на строку):")
    return NICKNAMES

async def nicknames_invites(update: Update, context: CallbackContext) -> int:
    try:
        nicknames = update.message.text.split('\n')
        nicknames = [nick.strip() for nick in nicknames if nick.strip()]

        if not nicknames:
            await update.message.reply_text("Пожалуйста, введите хотя бы один ник.")
            return NICKNAMES

        min_date = context.user_data['min_date']
        max_date = context.user_data['max_date']

        await update.message.reply_text("Генерация отчета...")
        for nick in nicknames:
            file_path = generate_invites(nick, min_date, max_date)
            if os.path.getsize(file_path) > 0:  # Проверка на непустой файл
                with open(file_path, 'rb') as report_file:
                    await context.bot.send_document(chat_id=update.message.chat.id, document=report_file)
            else:
                await update.message.reply_text(f"Файл отчета для {nick} пуст.")

            os.remove(file_path)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")

    return ConversationHandler.END


def generate_invites(nick: str, min_date: str, max_date: str) -> str:
    # Преобразование формата даты для URL
    min_date = datetime.strptime(min_date, '%d.%m.%Y').strftime('%Y-%m-%d')
    max_date = datetime.strptime(max_date, '%d.%m.%Y').strftime('%Y-%m-%d')

    # Настройка Selenium
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # только если необходимо
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=service, options=options)

    print(f"Начинаю поиск инвайтов лидера {nick} с {min_date} до {max_date}")
    url = f"https://rodina.logsparser.info/?server_number=5&type%5B%5D=invite&sort=desc&player={nick}&min_period={min_date}+00%3A00%3A00&max_period={max_date}+23%3A58%3A58&limit=1000"

    try:
        driver.get(url)
        for cookie in COOKIES:
            driver.add_cookie(cookie)
        driver.get(url)
        time.sleep(10)

        # Используем WebDriverWait для ожидания загрузки страницы
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "tr")))

        file_path = f"{nick}_invite.txt"
        with open(file_path, 'w', encoding='utf8') as file:
            page_num = 1
            while True:
                driver.get(url + f"&page={page_num}")
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                rows = soup.find_all('tr')

                if not rows:
                    print(f"Нет данных на странице {page_num} для {nick}")

                    break


                has_data = False
                for row in rows:
                    cells = row.find_all('td')[:-2]  # Пропускаем последние 2 тега <td>
                    if cells:
                        file.write(' '.join(cell.get_text().strip() for cell in cells) + '\n\n')
                        has_data = True

                if not has_data:
                    print(f"Нет данных на странице {page_num} для {nick}")

                    break

                page_num += 1

    finally:
        driver.quit()

    return file_path