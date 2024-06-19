import logging
import re
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback, get_user_locale
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold
from aiogram.types import Message, CallbackQuery
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from peewee import IntegrityError
from datetime import datetime

from states.states import MyStates
from loader import bot, dp
from keyboards.inline.inline_keyboards import gen_markup
from api.api import (get_place, get_currency, make_currency_keyboard, make_hotels_list,
                     photo_search, description_search)
from database.save_user_info import request_create
from database.get_user_info import user_history, get_history

router = Router()

def date_check(text: str) -> str:
    """
    Проверяет, является ли полученный текст датой (текст в формате dd-mm-yyyy)
    и если нет, то просит указать дату в формате dd-mm-yyyy
    """
    my_date = re.findall(r"\d{2}[-]\d{2}[-]\d{4}", text)

    if not my_date:
        return f'Формат даты неверен.\nУкажи корректную дату в формате dd-mm-yyyy.'

    if int(my_date[0][6:10]) > datetime.now().year + 3:
        return f'Невозможно забронировать - еще нет информации по этой дате.\nУкажи корректную дату в формате dd-mm-yyyy.'

    try:
        # преобразуем строку в объект datetime
        datetime.strptime(my_date[0], '%d-%m-%Y')

        if datetime.strptime(my_date[0], '%d-%m-%Y') < datetime.now():
            return f'Выбранная дата уже прошла.\nУкажи корректную дату в формате dd-mm-yyyy.'
    except ValueError:
        # если возникла ошибка ValueError, значит, дата введена некорректно
        return f'Введена некорректная дата.\nУкажи корректную дату в формате dd-mm-yyyy.'

    return my_date[0]


@router.message(MyStates.city)
async def city_handler(message: Message, state: FSMContext) -> None:
    """
    СОздает список мест, похожих на введенный город.
    Если ничего похожего не найдено, просит повторить ввод места для поиска апартаментов
    """
    # Удаляем клавиатуру, если она была.
    try:
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id - 1,
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    # Очищаем всю информацию для поиска
    await state.clear()

    logging.info(f"Пользователь: {str(message.from_user.id)}, хочет искать: {message.text}")

    place_keyboard = dict()
    place_dict_response = await get_place(message.chat.id, city=message.text)
    if place_dict_response == {}:
        await message.answer(f'Нет места для поиска, похожего на то, что ты ищешь.\n'
                             f'Введи место для поиска заново.')
    else:
        for key, value in place_dict_response.items():
            place_keyboard["city" + str(key)] = value[0]

        await message.answer(f"Выбери место для поиска из списка:",
                                parse_mode='html',
                                reply_markup=gen_markup(callback_data_dict=place_keyboard, button_row=1))

    await state.update_data(user_id=message.from_user.id,
                            categories_filter_ids="property_type::204,property_type::201,property_type::220,property_type::213,property_type::219,reviewscorebuckets::80,reviewscorebuckets::90,reviewscorebuckets::999,free_cancellation::1",
                            categories_filter_text="",
                            cities=place_dict_response
                            )


