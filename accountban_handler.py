import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, \
    CallbackQueryHandler
import os
from config import COOKIES
from database import *
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import asyncio
import sys

NICKNAMES, SERVER = range(2)

logger = logging.getLogger()

async def account_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)
    if role == 'admin' or role == 'developer':
        logger.info(f"Пользователь {user_id} начал проверку кандидатов")
        await update.message.reply_text('Введите никнеймы (каждый новый ник на новой строке):')
        return NICKNAMES
    else:
        logger.warning(
            f"Пользователь {user_id} с ролью {role} попытался запустить проверку кандидатов, но ему было отказано в доступе")
        await update.message.reply_text('Отказано в доступе')
        return ConversationHandler.END


async def get_server_choice(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    nicknames = update.message.text.strip().split('\n')
    context.user_data['nicknames'] = [nick.strip() for nick in nicknames if nick.strip()]
    user = update.message.from_user
    logger.info(f"Пользователь {user.username} ({user.id}) ввел ники: {context.user_data['nicknames']}")

    keyboard = [
        [InlineKeyboardButton(f"{i}", callback_data=str(i)) for i in range(1, 8)]  # предполагаем 7 серверов
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите номер сервера:', reply_markup=reply_markup)
    return SERVER


async def server_chosen(update: Update, context: CallbackContext) -> int:

    user_id = update.callback_query.from_user.id
    user_name = update.callback_query.from_user.name
    query = update.callback_query
    await query.answer()
    server = query.data
    context.user_data['server'] = server

    logger.info(f"Пользователь {user_name} ({user_id}) выбрал сервер №: {server}")

    await query.edit_message_text(text=f"Вы выбрали сервер {server}. Начинаю обработку...")

    nicknames = context.user_data.get('nicknames', [])
    server = context.user_data.get('server')

    results = await process_nicknames(update, context, nicknames, server)

    file_path = save_results_to_file(results)

    if os.path.getsize(file_path) > 0:

        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        logger.info(f"Пользователь {user_name} ({user_id}) получил файл с наказаниями {nicknames}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Не удалось найти информацию для предоставленных никнеймов.")

    os.remove(file_path)  # Очистка файла после отправки

    return ConversationHandler.END


async def process_nicknames(update: Update, context: CallbackContext, nicknames, server):
    user_id = update.effective_user.id
    results = []
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # только если необходимо
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    user_id = update.callback_query.from_user.id
    user_name = update.callback_query.from_user.name
    with webdriver.Chrome(service=service, options=options) as driver:
        for nick in nicknames:
            logger.info(f"Пользователь {user_name} ({user_id}) ищет аккаунт: {nick} на сервере {server}")
            player_id, reg_ip, last_ip = await get_player_info(update, context, driver, nick, server)

            if player_id:
                related_ids = await find_related_accounts(update, context, driver, reg_ip, last_ip)
                for related_id in related_ids:
                    logs = await get_account_logs(update, context, driver, related_id)
                    results.append({'nick': nick, 'logs': logs})

    return results


async def get_player_info(update: Update, context: CallbackContext, driver, nick, server):
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} начал получение информации об аккаунте {nick} на сервере {server}")

    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Начал поиск информации для аккаунта {nick}')

    url = f"https://rodina.logsparser.info/accounts?server_number={server}&name={nick}+"

    try:
        driver.get(url)
        # Убедитесь, что вы находитесь на правильном домене перед добавлением куки
        current_domain = driver.current_url.split('/')[2]
        for cookie in COOKIES:
            if 'domain' in cookie and cookie['domain'] not in current_domain:
                continue
            driver.add_cookie(cookie)
        driver.get(url)  # Перезагрузка страницы после добавления куки
        WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.TAG_NAME, "td")))
        logger.debug(url)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find_all('td')

        if len(rows) >= 9:
            player_id = rows[0].get_text().strip()
            last_ip = rows[-3].get_text().strip()  # Третий с конца <tr>
            reg_ip = rows[-2].get_text().strip()  # Второй с конца <tr>
            logger.debug(f"Получена информация для {nick}: player_id={player_id}, reg_ip={reg_ip}, last_ip={last_ip}")
            return player_id, reg_ip, last_ip
        else:
            logger.warning(f"Ожидаемая структура таблицы не найдена для {nick}")
            return None, None, None
    except Exception as e:
        logger.error(f"Ошибка при получении информации для {nick}: {e}")
        return None, None, None


