from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    InternalError
)
import os

# Создаем или открываем базу данных Database.db в том же каталоге, где находится файл models.py
db = SqliteDatabase(os.path.dirname(os.path.realpath(__file__)) + "\\Database.db",
                    pragmas={'foreign_keys': 1})


class BaseModel(Model):
    """
    Базовый класс моделей, связанных с базой данных
    """
    class Meta:
        database = db


class User(BaseModel):
    """
    Пользователи
    """
    user_id = IntegerField(primary_key=True)
    username = CharField(max_length=100, null=True)
    first_name = CharField(max_length=100)
    last_name = CharField(max_length=100, null=True)


class Request(BaseModel):
    """
    Запросы от пользователей к Booking.com, связка с пользователями по полю user
    """
    request_id = AutoField()
    user = ForeignKeyField(User, backref="requests")
    city = CharField(max_length=100)
    dest_id = CharField(max_length=10)
    dest_type = CharField(max_length=20)
    checkin_date = CharField(max_length=10)
    checkout_date = CharField(max_length=10)
    sum_night = CharField(max_length=10)
    adults_count = CharField(max_length=2)
    children_count = CharField(max_length=2)
    children_ages = CharField(max_length=20)
    categories_filter_ids = CharField(max_length=300)
    categories_filter_text = CharField(max_length=60, null=True)

    def __str__(self) -> str:
        """
        Строка, которая будет выводиться для запроса истории поиска
        """
        return ("{request_id}. {city}, {checkin_date} - {checkout_date}, "
                # "сумма за сутки: {sum_night}, взрослых: {adults_count}, "
                # "детей: {children_count}, возраст детей: {children_ages}, "
                # "удобства в номере: {categories_filter_text}"
                ).format(
            request_id=self.request_id,
            city=self.city,
            checkin_date=self.checkin_date,
            checkout_date=self.checkout_date,
            # sum_night=self.sum_night,
            # adults_count=self.adults_count,
            # children_count=self.children_count,
            # children_ages=self.children_ages,
            # categories_filter_text=self.categories_filter_text,
        )


def create_models() -> None:
    """
    Создаем все таблицы в базе данных, если их еще нет
    """
    try:
        db.create_tables(BaseModel.__subclasses__())
    except InternalError as px:
        print(str(px))

    # for user in User:
    #     print(user.user_id, " | ", user.username, " | ", user.first_name, " | ", user.last_name)
    #
    # User.delete().where(User.user_id == 1986356126).execute()
    #
    # user = User.get(User.user_id == 1986356126)
    # request = Request.get(Request.request_id > 3 & Request.user == user)
    # Request.delete().where((Request.request_id > 15) & (Request.user == user)).execute()
    # for request in Request:
    #     print(request.request_id, " | ", request.user)
