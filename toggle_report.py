# python3

from collections import defaultdict
from datetime import datetime, timedelta
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
TOKEN = 'xxxxxxxxxxxxxx'

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
DATE_FMT = '%d%m%y'


def format_date(rdate):
    year = rdate[-2:]
    month = rdate[2:4]
    day = rdate[:2]
    return f'20{year}-{month}-{day}'


def calculate_date(since, until):

    if not since:
        first_month_day = datetime.today() - relativedelta(day=1)
        since = first_month_day.date().strftime(DATE_FMT)

    if not until:
        last_month_day = datetime.strptime(since, DATE_FMT) + relativedelta(day=31)
        until = last_month_day.date().strftime(DATE_FMT)

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
    entry_list = re.findall(r'\[(.*?)\]', title.get('time_entry', ''))
    task_code = (entry_list and entry_list[0] or str()).upper()

    if parse_task:
        return task_code

    project_code = task_code.split('-')
    project_name = project_code and project_code[0] or str()
    return project_name


def parse_item(item, parse_task=False):
    item_name = parse_item_name(item['title'], parse_task=parse_task)
    return item_name, item['time'], item['local_start']


def analyze_data(data_list, parse_task=False):
    local_starts = list()
    data_dict = defaultdict(list)

    for data in data_list:
        total_time = data.get('time', 0)
        data_dict['total_time'].append(total_time)

        for item in data.get('items', []):
            item_key, item_value, local_start = parse_item(item, parse_task=parse_task)
            data_dict[item_key].append(item_value)
            local_starts.append(local_start)

    return data_dict, local_starts


def print_data(name, vals_list):
    seconds = sum(vals_list)
    hours = seconds // 3600000
    minutes = seconds % 3600000 / 60000
    print(f'{name} - {hours}h {minutes}m')


def get_rest_of_days(starts_str):
    starts_dt = [datetime.fromisoformat(x) for x in starts_str]
    max_date = max(starts_dt)
    last_month_day = max_date + relativedelta(day=31)
    daygenerator = (max_date + timedelta(x + 1) for x in range((last_month_day - max_date).days))
    rest_days = sum(1 for day in daygenerator if day.weekday() < 5)
    return rest_days


def _exit():
    input('\nPress any key to exit ...')
    exit()


if __name__ == '__main__':
    since = input('START DATE (for ex. `010322` or None): ')
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

    data_dict_by_project, local_starts = analyze_data(received_data)
    data_dict_by_task, _ = analyze_data(received_data, parse_task=True)
    data_dict_by_task.pop('total_time')

    if not until:
        day_rest = get_rest_of_days(local_starts)

    print('\n=======SUMMARY REPORT=======\n')
    print(f'{fsince} : {funtil}\n')

    for key, vals_list in data_dict_by_project.items():
        print_data(key, vals_list)

    print('\n-------by task-------\n')

    for key, vals_list in data_dict_by_task.items():
        print_data(key, vals_list)

    if not until:
        print('\n-------TODO-------\n')
        per_day = ((140 * 3600 * 1000) - sum(data_dict_by_project['total_time'])) / day_rest
        hours = per_day // 3600000
        minutes = per_day % 3600000 / 60000
        print(f'{day_rest} days, {hours}h {minutes}m / day\n')
