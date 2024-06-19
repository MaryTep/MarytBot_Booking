from aiogram.fsm.state import State, StatesGroup


class MyStates(StatesGroup):
    base = State()
    start = State()
    user_id = State()
    cities = State()
    city = State()
    history = State()
    checkin_date = State()
    checkout_date = State()
    currency = State()
    currency_exchange = State()
    sum_night = State()
    adults = State()
    children = State()
    children_ages = State()
    info = State()
    room_facility = State()
    categories_filter_ids = State()
    categories_filter_text = State()
    itog = State()
    photo = State()
    year = State()
    month = State()
    day = State()
    date_today = State

#    echo = State()
