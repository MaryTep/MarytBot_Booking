from aiogram.fsm.context import FSMContext
from aiogram import F, Router

from loader import bot
#from aiogram.filters import Command
#from aiogram.types import Message
#from config_data.config import DEFAULT_COMMANDS

router = Router()

# @router.message(F.text, Command("help"))
# async def command_start_handler(message: Message) -> None:
#     text = [f"/{command} - {desk}" for command, desk in DEFAULT_COMMANDS]
#     await message.answer("\n".join(text))


@router.callback_query(F.data == "help")
async def help_handler(callback_query, state: FSMContext):

    # Удаляем клавиатуру.
    await bot.edit_message_reply_markup(
        chat_id=callback_query.from_user.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )

    await callback_query.message.answer(f'HELP будет написан позже', parse_mode='html')
    await state.clear()
