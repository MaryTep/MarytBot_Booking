from .models import User, Request
from typing import Dict
import re

async def user_history(user_id: int) -> Dict:

    # Создаем историю поиска, если она существует (не более 10 последних поисков)
    user = User.get(User.user_id == user_id)
    requests = user.requests.order_by(-Request.request_id).limit(10)
    if requests != {}:
        req_keyboard = dict()
        for req in requests:
            req_str = str(req)
            req_keyboard["hist" + re.search(r'\d*', req_str).group()] = \
                (req_str)[len(re.search(r'\d*', req_str).group()) + 2:]
        return req_keyboard


async def get_history(request_id):
    response = Request.get(Request.request_id == request_id)
    return response

