import requests
import aiohttp
import json
import re

from datetime import datetime
from typing import List, Dict
from loader import bot
from config_data import config


# querystring = {"units": "metric", "checkout_date": "2024-07-21", "checkin_date": "2024-07-14",
#                "dest_type": "country", "locale": "ru", "room_number": "1", "filter_by_currency": "EUR",
#                "order_by": "price", "adults_number": "2", "dest_id": "-553173", "children_number": "1",
#                "categories_filter_ids": "class::2,class::4,free_cancellation::1", "children_ages": "9,0",
#                "include_adjacency": "true", "page_number": "0"}


async def api_request(chat_id: int, endpoint: str, querystring: Dict, params=None) -> requests.Response.json:
    url = "https://" + config.API_BASE_URL
    headers = {
        "X-RapidAPI-Key": config.RAPID_API_KEY,
        "X-RapidAPI-Host": config.API_BASE_URL
    }
    if not params:
        params = {}
    for param in params:
        querystring[param] = params[param]
    cur_url = url + endpoint
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=cur_url, headers=headers, params=querystring, timeout=20) as response:
                if response.status == 200:  # = requests.codes.ok:
                    js = await response.json()
                    return js
    except TimeoutError as error:
        await bot.send_message(chat_id=chat_id, text="Не удалось получить ответ от Booking.com. "
                                                     "Повтори поиск.")


async def get_place(chat_id, city) -> dict:
    """
    Получение списка похожих локаций (городов, регионов, отелей и т.п.) с сайтв
    """
    query = {"locale": "ru"}
    response = await api_request(chat_id=chat_id, endpoint='/v1/hotels/locations', querystring=query, params={'name': city})

    dest_dict = {}
    for i, response_i in enumerate(response):
        dest_dict[response_i['dest_id']] = [response_i['label'], response_i['dest_type']]
    #print(dest_dict)
    return dest_dict


async def get_currency(chat_id, currency) -> Dict:
    """
    Получение списка валют с сайтв
    """
    query = {"locale": "ru"}
    response = await api_request(chat_id=chat_id,
                                 endpoint='/v1/metadata/exchange-rates',
                                 querystring=query,
                                 params={'currency': currency}
                                 )
    return response


async def make_currency_keyboard(chat_id, currency) -> List[Dict]:
    """
    Получение списка валют с сайтв и создание списка словарей для клавиатур
    """
    currency_response = await get_currency(chat_id, currency)

    currency_keyboard = list()
    if currency_response == {} or currency_response is None:
        await bot.send_message(chat_id=chat_id, text="Не удалось получить ответ от Booking.com. "
                                                     "Повтори поиск.")
    else:
        # Создаем клавиатуру - список валют
        currency_lst = ["EUR"]
        currency_lst.extend([elem['currency'] for elem in currency_response['exchange_rates']])
        # Рассчитаем количество сообщений для вывода всей валюты
        if len(currency_lst) % 99 == 0:
            message_count = len(currency_lst) // 99
        else:
            message_count = len(currency_lst) // 99 + 1

        for i in range(message_count):
            currency_keyboard_dict = {}
            for j in range(99):  # создаем сообщения с клавиатурами по 3 * 33 = 99 кнопок
                if i * 99 + j >= len(currency_lst): # чтобы не вылететь за границу списка
                    break
                currency_keyboard_dict["curr_" + currency_lst[i * 99 + j]] = currency_lst[i * 99 + j]
            currency_keyboard.append(currency_keyboard_dict)

    return currency_keyboard


async def itog_search(page_number="0", **kwargs) -> json:

    """
    Получение списка отелей с сайтв согласно всем заданным пользователем условиям.
    Так как список может быть длинным, то получается постранично
    """

    query = {"units": "metric", "locale": "ru", "room_number": "1", "filter_by_currency": "EUR",
             "order_by": "price", "include_adjacency": "false", "page_number": page_number}

    if kwargs['children_number'] == 0:
        # response = await api_request(chat_id=chat_id, endpoint='/v1/hotels/search-filters', querystring=query, params={
        response = await (api_request(chat_id=kwargs['chat_id'], endpoint='/v1/hotels/search', querystring=query, params={
            'categories_filter_ids': kwargs['categories_filter_ids'],
            'checkin_date': kwargs['checkin_date'],
            'checkout_date': kwargs['checkout_date'],
            'dest_type': kwargs['dest_type'],
            'dest_id': kwargs['dest_id'],
            'adults_number': kwargs['adults_number']
        }))
    else:
        # response = await api_request(chat_id=chat_id, endpoint='/v1/hotels/search-filters', querystring=query, params={
        response = await (api_request(chat_id=kwargs['chat_id'], endpoint='/v1/hotels/search', querystring=query, params={
                'categories_filter_ids': kwargs['categories_filter_ids'],
                'checkin_date': kwargs['checkin_date'],
                'checkout_date': kwargs['checkout_date'],
                'dest_type': kwargs['dest_type'],
                'dest_id': kwargs['dest_id'],
                'adults_number': kwargs['adults_number'],
                'children_number': kwargs['children_number'],
                'children_ages': kwargs['children_ages']
        }))
    return response


