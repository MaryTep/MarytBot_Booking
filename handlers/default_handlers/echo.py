from aiogram.types import Message

from aiogram import Router
from aiogram.fsm.context import FSMContext

router = Router()


# Эхо хендлер, куда летят текстовые сообщения без указанного состояния
@router.message()
async def bot_echo_handler(message: Message, state: FSMContext):
    await message.answer(f"Эхо без состояния или фильтра.\nСообщение: {message.text}, {await state.get_state()}")