@router.message(MyStates.checkin_date)
async def checkin_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем дату заезда
    """
    date_ok = date_check(message.text)
    if date_ok.endswith("dd-mm-yyyy."):
        await message.answer(date_ok)
        return

    checkin_date = date_ok[6:10] + "-" + date_ok[3:5] + "-" + date_ok[0:2]
    year = int(date_ok[6:10])
    month = int(date_ok[3:5])
    day = int(date_ok[0:2])

    logging.info(f"Пользователь: {str(message.from_user.id)}, дата заезда: {checkin_date}")

    user_locale = await get_user_locale(message.from_user)
    if user_locale == "ru_RU":
        user_locale += ".utf-8"
    calendar = SimpleCalendar(locale=user_locale, show_alerts=True)
    calendar.set_dates_range(datetime(year, month, day), datetime(year + 3, 12, 31))
    await message.answer(f"Выбери дату выезда в календаре\n или введи её в формате dd-mm-yyyy",
                         reply_markup=await calendar.start_calendar(year=year, month=month))

    await state.update_data(checkin_date=checkin_date,
                            year=year,
                            month=month,
                            day=day
                            )

    await state.set_state(MyStates.checkout_date)


@router.message(MyStates.checkout_date)
async def checkout_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем дату выезда
    """
    date_ok = date_check(message.text)
    if date_ok.endswith("dd-mm-yyyy."):
        await message.answer(date_ok)
        return

    checkout_date = date_ok[6:10] + "-" + date_ok[3:5] + "-" + date_ok[0:2]

    logging.info(f"Пользователь: {str(message.from_user.id)}, дата выезда: {checkout_date}")

    # Запрашиваем у Booking.com список валют (изначально - в переводе на Евро)
    currency_keyboard = await make_currency_keyboard(message.chat.id, currency="EUR")
    if currency_keyboard is not None and currency_keyboard != {}:
        await message.answer(f"Выбери или введи валюту из списка")
        for i, currency_keyboard_i in enumerate(currency_keyboard):
            await message.answer(":",
                                 parse_mode='html',
                                 reply_markup=gen_markup(callback_data_dict=currency_keyboard_i,
                                 button_row=3))

        await message.answer(f"Выбери или введи валюту из списка")
    else:
        await message.answer("Не удалось получить ответ от Booking.com. Повтори поиск.")

    await state.update_data(checkout_date=checkout_date)

    await state.set_state(MyStates.currency)


@router.message(MyStates.currency)
async def currency_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем валюту
    """

    # Запрашиваем у Booking.com курсы валют относительно выбранной валюты
    currency_response = await get_currency(message.chat.id, currency=message.text.strip().upper())
    if currency_response == None:
        await message.answer(f'Нет такой валюты в списке.\n'
                             f'Введи валюту заново.')
    else:
        currency = message.text.strip().upper()

        logging.info(f"Пользователь: {str(message.from_user.id)}, валюта: {currency}")

        currency_exchange = dict()
        data = await state.get_data()
        currency_exchange["curr_" + currency] = "1"
        # Создаем список валют для пересчета цен отеля (добавляем выбранную валюту с курсом 1)
        for elem in currency_response["exchange_rates"]:
            currency_exchange["curr_" + elem["currency"]] = elem["exchange_rate_buy"]
        await message.answer(f"Введи максимальную сумму в {currency} за сутки (всего планируется "
                         f"{(datetime.strptime(data['checkout_date'], '%Y-%m-%d') -
                             datetime.strptime(data['checkin_date'], '%Y-%m-%d')).days} сут.).\n"
                         f"Введи 0, если не хочешь ограничивать сумму.")
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id - 3,
                reply_markup=None
            )
        except TelegramBadRequest:
            pass
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id - 2,
                reply_markup=None
            )
        except TelegramBadRequest:
            pass

        await state.update_data(currency=currency, currency_exchange=currency_exchange)

        await state.set_state(MyStates.sum_night)


@router.message(MyStates.sum_night)
async def sum_night_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем сумму за сутки
    """
    try:
        int(message.text)
        if int(message.text) == 0:
            sum_night = 10000000 # без ограничения суммы за ночь
        else:
            sum_night = int(message.text)

        logging.info(f"Пользователь: {str(message.from_user.id)}, максимальная стоимость в сутки: {sum_night}")

        await message.answer("Введи количество взрослых")
        await state.set_state(MyStates.adults)

        await state.update_data(sum_night=sum_night)

    except ValueError:
        await message.answer('Введи одно число')


