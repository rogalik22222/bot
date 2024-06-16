import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
from config import COOKIES
from database import *
logging.basicConfig(level=logging.INFO)
from webdriver_manager.chrome import ChromeDriverManager
NICKNAMES = range(1)


async def account_start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    role = get_user_role(user_id)
    if role == 'tech' or role == 'admin' or role == 'developer':
        await update.message.reply_text('Введите никнеймы (каждый новый ник на новой строке):')
        return NICKNAMES
    else:
        await update.message.reply_text('Отказано в доступе')
        return ConversationHandler.END



async def get_player_id(update: Update, context: CallbackContext, nick: str):
    logging.info("Запуск браузера для получения player_id")
    await update.message.reply_text(f'Начал поиск id аккаунта {nick}')

    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # только если необходимо
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')


    driver = webdriver.Chrome(service=service, options=options)
    url = f"https://rodina.logsparser.info/accounts?server_number=5&name={nick}+"

    try:
        driver.get(url)
        for cookie in COOKIES:
            driver.add_cookie(cookie)
        driver.get(url)
        time.sleep(15)

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
            logging.info(f"Получен player_id: {player_id}")
            return player_id
        logging.warning("Не удалось найти player_id")
        return None
    finally:
        driver.quit()


async def find_ip(update: Update, context: CallbackContext) -> int:
    nicknames = update.message.text.strip().split('\n')
    for nick in nicknames:
        nick = nick.strip()
        if not nick:
            continue

        player_id = await get_player_id(update, context, nick)

        if player_id is None:
            await update.message.reply_text(f'Не удалось найти игрока с ником {nick}.')
            continue

        url1 = f"https://rodina.logsparser.info/?server_number=5&type%5B%5D=disconnect&sort=desc&player={player_id}&limit=1000"
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')

        driver = webdriver.Chrome(service=service, options=options)
        try:
            driver.get(url1)
            for cookie in COOKIES:
                driver.add_cookie(cookie)
            driver.get(url1)
            time.sleep(15)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr')

            ip_addresses = set()
            for row in rows:
                cells = row.find_all('td')
                last_cell = cells[-1] if cells else None

                if last_cell:
                    div = last_cell.find('div', class_='table-ip')
                    if div:
                        a_tags = div.find_all('a')
                        for a in a_tags:
                            badge_secondary = a.find('span', class_='badge badge-secondary')
                            if badge_secondary:
                                ip_address = badge_secondary.get_text().strip()
                                if ip_address and ip_address != '255.255.255.255':
                                    ip_addresses.add(ip_address)

            if ip_addresses:
                logging.info(f"Найдены IP адреса: {ip_addresses}")
                await update.message.reply_text(f'Найдены IP адреса для {nick}: {", ".join(ip_addresses)}')
                await find_accounts_by_ips(update, context, driver, ip_addresses)
            else:
                await update.message.reply_text(f'Не удалось найти IP-адреса для {nick}.')
        finally:
            driver.quit()

    await update.message.reply_text('Выгрузка закончена.')
    return ConversationHandler.END


async def find_accounts_by_ips(update: Update, context: CallbackContext, driver, ip_addresses):
    base_url = "https://rodina.logsparser.info/accounts?server_number=5&ip={}"

    for ip in ip_addresses:
        initial_message = await update.message.reply_text(f'Начинаю поиск по IP: {ip}')
        message_id = initial_message.message_id

        url = base_url.format(ip)
        logging.info(f"Переход по URL: {url}")

        driver.get(url)
        for cookie in COOKIES:
            driver.add_cookie(cookie)
        driver.get(url)
        time.sleep(15)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find_all('tr')

        if rows:
            message_lines = [f'Найдено входы по IP: {ip}']
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    first_td = cells[0].get_text().strip()
                    second_td = cells[1].get_text().strip()
                    message_lines.append(f'{second_td} [{first_td}]')

            message_text = '\n'.join(message_lines)
            await context.bot.edit_message_text(text=message_text, chat_id=update.message.chat_id,
                                                message_id=message_id)
        else:
            await context.bot.edit_message_text(text=f'По IP {ip} не найдено входов.', chat_id=update.message.chat_id,
                                                message_id=message_id)


async def account_cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Команда отменена.')
    return ConversationHandler.END


def accountc_handler():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Проверить твинки🤡$'), account_start)],
        states={NICKNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, find_ip)]},
        fallbacks=[CommandHandler('cancel', account_cancel)],
    )
