from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def gen_markup(callback_data_dict: dict, button_row: int = 3) -> InlineKeyboardMarkup:
    """
    Создаём инлайн-клавиатуру таким образом, чтобы в строке было не более,
    чем button_row кнопок.
    В последней строке кнопок может быть меньше, чем в остальных
    """

    # Из переданного словаря создаем кнопки: ключ словаря - callback_query кнопки,
    # значение - надпись на кнопке
    buttons = [InlineKeyboardButton(
        text=value, callback_data=str(key)) for key, value in callback_data_dict.items()]
    # Определяем количество строк клавиатуры
    if len(buttons) % button_row != 0:
        rows_count = len(buttons) // button_row + 1
    else:
        rows_count = len(buttons) // button_row

    # Создаём кнопки построчно
    buttons_itog = list()
    for i in range(rows_count):
        buttons_itog.append([buttons[i * button_row]])
        for j in range(1, button_row):
            if i * button_row + j < len(buttons):
                buttons_itog[i].append(buttons[i * button_row + j])

    # Создаём объект клавиатуры, добавляя в него кнопки.
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons_itog)

    return keyboard
