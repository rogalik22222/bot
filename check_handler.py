import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
from config import COOKIES
from database import init_db, add_user, get_user_role, update_user_role, get_all_users, delete_user
import sqlite3
from dostups import *
init_db()

NICKNAMES = range(1)



async def check_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    roles = get_user_role(user_id)  # Предположим, что get_user_role возвращает строку с ролью пользователя

    # Проверяем роль пользователя
    if roles in ['sled', 'tech', 'admin', 'developer']:
        await update.message.reply_text('Введите никнеймы (каждый новый ник на новой строке):')
        return NICKNAMES  # Возвращаем состояние, в котором пользователь может вводить никнеймы

    # Если не найдено подходящих ролей, отправляем сообщение об отказе
    await update.message.reply_text('Отказано в доступе')
    return ConversationHandler.END  # Завершаем обработчик разговора



def get_player_id(nick):
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')

    driver = webdriver.Chrome(service=service, options=options)
    url = f"https://rodina.logsparser.info/accounts?server_number=5&name={nick}+"

    try:
        driver.get(url)
        for cookie in COOKIES:
            driver.add_cookie(cookie)
        driver.get(url)
        time.sleep(10)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        rows = list(soup.find_all('tr'))

        log_lines = []
        for row in rows:
            cells = row.find_all('td')[:-9]
            if cells:
                log_lines.append(' '.join(cell.get_text().strip() for cell in cells))

        if log_lines:
            first_row = log_lines[0]
            player_id = first_row.split()[0]
            return player_id
        return None
    finally:
        driver.quit()

async def check_nicknames(update: Update, context: CallbackContext) -> int:
    nicks = update.message.text.split('\n')
    nicks = [nick.strip() for nick in nicks]

    for nick in nicks:
        checking_message = await update.message.reply_text(f'Начинаю проверку привязок для никнейма: {nick}')

        try:
            player_id = get_player_id(nick)
            if not player_id:
                await checking_message.edit_text(f'Не удалось найти ID для никнейма {nick}')
                continue

            service = Service(ChromeDriverManager().install())
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')

            driver = webdriver.Chrome(service=service, options=options)
            url = f"https://rodina.logsparser.info/?server_number=5&type%5B%5D=mail&type%5B%5D=password&type%5B%5D=vk_attach&type%5B%5D=vk_detach&type%5B%5D=googleauth_attach&type%5B%5D=googleauth_detach&sort=desc&player={player_id}&limit=1000"

            driver.get(url)
            for cookie in COOKIES:
                driver.add_cookie(cookie)
            driver.get(url)
            time.sleep(10)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            rows = list(soup.find_all('tr'))

            log_lines = []
            for row in rows:
                cells = row.find_all('td')[:-2]
                if cells:
                    log_lines.append(' '.join(cell.get_text().strip() for cell in cells))

            account_status = parse_account_activities(log_lines)
            result_message = (f"Привязки для никнейма {nick}({player_id}):\n"
                              f"Google Authenticator: {account_status['Google Authenticator']}\n"
                              f"ВКонтакте: {account_status['ВКонтакте']}\n"
                              f"Mail Address: {account_status['Mail Address']}\n"
                              f"Последнее изменение пароля: {account_status['Last Password Change']}")
            await checking_message.edit_text(result_message)
        except Exception as e:
            await checking_message.edit_text(f'Произошла ошибка при проверке привязок для никнейма {nick}: {e}')
        finally:
            driver.quit()

    await update.message.reply_text('Выгрузка закончена.')
    return ConversationHandler.END

def parse_account_activities(log_lines):
    account_status = {
        "Google Authenticator": "не привязан",
        "ВКонтакте": "не привязан",
        "Mail Address": "не привязан",
        "Last Password Change": "Пароль не изменялся"
    }

    for line in reversed(log_lines):
        if "привязал к своему аккаунту защиту Google Authenticator" in line:
            account_status["Google Authenticator"] = "привязан"
        elif "привязал к своему аккаунту страницу ВКонтакте" in line:
            vk_page = line.split(" страницу ВКонтакте ")[-1]
            account_status["ВКонтакте"] = vk_page.strip()
        elif "изменил почту" in line:
            new_email = line.split(" на ")[-1]
            account_status["Mail Address"] = new_email.strip()
        elif "изменил пароль на" in line:
            date_time = line.split("изменил пароль на")[0].strip()
            account_status["Last Password Change"] = date_time

    return account_status

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END


def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Проверить привязки🔗$'), check_start)],
        states={
            NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_nicknames)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
