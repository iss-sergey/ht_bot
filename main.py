import telebot
from telebot import types
import settings
from keyboa import Keyboa
import sqlite3 as sql
import datetime

TOKEN = settings.token


bot = telebot.TeleBot(TOKEN)


# Создает запрос в db
def set_sql_query(sql_query):
    with sql.connect('habittracker.db') as sql_con:
        sql_con.row_factory = sql.Row
        cursor = sql_con.cursor()
        cursor.execute(sql_query)
        date_today = datetime.date.today()
        habits_list = []
        for row in cursor:
            habit_date_checked = None
            if row['date_checked']:
                year, mont, day = [int(n) for n in row['date_checked'].split('-')]
                habit_date_checked = datetime.date(year, mont, day)

            status = '-' if not habit_date_checked or (date_today - habit_date_checked).days != 0 else '+'
            habit = {'rowid': row['rowid'],
                     'name': row['name'],
                     'status': status,
                     'date_checked': row['date_checked']}
            habits_list.append(habit)
        return habits_list


# Проверяет коректность введенной команды
def is_command_correct(user_command, message):
    if len(user_command) <= 1:
        bot.send_message(message.chat.id, 'Команда введена не корректно.')
        return False
    return True


# Загружает данные из базы
def load_from_db(table_name):
    query = f"SELECT ROWID, * FROM '{table_name}'"
    return set_sql_query(query)


def form_habit_list_message(table_name):
    habits_list = load_from_db(table_name)
    if habits_list:
        text_message = f'<b>Список привычек</b>\n\n'.upper()
        for number, row in enumerate(habits_list, start=1):
            mark = '\u2705' if row['status'] == '+' else '\u274C'
            sep = '  ' if number < 10 else ''
            text_message += f'<b>{number}{sep}</b> - <b>{mark}</b> {row["name"]} <b>ID {row["rowid"]}</b>\n'
        buttons = [{'Отметить': 'check'}, {'Снять отметку': 'uncheck'}, {'Удалить': 'dell'}]
        in_line_kb = Keyboa(items=buttons, items_in_row=2)
        return {'text_message': text_message, 'in_line_kb': in_line_kb()}

    return False


@bot.message_handler(func=lambda msg: msg.text == 'Справка')
@bot.message_handler(commands='start')
def start(message):
    bot.delete_message(message.chat.id, message.id)
    kboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_show_habitlist = types.KeyboardButton('Список привычек')
    bth_help = types.KeyboardButton('Справка')
    kboard.add(btn_show_habitlist, bth_help)

    message_text = """Для добавления новой привычки введите знак \u2795 и далее наименование привычки"""

    bot.send_message(message.chat.id, message_text, reply_markup=kboard)


@bot.message_handler(func=lambda msg: True)
def user_commands(message):
    table_name = message.chat.id
    command = message.text.strip()

    if command[0] == '+' and is_command_correct(command, message):
        query1 = f"""CREATE TABLE IF NOT EXISTS "{table_name}"(
                         name TEXT NOT NULL,
                         date_checked TEXT)"""
        query2 = f"INSERT INTO '{table_name}' VALUES ('{command[1:].strip()}', NULL)"

        set_sql_query(query1)
        set_sql_query(query2)
        bot.send_message(message.chat.id, 'Привычка успешно добавлена.')

        habit_list_message = form_habit_list_message(table_name)
        if not habit_list_message:
            bot.send_message(message.chat.id, 'Список привычек пуст.')
        else:
            bot.send_message(message.chat.id, habit_list_message['text_message'],
                             reply_markup=habit_list_message['in_line_kb'], parse_mode="HTML")

    elif command == 'Список привычек':
        bot.delete_message(message.chat.id, message.id)

        habit_list_message = form_habit_list_message(table_name)
        if not habit_list_message:
            bot.send_message(message.chat.id, 'Список привычек пуст.')
        else:
            bot.send_message(message.chat.id, habit_list_message['text_message'],
                             reply_markup=habit_list_message['in_line_kb'], parse_mode="HTML")


