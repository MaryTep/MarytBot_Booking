import logging
import asyncio

import loader
import handlers
from database.models import create_models


async def main() -> None:

    create_models()
    bot = loader.bot
    dp = loader.dp
    dp.include_router(handlers.default_handlers.start.router)
    dp.include_router(handlers.custom_handlers.custom_handlers.router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
    #await dp.start_polling(bot, allowed_updates=[])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main())

