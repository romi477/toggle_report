# python3

from collections import defaultdict
from datetime import datetime
import logging
import re

from dateutil.relativedelta import relativedelta
from requests.auth import HTTPBasicAuth
import requests


_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)

channel = logging.StreamHandler()
formatter = logging.Formatter('\n[%(levelname)s] %(message)s')

channel.setFormatter(formatter)
_log.addHandler(channel)

WORKSPACE = 000000
TOKEN = 'xxxxxxxxxxxxxxxxxxxx'

HEADERS = {
    'content-type': 'application/json',
}
PARAMS = {
    'workspace_id': WORKSPACE,
    'since': '2022-04-01',
    'until': '2022-05-01',
    'user_agent': 'api_test',
}
SUMMARY_URL = 'https://api.track.toggl.com/reports/api/v2/summary'


def format_date(rdate):
    year = rdate[-2:]
    month = rdate[2:4]
    day = rdate[:2]
    return f'20{year}-{month}-{day}'


def calculate_date(since, until):
    if not until:
        pattern = '%d%m%y'
        last_month_day = datetime.strptime(since, pattern) + relativedelta(day=31)
        until = last_month_day.date().strftime(pattern)

    return format_date(since), format_date(until)


def fetch_data(since, until):
    input_params = {
        'since': since,
        'until': until,
    }
    response = requests.get(
        SUMMARY_URL,
        params={**PARAMS, **input_params},
        headers=HEADERS,
        auth=HTTPBasicAuth(TOKEN, 'api_token'),
    )

    if response.ok:
        return response.json()

    raise Exception(response.text)


def parse_item_name(title, parse_task=False):
    entry_list = re.findall(r'\[(.*?)\]', title.get('time_entry', str()))
    task_code = (entry_list and entry_list[0] or str()).upper()

    if parse_task:
        return task_code

    project_code = task_code.split('-')
    project_name = project_code and project_code[0] or str()
    return project_name


def parse_item(item, parse_task=False):
    item_name = parse_item_name(
        item.get('title', dict()),
        parse_task=parse_task,
    )
    return item_name, item.get('time', int())


def analyze_data(data_list, parse_task=False):
    data_dict = defaultdict(list)

    for data in data_list:
        total_time = data.get('time', int())
        data_dict['total_time'].append(total_time)

        for item in data.get('items', []):
            item_key, item_value = parse_item(item, parse_task=parse_task)
            data_dict[item_key].append(item_value)

    return data_dict


def print_data(name, vals_list):
    seconds = sum(vals_list)
    hours = seconds // 3600000
    minutes = seconds % 3600000 / 60000
    print(f'{name} - {hours}h {minutes}m')


def _exit():
    input('\nPress any key to exit ...')
    exit()


if __name__ == '__main__':
    since = input('START DATE (for ex. `010322`): ')
    until = input('END DATE (for ex. `010422` or None): ')

    fsince, funtil = calculate_date(since, until)

    try:
        response = fetch_data(fsince, funtil)
    except Exception as ex:
        _log.error(ex)
        _exit()

    if not response.get('total_grand'):
        _log.info('There was a job free period.')
        _exit()

    received_data = response.get('data', [])
    if not received_data:
        _log.info('Empty received data.')
        _exit()

    data_dict_by_project = analyze_data(received_data)
    data_dict_by_task = analyze_data(received_data, parse_task=True)
    data_dict_by_task.pop('total_time')

    print('\n=======SUMMARY REPORT=======\n')
    for key, vals_list in data_dict_by_project.items():
        print_data(key, vals_list)

    print('\n-------by task-------\n')
    for key, vals_list in data_dict_by_task.items():
        print_data(key, vals_list)
