import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения пользователю"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Отправлено сообщение {message}')
    except Exception:
        logger.exception(f'Не удается отправить сообщение: {message}')


def get_api_answer(current_timestamp):
    """Запрос к сервису"""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise Exception(
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа API {homework_statuses.status_code}'
        )
    return homework_statuses.json()


def check_response(response):
    """Проверка наличия в ответе ключа 'homework'."""
    try:
        homeworks = response['homeworks']
    except KeyError:
        raise KeyError('Отсутствует необходимый ключ "homework"')
    if type(homeworks) is not list:
        raise Exception('По ключу "homeworks" получен не список')
    return homeworks


def parse_status(homework):
    """Получение информации о домашней работе."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError:
        raise KeyError('Отсутствует необходимый ключ в домашней работе')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        raise Exception('Незадокументированный статус домашней работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности токенов."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if not token:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {token}'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(current_timestamp)
                if check_response(response):
                    homework = response['homeworks'][0]
                    message = parse_status(homework)
                    send_message(bot, message)
                else:
                    logger.debug('Статус домашней работы не изменился')
                current_timestamp = response.get('current_date')
                time.sleep(RETRY_TIME)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.exception(message)
                send_message(bot, message)
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
