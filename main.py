import configparser
import logging
import random
from typing import Tuple, Optional

from telegram import Update, Chat, ChatMember, ParseMode, ChatMemberUpdated
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    ChatMemberHandler,
    MessageHandler,
    Filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


roles = [
    'мафия',
    'житель',
    'доктор',
    'комиссар',
    'маньяк',
    'любовница'
]


def get_roles(count_of_players: int) -> list:
    if 3 <= count_of_players <= 5:
        return [roles[0]] + [roles[1]] * (count_of_players - 1)
    if 6 <= count_of_players <= 8:
        return [roles[0], roles[0], roles[2]] + [roles[1]] * (count_of_players - 3)
    if 9 <= count_of_players <= 11:
        return [roles[0], roles[0], roles[0], roles[2], roles[3]] + [roles[1]] * (count_of_players - 5)


def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> Optional[Tuple[bool, bool]]:
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.CREATOR,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.CREATOR,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


def track_chats(update: Update, context: CallbackContext) -> None:
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result
    cause_name = update.effective_user.full_name
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            logger.info("%s started the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
    else:
        if not was_member and is_member:
            logger.info("%s added the bot to the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).discard(chat.id)


def greet_chat_members(update: Update, context: CallbackContext) -> None:
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()

    if not was_member and is_member:
        update.effective_chat.send_message(
            f"{member_name} was added by {cause_name}. Welcome!",
            parse_mode=ParseMode.HTML,
        )
    elif was_member and not is_member:
        update.effective_chat.send_message(
            f"{member_name} is no longer with us. Thanks a lot, {cause_name} ...",
            parse_mode=ParseMode.HTML,
        )


def ban_word_command(update: Update, context: CallbackContext):
    if update.effective_message.text == 'плохое слово':
        update.effective_message.delete()
        update.effective_user.send_message('больше так не делай!')


def start_command(update: Update, context: CallbackContext):
    context.bot_data[update.effective_chat.id] = {}
    context.bot_data[update.effective_chat.id]['is_started'] = True
    context.bot_data[update.effective_chat.id]['is_joining'] = True
    context.bot_data[update.effective_chat.id]['players'] = []
    update.effective_chat.send_message('игра началась, отправьте (играю) те кто в игре')


def new_game_member_command(update: Update, context: CallbackContext):
    if update.effective_chat.id not in context.bot_data:
        return

    if context.bot_data[update.effective_chat.id]['is_started'] \
            and context.bot_data[update.effective_chat.id]['is_joining']:
        if update.effective_user not in context.bot_data[update.effective_chat.id]['players']:
            update.effective_chat.send_message('ты в игре')
            context.bot_data[update.effective_chat.id]['players'].append(
                {
                    'user': update.effective_user,
                    'role': None
                }

            )
        else:
            update.effective_chat.send_message('ты уже играешь')


def end_of_joining_command(update: Update, context: CallbackContext):
    if update.effective_chat.id not in context.bot_data and not context.bot_data[update.effective_chat.id]['is_started']:
        return

    count_of_players = len(context.bot_data[update.effective_chat.id]['players'])
    if 2 < count_of_players < 12:
        context.bot_data[update.effective_chat.id]['is_joining'] = False
        current_roles = get_roles(count_of_players)
        for i in context.bot_data[update.effective_chat.id]['players']:
            a = random.choice(current_roles)
            i['user'].send_message(a)
            i['role'] = a
            current_roles.remove(a)
    else:
        update.effective_chat.send_message('Недостаточно игроков или превышает допустимое значение')




def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    updater = Updater(token=config['Bot']['token'])
    dispatcher = updater.dispatcher
    dispatcher.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    dispatcher.add_handler(CommandHandler('start', start_command))
    dispatcher.add_handler(CommandHandler('end_join', end_of_joining_command))
    dispatcher.add_handler(MessageHandler(filters=Filters.regex('играю'), callback=new_game_member_command))
    dispatcher.add_handler(MessageHandler(filters=Filters.text, callback=ban_word_command))
    dispatcher.add_handler(ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER))
    updater.start_polling(allowed_updates=Update.ALL_TYPES)
    updater.idle()


if __name__ == '__main__':
    main()