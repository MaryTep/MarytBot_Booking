from database.models import User, Request
from typing import Dict


async def user_create(user_id: int, username: str, first_name: str, last_name: str) -> None:
    """
    Записываем в базу нового пользователя
    """
    User.create(
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )


async def request_create(my_dict: Dict) -> None:
    """
    Записываем в базу новый запрос от пользователя
    """
    new_request = Request(**my_dict)
    new_request.save()