async def find_related_accounts(update: Update, context: CallbackContext, driver, reg_ip, last_ip):
    user_id = update.effective_user.id
    logger.debug(f"Пользователь {user_id} ищет связанные аккаунты по IP: {reg_ip} и {last_ip}")

    gaserver = get_server(user_id)
    related_ids = set()
    for ip in [reg_ip, last_ip]:
        if not ip:
            continue

        url = f"https://rodina.logsparser.info/accounts?server_number={gaserver}&ip={ip}"

        try:
            driver.get(url)
            current_domain = driver.current_url.split('/')[2]
            for cookie in COOKIES:
                if 'domain' in cookie and cookie['domain'] not in current_domain:
                    continue
                driver.add_cookie(cookie)
            driver.get(url)  # Перезагрузка страницы после добавления куки
            WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tr")))

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr')

            for row in rows:
                cells = row.find_all('td')
                if cells:
                    related_ids.add(cells[0].get_text().strip())
        except Exception as e:
            logger.error(f"Ошибка при поиске связанных аккаунтов по IP {ip}: {e}")

    logger.debug(f"Найдено связанных аккаунтов: {related_ids}")
    return related_ids


async def get_account_logs(update: Update, context: CallbackContext, driver, player_id):
    user_id = update.effective_user.id
    logger.debug(f"Пользователь {user_id} начал получение логов для аккаунта {player_id}")

    gaserver = get_server(user_id)

    url = f"https://rodina.logsparser.info/?server_number={gaserver}&type%5B%5D=ban&type%5B%5D=jail&type%5B%5D=mute&type%5B%5D=banip&type%5B%5D=unban&type%5B%5D=unjail&type%5B%5D=unmute&type%5B%5D=unbanip&sort=desc&limit=1000&player={player_id}"

    try:
        driver.get(url)
        current_domain = driver.current_url.split('/')[2]
        for cookie in COOKIES:
            if 'domain' in cookie and cookie['domain'] not in current_domain:
                continue
            driver.add_cookie(cookie)
        driver.get(url)  # Перезагрузка страницы после добавления куки
        WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.TAG_NAME, "tr")))

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find_all('tr')
        logs = []
        for row in rows:
            cells = row.find_all('td')[:-2]  # Ищем все клетки в строке, кроме последних двух
            log_line = ' '.join(cell.get_text().strip() for cell in cells)
            logs.append(log_line)
        logger.debug(f"{player_id} получил логи")
        return logs
    except Exception as e:
        logger.error(f"Ошибка при получении логов для аккаунта {player_id}: {e}")
        return []


def save_results_to_file(results):
    file_path = 'results.txt'
    with open(file_path, 'w', encoding='utf-8') as file:
        for result in results:
            file.write(f"Найдено наказаний по никнейму: {result['nick']}\n")
            for log in result['logs']:
                file.write(f"{log}\n")
            file.write("\n")
    return file_path


async def account_cancel(update: Update, context: CallbackContext) -> int:
    from main import start
    user_id = update.message.from_user.id
    logger.info(f"Пользователь {user_id} отменил команду.")
    await update.message.reply_text('Команда отменена.')
    await start(update, context)
    return ConversationHandler.END


def accountcc_handler():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Проверка кандидатов1️⃣3️⃣$'), account_start)],
        states={
            NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_server_choice)],
            SERVER: [CallbackQueryHandler(server_chosen)],
        },
        fallbacks=[CommandHandler('cancel', account_cancel)],
    )