@router.message(MyStates.adults)
async def adults_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем количество взрослых
    """
    try:
        int(message.text)
        if int(message.text) <= 0:
            await message.answer("Количество взрослых должно быть больше 0")
        else:
            adults_count = int(message.text)

            logging.info(f"Пользователь: {str(message.from_user.id)}, взрослых: {adults_count}")

            await message.answer("Введи количество детей")
            await state.set_state(MyStates.children)

        await state.update_data(adults_count=adults_count)

    except ValueError:
        await message.answer('Введи одно число')


@router.message(MyStates.children)
async def children_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем количество детей
    """
    try:
        int(message.text)
        children_count = int(message.text)
        children_ages = 0
        # Если количество детей 0 или меньше, то меняем количество на 0, а возраст запрашивать не будем
        if children_count <= 0:
            children_count = 0
            children_ages = 0
        if children_count == 1:
            add_text = "ребенка"
        else:
            add_text = "детей через запятую"

        await state.update_data(children_count=children_count, children_ages=children_ages)

        logging.info(f"Пользователь: {str(message.from_user.id)}, детей: {children_count}")

        if children_count != 0:
            await message.answer(f"Введи возраст {add_text}")
            await state.set_state(MyStates.children_ages)
        else: # без детей
            await message.answer(f"<pre>Отметь необходимые удобства в номере,\n"
                                 f"После нажатия на необходимые удобства, выбери 'Готово'</pre>",
                                 parse_mode='html',
                                 reply_markup=gen_markup(callback_data_dict={
                                     'aircond': 'Кондиционер',
                                     'dishwasher': 'Стиральная машина',
                                     'kitchen': 'Кухня/мини-кухня',
                                     'facility': 'Готово',
                                 },
                                     button_row=3))
            await state.set_state(MyStates.room_facility)

    except ValueError:
        await message.answer('Введи одно число')


@router.message(MyStates.children_ages)
async def children_ages_handler(message: Message, state: FSMContext) -> None:
    """
    Сохраняем возраст ребенка/детей
    """
    data = await state.get_data()
    try:
        if data['children_count'] == 1:
            add_text = f"Ожидалась одна цифра возраста"
        else:
            add_text = f"Ожидалось {data['children_count']} возраста через запятую"
        ages = message.text.replace(" ", "").split(",")
        for age in ages:
            if not age.isdigit():
                await message.answer(f"{add_text}")
                return
        if len(ages) != data['children_count']:
            await message.answer(f"{add_text}")
            return
        children_ages = ",".join(ages)

        await state.update_data(children_ages=children_ages)

        logging.info(f"Пользователь: {str(message.from_user.id)}, возраст детей: {children_ages}")

        await message.answer(f"<pre>Отметь необходимые удобства в номере,\n"
                             f"После нажатия на необходимые удобства, выбери 'Готово'</pre>",
                             parse_mode='html',
                             reply_markup=gen_markup(callback_data_dict={
                                                        'aircond': 'Кондиционер',
                                                        'dishwasher': 'Стиральная машина',
                                                        'kitchen': 'Кухня/мини-кухня',
                                                        'facility': 'Готово',
                                                        },
                                                        button_row=3))
        await state.set_state(MyStates.room_facility)

    except ValueError:
        await message.answer(f'{add_text}')


@router.message(MyStates.photo)
async def photo_handler(message: Message, state: FSMContext) -> None:
    """
    Выдаем фото, дополнительную информацию об отеле и его местоположение на сайте maps.google.com
    """
    try:
        # если введено не число из списка (в том числе вообще не число),то по ошибке уходим в Exception
        data = await state.get_data()
        tmp = data["info"][int(message.text)]

        logging.info(f"Пользователь: {str(message.from_user.id)}, номер отеля для инфо: {message.text}")

        photo_api = await photo_search(chat_id=message.chat.id, hotel_id=data["info"].get(int(message.text)))

        # запускаем description до тех пор, пока не отдаст реальное описание (descriptiontype_id = 6)
        description_api = await description_search(chat_id=message.chat.id, hotel_id=data["info"].get(int(message.text)))
        while description_api['descriptiontype_id'] != 6:
            description_api = await description_search(chat_id=message.chat.id, hotel_id=data["info"].get(int(message.text)))

        # Выдаем все фото или сообщаем об их отсутствии
        if photo_api == []:
            await message.answer(f'У выбранного отеля нет фотографий')
        else:
            for i, photo_api_i in enumerate(photo_api):
                #print(photo_api[i]["url_max"])
                await bot.send_photo(message.chat.id, photo=photo_api_i["url_max"])

        # Напоминаем о том, какой отель был выбран и выдаем информацию о нем
        # и его местоположение на сайте maps.google.com
        await message.answer(f'{data["info"].get("info" + message.text)}\n'
                             f'{description_api['description']}')
        await message.answer(f"<a href='https://maps.google.com/?q="
                             f"{data["info"].get("latitude" + message.text)},"
                             f"{data["info"].get("longitude" + message.text)}'"
                             f">Посмотреть на карте</a>",
                             parse_mode="HTML",
                             )
        await message.answer(f"Чтобы начать новый поиск, нажми кнопку.\n"
                             f"Чтобы получить информацию о другом отеле из списка, введи его номер",
                             reply_markup=gen_markup(callback_data_dict={
                                 'search': 'Начать поиск заново'
                                 # 'help': 'Помощь'
                             },
                                 button_row=1)
                             )

        #await state.set_state(MyStates.photo)

    except Exception:
        await message.answer(f'Введи номер отеля из списка')