@bot.callback_query_handler(func=lambda cbm: cbm.data)
def used_inline_kb(callback, ):
    table_name = callback.message.chat.id
    habits_list = load_from_db(table_name)
    # Выводит сообщение с информацией какое действие будет выполнено и клавиатуру с выбором номера привычки
    if callback.data in ('check', 'uncheck', 'dell'):
        action_name = {'check': ('которой нужно поставить отметку о выполнении.',
                                 [i for i, elem in enumerate(habits_list, start=1) if elem['status'] == '-']),
                       'uncheck': ('с которой нужно снять отметку о выполнении.',
                                   [i for i, elem in enumerate(habits_list, start=1) if elem['status'] == '+']),
                       'dell': ('которую нужно удалить.',
                                [i for i, _ in enumerate(habits_list, start=1)])}
        buttons = action_name[callback.data][1]
        habits_number_kb = Keyboa(items=buttons,
                                  items_in_row=6,
                                  back_marker=f'_{callback.data}')
        bot.send_message(callback.message.chat.id,
                         f'Выберете номер привычки {action_name[callback.data][0]}',
                         reply_markup=habits_number_kb())
    # Выводмт вопрос о подтверждении удаления привычки
    else:
        if callback.data.endswith('_dell'):
            # habit_number хранит номер выбранной привычки в списке
            habit_number = int(callback.data[:-5]) - 1
            # habit_id хранит ID записи в базе, которую нужно удалить
            habit_id = habits_list[habit_number]['rowid']
            buttons = [{'Да': 'y'}, {'Нет': 'n'}]
            yes_no_kb = Keyboa(items=buttons, items_in_row=2, back_marker=f'dell_{habit_id}')
            bot.edit_message_text(chat_id=callback.message.chat.id,
                                  message_id=callback.message.id,
                                  text=f'Вы действтельно хотите удалить привычку '
                                       f'<i><b>{habits_list[habit_number]["name"]}</b></i>',
                                  reply_markup=yes_no_kb(),
                                  parse_mode='HTML')
        # Удаляет привычку при подтвержении
        elif callback.data.startswith('ydell_'):
            bot.delete_message(callback.message.chat.id, callback.message.id)
            habit_id = int(callback.data[6:])
            query = f"DELETE FROM '{table_name}' WHERE ROWID == {habit_id}"
            set_sql_query(query)
            bot.edit_message_text(chat_id=callback.message.chat.id,
                                  message_id=callback.message.id - 1,
                                  text='Привычка удалена')
        # Устанавливает полю date_checked(дата последнего выполнения) текущую дату
        elif callback.data.endswith('_check'):

            bot.delete_message(callback.message.chat.id, callback.message.id)

            # habit_id хранит ID записи в базе, которой нужно поставить отметку выполнено
            habit_id = habits_list[int(callback.data[:-6]) - 1]['rowid']
            date_today = datetime.date.today()
            query = f"UPDATE '{table_name}' SET date_checked='{date_today}'  WHERE ROWID == {habit_id}"
            set_sql_query(query)
        # Устанавливает полю date_checked(дата последнего выполнения) значение NULL
        elif callback.data.endswith('_uncheck'):

            bot.delete_message(callback.message.chat.id, callback.message.id)

            # habit_id хранит ID записи в базе, которой нужно поставить отметку выполнено
            habit_id = habits_list[int(callback.data[:-8]) - 1]['rowid']
            query = f"UPDATE '{table_name}' SET date_checked=NULL  WHERE ROWID == {habit_id}"
            set_sql_query(query)

        habit_list_message = form_habit_list_message(table_name)
        if not habit_list_message:
            bot.send_message(callback.message.chat.id, 'Список привычек пуст.')
        else:
            bot.send_message(callback.message.chat.id, habit_list_message['text_message'],
                             reply_markup=habit_list_message['in_line_kb'], parse_mode="HTML")


bot.polling()
