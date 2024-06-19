import os
from dotenv import load_dotenv, find_dotenv

if not find_dotenv():
    exit("Переменные окружения не загружены т.к отсутствует файл .env")
else:
    load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    exit('RAPID_API_KEY отсутствует в переменных окружения')

RAPID_API_KEY = os.getenv("RAPID_API_KEY")
if RAPID_API_KEY is None:
    exit('RAPID_API_KEY отсутствует в переменных окружения')

# DEFAULT_COMMANDS = (
#     ("start", "Начать поиск апартаментов")
#     # ("help", "Вывести справку")
# )
#
API_BASE_URL = "booking-com.p.rapidapi.com"