# simple calendar usage - filtering callbacks of calendar format
@dp.callback_query(SimpleCalendarCallback.filter())
async def process_simple_calendar(callback_query: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    """
    Создаем календарь
    """
    data = await state.get_data()
    user_locale = await get_user_locale(callback_query.from_user)
    if user_locale == "ru_RU":
        user_locale += ".utf-8"
    calendar = SimpleCalendar(locale=user_locale, show_alerts=True)
    calendar.set_dates_range(datetime(data["year"], data["month"], data["day"]), datetime(data["year"]+3, 12, 31))
    selected, date = await calendar.process_selection(callback_query, callback_data)
    if selected:
        year = date.year
        month = date.month
        day = date.day
        if data.get("checkin_date"):
            checkout_date = date.strftime("%Y-%m-%d")
            await callback_query.message.answer(f'Выбрана {hbold(date.strftime("%d-%m-%Y"))}')

            logging.info(f"Пользователь: {str(callback_query.from_user.id)}, дата выезда: {checkout_date}")

            # Запрашиваем у Booking.com список валют (изначально - в переводе на Евро)
            currency_keyboard = await make_currency_keyboard(callback_query.from_user.id, currency="EUR")
            if currency_keyboard is not None:
                await callback_query.message.answer(f"Выбери или введи валюту из списка")
                for i, currency_keyboard_i in enumerate(currency_keyboard):
                    await callback_query.message.answer(":",
                                            parse_mode='html',
                                            reply_markup=gen_markup(callback_data_dict=currency_keyboard_i,
                                                                    button_row=3))

                await state.update_data(checkout_date=checkout_date)

                await callback_query.message.answer(f"Выбери или введи валюту из списка")
            else:
                await callback_query.message.answer("Не удалось получить ответ от Booking.com. Повтори поиск.")

            await state.set_state(MyStates.currency)
        else:
            checkin_date = date.strftime("%Y-%m-%d")

            logging.info(f"Пользователь: {str(callback_query.from_user.id)}, дата заезда: {checkin_date}")

            await callback_query.message.answer(f'Выбрана {hbold(date.strftime("%d-%m-%Y"))}')
            await callback_query.message.answer(f'Выбери дату выезда в календаре\n'
                                                f'или введи её в формате dd-mm-yyyy',
                reply_markup=await calendar.start_calendar(year=data["year"], month=data["month"])
                )

            await state.update_data(checkin_date=checkin_date,
                                    year=year,
                                    month=month,
                                    day=day
                                    )

            await state.set_state(MyStates.checkout_date)


@dp.callback_query(F.data == "aircond")
async def room_facility_11_handler(callback_query, state: FSMContext) -> None:
    """
    Добавляе в условия наличие кондиционера
    """
    data = await state.get_data()
    categories_filter_ids = data["categories_filter_ids"] + ",room_facility::11"

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, нужен кондиционер")

    if data['categories_filter_text'] == "":
        categories_filter_text = data["categories_filter_text"] + "кондиционер"
    else:
        categories_filter_text = data["categories_filter_text"] + ", кондиционер"
    await state.update_data(categories_filter_ids=categories_filter_ids,
                            categories_filter_text=categories_filter_text)


@dp.callback_query(F.data == "dishwasher")
async def room_facility_34_handler(callback_query, state: FSMContext) -> None:
    """
    Добавляе в условия наличие стиральной машины
    """
    data = await state.get_data()
    categories_filter_ids = data["categories_filter_ids"] + ",room_facility::34"

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, нужна стиральная машина")

    if data['categories_filter_text'] == "":
        categories_filter_text = data["categories_filter_text"] + "стиральная машина"
    else:
        categories_filter_text = data["categories_filter_text"] + ", стиральная машина"
    await state.update_data(categories_filter_ids=categories_filter_ids,
                            categories_filter_text=categories_filter_text)


@dp.callback_query(F.data == "kitchen")
async def room_facility_999_handler(callback_query, state: FSMContext) -> None:
    """
    Добавляе в условия наличие кухни/миникухни
    """
    data = await state.get_data()
    categories_filter_ids = data["categories_filter_ids"] + ",room_facility::999"

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, нужна кухня/мини-кухня")

    if data['categories_filter_text'] == "":
        categories_filter_text = data["categories_filter_text"] + "Кухня/мини-кухня"
    else:
        categories_filter_text = data["categories_filter_text"] + ", Кухня/мини-кухня"
    await state.update_data(categories_filter_ids=categories_filter_ids,
                            categories_filter_text=categories_filter_text)


@dp.callback_query(F.data == "facility")
async def room_facility_itog_handler(callback_query, state: FSMContext) -> None:
    """
    После выбора удобств в номере, создаем список с условиями запроса к Booking.com
    """
    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )
    data = await state.get_data()

    if data["sum_night"] == 10000000:
        sum_text = "без ограничений"
    else:
        sum_text = data["currency"] + " " + str(data["sum_night"])
    if data["children_count"] == 0:
        text = (f"<pre>Ищу отели в городе {hbold(data["city"])}\n"
                f"дата заезда: {hbold(data["checkin_date"])}\n"
                f"дата выезда: {hbold(data["checkout_date"])}\n"
                f"максимальная стоимость в сутки: {hbold(sum_text)}\n"
                f"количество взрослых: {hbold(data["adults_count"])}\n"
                f"количество детей: {hbold(data["children_count"])}\n"
                f"удобства в номере: {hbold(data["categories_filter_text"])}</pre>"
                )
    else:
        text = (f"<pre>Ищу отели в городе {hbold(data["city"])}\n"
                f"дата заезда: {hbold(data["checkin_date"])}\n"
                f"дата выезда: {hbold(data["checkout_date"])}\n"
                f"максимальная стоимость в сутки: {hbold(sum_text)}\n"
                f"количество взрослых: {hbold(data["adults_count"])}\n"
                f"количество детей: {hbold(data["children_count"])}\n"
                f"возраст детей: {hbold(data["children_ages"])}\n"
                f"удобства в номере: {hbold(data["categories_filter_text"])}</pre>"
                )

    await callback_query.message.answer(text=text,
                                        parse_mode='html',
                                        reply_markup=gen_markup(callback_data_dict={
                                             'itog': 'Запустить поиск',
                                             'search': 'Начать поиск заново'
                                             # 'help': 'Помощь'
                                        },
                                            button_row=2)
                                        )

    await state.set_state(MyStates.itog)