#async def make_hotels_list(my_currency, currency_exchange, sum_night, **kwargs) -> tuple:
async def make_hotels_list(**kwargs) -> tuple:

    page_num = 0
    price = 0
    hotel_num = 0
    currency = ""
    distances = ""
    accommodation = ""

    info = dict()

    while True:
        result_api = await itog_search(page_number=str(page_num), **kwargs)
        # json_raw = json.dumps(result_api, ensure_ascii=False, indent=2)
        # print(json_raw)
        if result_api is None or result_api["count"] is None or len(result_api["result"]) == 0:
            break
        else:
            for i, result_api_i in enumerate(result_api["result"]):
                try:
                    if result_api_i["composite_price_breakdown"].get("strikethrough_amount"):
                        price = int(
                            result_api_i["composite_price_breakdown"]["strikethrough_amount"]["value"])
                        currency = result_api_i["composite_price_breakdown"]["strikethrough_amount"][
                            "currency"]
                    else:
                        price = int(result_api_i["composite_price_breakdown"]["gross_amount"]["value"])
                        currency = result_api_i["composite_price_breakdown"]["gross_amount"]["currency"]
                    if result_api_i["composite_price_breakdown"].get("discounted_amount"):
                        price -= int(
                            result_api_i["composite_price_breakdown"]["discounted_amount"].get("value", 0))
                    if result_api_i["composite_price_breakdown"].get("charges_details"):
                        price += int(
                            result_api_i["composite_price_breakdown"]["charges_details"]["amount"].get(
                                "value", 0))

                    accommodation = result_api_i.get("unit_configuration_label", "")

                    if result_api_i.get("distances", []) != []:
                        distances = result_api_i["distances"][0].get("text", "")
                    else:
                        if result_api_i.get("distance_to_cc", "") != "":
                            distances = result_api_i.get("distance_to_cc") + " км до центра"
                        else:
                            distances = ""
                except ValueError:
                    price = 0
                days_count = (datetime.strptime(kwargs['checkout_date'], '%Y-%m-%d') -
                              datetime.strptime(kwargs['checkin_date'], '%Y-%m-%d')).days
                price /= float(kwargs['currency_exchange'].get("curr_" + currency))
                if (price / days_count) <= kwargs['sum_night']:
                    hotel_num += 1
                    info[hotel_num] = re.search(r"\d+", result_api_i["id"]).group()
                    info["info" + str(hotel_num)] = (f'| {hotel_num} |'
                                          f' {result_api_i["hotel_name_trans"]} |'
                                          f'  {kwargs['my_currency']} {str(int(price))}\n'
                                          f'       {distances}\n'
                                          f'       {accommodation}\n')
                    info["latitude" + str(hotel_num)] = str(result_api_i["latitude"])
                    info["longitude" + str(hotel_num)] = str(result_api_i["longitude"])
        page_num += 1

    page_hotel = list()
    if hotel_num != 0: # если есть подходящие отели
        if hotel_num % 20 == 0:
            page_hotel_count = hotel_num // 20
        else:
            page_hotel_count = hotel_num // 20 + 1
        for i in range(page_hotel_count):
            page_hotel_str = ""
            for j in range(20):
                if i * 20 + j + 1 <= hotel_num:
                    page_hotel_str = "".join([page_hotel_str, info["info" + str(i * 20 + j + 1)]])
            page_hotel.append(page_hotel_str)

    return page_hotel, info

async def photo_search(chat_id, hotel_id) -> List:
    """
    Получение фотографий отеля с сайтв
    """
    query = {"locale": "ru"}
    response = await api_request(chat_id=chat_id, endpoint='/v1/hotels/photos', querystring=query, params={
            'hotel_id': hotel_id
        })
    return response


async def description_search(chat_id, hotel_id) -> Dict:
    """
    Получение описания отеля с сайтв
    """
    query = {"locale": "ru"}
    response = await api_request(chat_id=chat_id, endpoint='/v1/hotels/description', querystring=query, params={
      'hotel_id': hotel_id
    })
    return response
