import logging
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from aiogram import Router

from peewee import IntegrityError
from loader import bot
from states.states import MyStates
from database.save_user_info import user_create
from database.get_user_info import user_history
from keyboards.inline.inline_keyboards import gen_markup

router = Router()

# Когда пользователь отправляет команду `/start`, здороваемся
# и предлагаем запустить поиск города
@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """
    В этот хендлер попадаем по команде `/start`
    """

    # logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="a",
    #                 format="%(asctime)s %(levelname)s %(message)s")

    # Удаляем клавиатуру, если она была.
    try:
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id - 1,
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    logging.info(f"Вошел пользователь: {str(user_id)} | {str(username)} | {str(first_name)} | {str(last_name)}")

    try:
        tmp = await user_create(user_id=user_id, username=username, first_name=first_name, last_name=last_name)

        await message.answer(f"Добро пожаловать, {hbold(first_name)}!\n"
                             f"Я - бот для поиска апартаментов на сайте Booking.com.\nВведи город для поиска",
                             parse_mode='html')

    # если такой пользователь уже есть в базе
    except IntegrityError:
        await message.answer(f"Рад тебя снова видеть, {hbold(first_name)}!\n")
        req_keyboard = await user_history(user_id)
        # Если у пользователя уже есть история поика
        if req_keyboard:
            text = f"<pre>Введи новый город для поиска или выбери из истории поиска</pre>"
            await message.answer(text,
                                 parse_mode='html',
                                 reply_markup=gen_markup(callback_data_dict=req_keyboard, button_row=1))
        else:
            text = f"Введи новый город для поиска"
            await message.answer(text, parse_mode='html')

    # Переходим к вводу места бронирования (отель, город, регион и т.п.)
    await state.set_state(MyStates.city)