@dp.callback_query(F.data == "itog")
async def itog_handler(callback_query, state: FSMContext) -> None:
    """
    Запускаем поиск отелей по заданным условиям на Booking.com
    """

    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )

    await callback_query.message.answer(f'Идет поиск подходящих отелей, подожди немного')

    try:
        # Записываем данные в таблицу запросов
        data = await state.get_data()
        tmp = await request_create(my_dict=data)
        # Запускаем создание страниц с отелями
        result_hotels, info = await make_hotels_list(my_currency=data.get('currency'),
                                         currency_exchange=data.get('currency_exchange'),
                                         sum_night=data.get('sum_night'),
                                         chat_id=callback_query.message.chat.id,
                                         city=data.get('city'),
                                         dest_id=data.get('dest_id'),
                                         dest_type=data.get('dest_type'),
                                         checkin_date=data.get('checkin_date'),
                                         checkout_date=data.get('checkout_date'),
                                         adults_number=data.get('adults_count'),
                                         children_number=data.get('children_count'),
                                         children_ages=data.get('children_ages'),
                                         categories_filter_ids=data.get('categories_filter_ids')
                                         )
        # Выводим результат поиска пользователю
        if result_hotels != []:
            for i, result_hotel in enumerate(result_hotels):
                await callback_query.message.answer(f'<pre>{result_hotel}</pre>',
                                                            parse_mode='html')

            await callback_query.message.answer(f'Чтобы посмотреть фотографии объекта и '
                                                f'информацию о нем, введи его номер.\n'
                                                f'Чтобы начать новый поиск, нажми кнопку',
                                                reply_markup=gen_markup(callback_data_dict={
                                                    'search': 'Начать поиск заново'
                                                    # 'help': 'Помощь'
                                                },
                                                    button_row=1)
                                                )
            await state.update_data(info=info)

            await state.set_state(MyStates.photo)

        else:
            await callback_query.message.answer(f'Нет отелей, подходящих под условия.\n'
                                                f'Чтобы начать новый поиск, нажми кнопку',
                                                reply_markup=gen_markup(callback_data_dict={
                                                    'search': 'Начать поиск заново'
                                                    # 'help': 'Помощь'
                                                },
                                                    button_row=1)
                                                )
            await state.set_state(MyStates.city)

    except IntegrityError as error:
        await callback_query.message.answer(f'Произошла ошибка при записи данных в базу.\n'
                                            f'Начни поиск заново, нажмав на кнопку',
                                            reply_markup=gen_markup(callback_data_dict={
                                                'search': 'Начать поиск заново'
                                                # 'help': 'Помощь'
                                            },
                                                button_row=1)
                                            )
        await state.set_state(MyStates.city)


