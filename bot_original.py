import logging
import os
import asyncio
import emoji
import uuid

from html import escape
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

from classify import classify_message, train, dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

bot = Bot(os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранилище сообщений, которые были классифицированы как спам для обработки ложных срабатываний (автоматически очищается каждые 24 часа)
messagesBySession = {}
message_storage = {}


# Обработка любых сообщений в ЛС бота
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.reply("❌ Бот не предназначен для работы в личных сообщениях!")


# Команда для добавления фразы в датасет
@dp.message(Command("add"))
async def add(message: types.Message, command: CommandObject):
    if message.chat.id != int(os.getenv("JOURNAL_CHAT_ID")):
        await message.reply("❌ Нет доступа")
        return

    args = command.args

    if args is not None:
        message_id = str(uuid.uuid4())
        message_storage[message_id] = args  # Сохраняем сообщение в хранилище

        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="Спам", callback_data=f"add:spam:{message_id}"))
        keyboard.add(InlineKeyboardButton(text="Не спам", callback_data=f"add:ham:{message_id}"))

        await message.reply(
            f"<b>Выберите тип сообщения</b>\n\n<blockquote>{args}</blockquote>\n\nHAM - не спам, SPAM - спам",
            reply_markup=keyboard.as_markup())


# Обработка выбора Спам/Не спам при добавлении
@dp.callback_query(F.data.startswith("add:"))
async def add_callback(callback: CallbackQuery):
    data = callback.data.split(":")
    category = data[1]  # spam или ham
    message_id = data[2]  # uuid сообщения

    message_text = message_storage.get(message_id)

    if message_text is None:
        await callback.answer("❌ Сообщение не найдено.")
        return

    confirmation_keyboard = InlineKeyboardBuilder()
    confirmation_keyboard.add(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_add:{category}:{message_id}"))
    confirmation_keyboard.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_add"))

    await callback.message.edit_text(
        f"Вы уверены, что хотите добавить это сообщение как {category.upper()}?\n\n<blockquote>{message_text}</blockquote>",
        reply_markup=confirmation_keyboard.as_markup())
    await callback.answer()


# Подтверждение добавления
@dp.callback_query(F.data.startswith("confirm_add:"))
async def confirm_add(callback: CallbackQuery):
    data = callback.data.split(":")
    category = data[1]  # spam или ham
    message_id = data[2]  # уникальный идентификатор сообщения

    # Получаем текст сообщения из хранилища
    message_text = message_storage.get(message_id)

    if message_text is None:
        await callback.answer("❌ Сообщение не найдено")
        return

    # Запись в файл
    with open(dataset, 'a', encoding='utf-8') as f:
        message_text = ' '.join(message_text.splitlines())

        f.write(f"\n{category} {message_text}")

    await callback.message.edit_text("Обработка...", parse_mode=None)

    await callback.message.edit_text(
        f"✅ Сообщение было добавлено как {category}, модель переобучается\n\n<blockquote>{message_text}</blockquote>\n\n<b>Тестовая точность: {(train("r") * 100):.0f}%</b>")
    del message_storage[message_id]

        @ dp.callback_query(F.data == "cancel_add")
    async

    def cancel_add(callback: CallbackQuery):
        await callback.answer("Добавление отменено")
        await callback.message.delete()

    # Самый важный хендлер - обработка всех сообщений (занимает около полусекунды при тарифе "Стандартный", с "Начальным +" иногда уходит в желтую зону)
    @dp.message()
    async def check_spam(message: types.Message):
        if message.chat.type == "private" or message.chat.id != int(os.getenv("CHAT_IDS")):
            return

        # Проверка пересланного сообщения
        if not await msg_from_group(message) and (message.forward_from and message.forward_from.is_bot) or (
                message.forward_from_chat and message.forward_from_chat.id not in [int(os.getenv("CHAT_IDS")),
                                                                                   int(os.getenv(
                                                                                           "CHANNEL_ID"))] and message.forward_from_chat.type == "channel"):
            await message.delete()
            await send_log(message, "forwarded_from_")
            return

        # Классификация сообщения (спам/не спам) и проверка является ли пользователь админом (т.к. у нас все пишут от лица группы - сделаем проверку на ID группы)
        elif not await msg_from_group(message) and classify_message(message.text):
            await message.delete()
            await send_log(message, "classify")
            return

        # Проверка наличия эмодзи в сообщении
        if not await msg_from_group(message) and check_emojis(message.text):
            await message.delete()
            await send_log(message, "emoji_spam")
            return

    # Кнопка "Ложное!" в чате журнала
    @dp.callback_query(F.data.startswith("false:"))
    async def false(callback: CallbackQuery):
        message_id = int(callback.data.split(":")[1])

        if message_id in messagesBySession:
            original_msg = messagesBySession[message_id][0]
            sended_msg = messagesBySession[message_id][1]

            with open(dataset, 'a', encoding='utf-8') as f:
                edited_text = ' '.join(original_msg.text.splitlines())

                f.write(f"\nham {edited_text}")
            await callback.message.edit_text("Обработка...", parse_mode=None)
            await sended_msg.edit_text(
                text=f"✅ Срабатывание отмечено как ложное, датасет обновлен, модель переобучается.\n\n<blockquote>Сообщение: <i>{escape((original_msg.text if original_msg.text else original_msg.caption if original_msg.caption else "
            текст
            сообщения
            отсутствует
            "))}</i></blockquote>\n\n<b>Тестовая точность: {(train("r") * 100):.0f}%</b>")
            else:
            await callback.answer("Произошла ошибка: сообщение не найдено в словаре")

            # Исключение пользователя по кнопке в чате журнала
            @ dp.callback_query(F.data.startswith("ban:"))
            async

            def false(callback: CallbackQuery):

                message_id = int(callback.data.split(":")[1])

            if message_id in messagesBySession:
                original_msg = messagesBySession[message_id][0]
                sended_msg = messagesBySession[message_id][1]
                reason = messagesBySession[message_id][2]

                try:
                    await bot.ban_chat_member(original_msg.chat.id, original_msg.from_user.id)
                    await callback.answer("Спамер заблокирован навсегда")
                except:
                    await callback.answer("Произошла ошибка")

                await sended_msg.edit_text(
                    text=f"🚫 Удалено подозрительное сообщение от <b><a href='tg://user?id={original_msg.from_user.id}'>{original_msg.from_user.first_name}</a>, а спамер заблокирован по решению {callback.from_user.first_name}</b>!\n\n<blockquote>Сообщение: <i>{escape((original_msg.text if original_msg.text else original_msg.caption if original_msg.caption else "
                текст
                сообщения
                отсутствует
                "))}</i></blockquote>\n\nПричина удаления: <b>{reason}</b>")
                else:
                await callback.answer("Произошла ошибка: сообщение не найдено в словаре")

                # Очистка хранилища каждые 24 часа
                async

                def clear_messages_by_session():

                    while True:
                        # Очищаем хранилище
                        messagesBySession.clear()
                        message_storage.clear()
                        logger.info("Хранилище сообщений очищено.")

                        # Ждем 24 часа до следующей очистки
                        await asyncio.sleep(24 * 60 * 60)  # 24 часа в секундах

            async def msg_from_group(message: types.Message):
                return True if str(message.from_user.id) == "1087968824" else False

            # Отправка "лога" в чат журнала
            async def send_log(message: types.Message, type: str):
                user_id = message.from_user.id

                # Можно обернуть в match case для большей читаемости
                reason = "зафиксирован спам" if type == "classify" else "сообщение переслано от канала или бота" if type == "forwarded_from_" else "сообщение подержит в себе 3 или более эмодзи подряд"

                msg = f"🚫 Удалено подозрительное сообщение от <b><a href='tg://user?id={user_id}'>{message.from_user.first_name}</a></b>!\n\n<blockquote>Сообщение: <i>{escape((message.text if message.text else message.caption if message.caption else "
                текст
                сообщения
                отсутствует
                "))}</i></blockquote>\n\nПричина удаления: <b>{reason}</b>"

                sended_msg = await bot.send_message(int(os.getenv("JOURNAL_CHAT_ID")), msg,
                                                    reply_markup=await markup(message, True,
                                                                              True) if type == "classify" else await markup(
                                                        message, False, True))

                messagesBySession[message.message_id] = message, sended_msg, reason
                logging.info("Сообщение отправлено!")

                # Сообщение пользователю о причине удаления его сообщения
                if type == "emoji_spam":
                    rmsg = await message.answer(
                        f"<b>{message.from_user.full_name}</b>, ваше сообщение удалено, так как оно содержит три или более эмодзи")

                await asyncio.sleep(15)
                await rmsg.delete()

                # Стандартный markup кнопок для чата журнала
                async

                def markup(message: types.Message, withFalse: bool, withBan: bool):
                    builder = InlineKeyboardBuilder()

                    builder.add(InlineKeyboardButton(text="❗️Ложное",
                                                     callback_data=f"false:{message.message_id}")) if withFalse else None
                    builder.add(InlineKeyboardButton(text="⛔️ Исключить",
                                                     callback_data=f"ban:{message.message_id}")) if withBan else None

                    if not withBan and not withBan:
                        return None
                    return builder.as_markup()

                # проверка, есть ли в сообщении 3 или более ЛЮБЫХ эмодзи
                def check_emojis(text):
                    emojis = [char for char in text if emoji.is_emoji(char)]

                    for i in range(len(emojis) - 2):
                        if emojis[i] and emojis[i + 1] and emojis[i + 2]:
                            return True
                    return False

                async def main():
                    train("nr")

                    asyncio.create_task(clear_messages_by_session())

                    await bot.delete_webhook(drop_pending_updates=True)
                    await dp.start_polling(bot)

                asyncio.run(main())