import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
import asyncio
import os
from config import COOKIES
logging.basicConfig(level=logging.INFO)
from  database import *
NICKNAMES, SERVER, PROCESSING = range(3)

async def account_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)
    if role == 'admin' or role == 'developer':
        await update.message.reply_text('Введите никнеймы (каждый новый ник на новой строке):')
        return NICKNAMES
    else:
        await update.message.reply_text('Отказано в доступе')
        return ConversationHandler.END


async def get_server_choice(update: Update, context: CallbackContext) -> int:
    nicknames = update.message.text.strip().split('\n')
    context.user_data['nicknames'] = [nick.strip() for nick in nicknames if nick.strip()]

    keyboard = [
        [InlineKeyboardButton(f"{i}", callback_data=str(i)) for i in range(1, 8)]  # assuming 10 servers
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите номер сервера:', reply_markup=reply_markup)
    return SERVER

async def server_chosen(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    server = query.data
    context.user_data['server'] = server

    await query.edit_message_text(text=f"Вы выбрали сервер {server}. Начинаю обработку...")

    nicknames = context.user_data.get('nicknames', [])
    server = context.user_data.get('server')

    results = await process_nicknames(query, context, nicknames, server)

    file_path = save_results_to_file(results)

    if os.path.getsize(file_path) > 0:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Не удалось найти информацию для предоставленных никнеймов.")

    os.remove(file_path)  # Clean up the file after sending

    return ConversationHandler.END

async def process_nicknames(query, context: CallbackContext, nicknames, server):
    results = []

    for nick in nicknames:
        player_id, reg_ip, last_ip = await get_player_info(query, context, nick, server)

        if player_id:
            related_ids = await find_related_accounts(query, context, server, reg_ip, last_ip)
            for related_id in related_ids:
                logs = await get_account_logs(query, context, server, related_id)
                results.append({'nick': nick, 'logs': logs})

    return results

async def get_player_info(query, context: CallbackContext, nick, server):
    logging.info("Запуск браузера для получения информации об аккаунте")
    await query.message.reply_text(f'Начал поиск информации для аккаунта {nick}')

    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')

    driver = webdriver.Chrome(service=service, options=options)
    url = f"https://rodina.logsparser.info/accounts?server_number={server}&name={nick}+"

    try:
        driver.get(url)
        for cookie in COOKIES:
            driver.add_cookie(cookie)
        driver.get(url)  # Перезагрузка страницы после добавления куки
        time.sleep(15)
        logging.info(url)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find_all('td')

        if len(rows) >= 9:
            player_id = rows[0].get_text().strip()
            last_ip = rows[-3].get_text().strip()  # Third to last <tr>
            reg_ip = rows[-2].get_text().strip()  # Second to last <tr>
            logging.info(f"Получена информация для {nick}: player_id={player_id}, reg_ip={reg_ip}, last_ip={last_ip}")
            return player_id, reg_ip, last_ip
        else:
            logging.warning(f"Ожидаемая структура таблицы не найдена для {nick}")
            return None, None, None
    finally:
        driver.quit()

async def find_related_accounts(query, context: CallbackContext, server, reg_ip, last_ip):
    logging.info(f"Поиск связанных аккаунтов по IP: {reg_ip} и {last_ip}")

    related_ids = set()
    for ip in [reg_ip, last_ip]:
        if not ip:
            continue

        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')

        driver = webdriver.Chrome(service=service, options=options)
        url = f"https://rodina.logsparser.info/accounts?server_number=5&ip={ip}"

        try:
            driver.get(url)
            for cookie in COOKIES:
                driver.add_cookie(cookie)
            driver.get(url)  # Перезагрузка страницы после добавления куки
            time.sleep(15)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr')

            for row in rows:
                cells = row.find_all('td')
                if cells:
                    related_ids.add(cells[0].get_text().strip())
        finally:
            driver.quit()

    logging.info(f"Найдены связанные аккаунты: {related_ids}")
    return related_ids

async def get_account_logs(query, context: CallbackContext, server, player_id):
    logging.info(f"Получение логов для аккаунта {player_id}")

    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')

    driver = webdriver.Chrome(service=service, options=options)
    url = f"https://rodina.logsparser.info/?server_number=5&type%5B%5D=ban&type%5B%5D=jail&type%5B%5D=mute&type%5B%5D=banip&type%5B%5D=unban&type%5B%5D=unjail&type%5B%5D=unmute&type%5B%5D=unbanip&sort=desc&limit=1000&player={player_id}"

    try:
        driver.get(url)
        for cookie in COOKIES:
            driver.add_cookie(cookie)
        driver.get(url)  # Перезагрузка страницы после добавления куки
        time.sleep(15)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find_all('tr')

        logs = []
        for row in rows:
            cells = row.find_all('td')[:-2]
            log_line = ' '.join(cell.get_text().strip() for cell in cells)
            logs.append(log_line)

        logging.info(f"Логи для аккаунта {player_id}: {logs}")
        return logs
    finally:
        driver.quit()
def save_results_to_file(results):
    file_path = 'results.txt'
    with open(file_path, 'w', encoding='utf-8') as file:
        for result in results:
            file.write(f"Nick_Name: {result['nick']}\n")
            for log in result['logs']:
                file.write(f"{log}\n")
            file.write("\n")
    return file_path

async def account_cancel(update: Update, context: CallbackContext) -> int:
    from main import start
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