@dp.callback_query(F.data == "search")
async def search_handler(callback_query, state: FSMContext):
    """
    Запускаем новый поиск по нажатию на кнопку "Начать поиск заново"
    """
    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, запустил новый поиск")

    req_keyboard = await user_history(callback_query.from_user.id)
    #Если у пользователя уже есть история поиска, то покажем её
    if req_keyboard:
        text = f"<pre>Введи новый город для поиска или выбери из истории поиска</pre>"
        await callback_query.message.answer(text,
                             parse_mode='html',
                             reply_markup=gen_markup(callback_data_dict=req_keyboard, button_row=1))
    else:
        text = f"Введи новый город для поиска"
        await callback_query.message.answer(text, parse_mode='html')

    await state.set_state(MyStates.city)


@dp.callback_query(F.data.startswith("hist"))
async def history_handler(callback_query, state: FSMContext):
    """
    Очищаем все данные и подтягиваем выбранныые из историю поиска
    """
    requests = await get_history(int(callback_query.data[4:]))
    # Очищаем всю информацию для поиска
    await state.clear()
    data = await state.get_data()
    # И записываем туда выбранную из истории
    user_id = callback_query.from_user.id
    city = requests.city
    dest_id = requests.dest_id
    dest_type = requests.dest_type
    checkin_date = requests.checkin_date
    checkout_date = requests.checkout_date
    await state.update_data(user_id=user_id,
                            categories_filter_ids="property_type::204,property_type::201,property_type::220,property_type::213,property_type::219,reviewscorebuckets::80,reviewscorebuckets::90,reviewscorebuckets::999,free_cancellation::1",
                            categories_filter_text="",
                            city=city,
                            dest_id=dest_id,
                            dest_type=dest_type,
                            checkin_date=checkin_date,
                            checkout_date=checkout_date
                            )

    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, выбрал из истории: {city}, {checkin_date} - {checkout_date}")

    await callback_query.message.answer(f'Выбрано: {city}, '
                                        f'{checkin_date} - {checkout_date}',
                                        parse_mode='html')
    # Запрашиваем у Booking.com список валют (изначально - в переводе на Евро)
    currency_keyboard = await make_currency_keyboard(callback_query.from_user.id, currency="EUR")
    if currency_keyboard is not None:
        await callback_query.message.answer(f"Выбери или введи валюту из списка")
        for i, currency_keyboard_i in enumerate(currency_keyboard):
            await callback_query.message.answer(":",
                                 parse_mode='html',
                                 reply_markup=gen_markup(callback_data_dict=currency_keyboard_i,
                                 button_row=3))

        await callback_query.message.answer(f"Выбери или введи валюту из списка")
    else:
        await callback_query.message.answer("Не удалось получить ответ от Booking.com. Повтори поиск.")

    await state.set_state(MyStates.currency)


@dp.callback_query(F.data.startswith("curr"))
async def currency_choose_handler(callback_query, state: FSMContext):
    """
    Выбор валюты из списка
    """
    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id - 1,
            reply_markup=None
        )
    except TelegramBadRequest:
        pass
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id + 1,
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    data = await state.get_data()
    currency = callback_query.data[5:]

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, валюта: {currency}")

    # Запрашиваем у Booking.com курсы валют относительно выбранной валюты
    currency_response = await get_currency(callback_query.from_user.id,
                                           currency=callback_query.data[5:])
    currency_exchange = dict()
    currency_exchange["curr_" + currency] = "1"
    # Создаем список валют для пересчета цен отеля (добавляем выбранную валюту с курсом 1)
    for elem in currency_response["exchange_rates"]:
        currency_exchange["curr_" + elem["currency"]] = elem["exchange_rate_buy"]
    await callback_query.message.answer(f"Введи максимальную сумму в {currency} за сутки (всего планируется "
                     f"{(datetime.strptime(data['checkout_date'], '%Y-%m-%d') -
                         datetime.strptime(data['checkin_date'], '%Y-%m-%d')).days} сут.).\n"
                     f"Введи 0, если не хочешь ограничивать сумму.")

    await state.update_data(currency=currency, currency_exchange=currency_exchange)

    await state.set_state(MyStates.sum_night)


@dp.callback_query(F.data.startswith("city"))
async def city_choose_handler(callback_query, state: FSMContext):
    """
    Выбор места для поиска из списка
    """
    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )
    data = await state.get_data()

    #dest_id = callback_query.data[callback_query.data.find("city") + 4:callback_query.data.find("@")]
    dest_id = callback_query.data[callback_query.data.find("city") + 4:]
    city = data["cities"].get(dest_id)[0]
    dest_type = data["cities"].get(dest_id)[1]
    year = datetime.now().year
    month = datetime.now().month
    day = datetime.now().day
    date_today = datetime.now()

    logging.info(f"Пользователь: {str(callback_query.from_user.id)}, выбранная локация: {city}")

    user_locale = await get_user_locale(callback_query.from_user)
    if user_locale == "ru_RU":
        user_locale += ".utf-8"
    calendar = SimpleCalendar(locale=user_locale, show_alerts=True)
    calendar.set_dates_range(datetime(year, month, day), datetime(year+3, 12, 31))
    await callback_query.message.answer(f"Будем искать отель в {city}\n", reply_markup=None)
    await callback_query.message.answer(
        f"Выбери дату заезда в календаре\nили введи её в формате dd-mm-yyyy",
        reply_markup=await calendar.start_calendar(year=year, month=month)
    )
    await state.update_data(city=city,
                            dest_id=dest_id,
                            dest_type=dest_type,
                            year=year,
                            month=month,
                            day=day,
                            date_today=date_today
                            )

    await state.set_state(MyStates.checkin_date)
