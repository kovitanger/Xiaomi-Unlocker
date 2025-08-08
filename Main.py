import subprocess
import sys
import os
import platform

# Массивы с серверами
ntp_servers = [
    "ntp0.ntp-servers.net", "ntp1.ntp-servers.net", "ntp2.ntp-servers.net",
    "ntp3.ntp-servers.net", "ntp4.ntp-servers.net", "ntp5.ntp-servers.net",
    "ntp6.ntp-servers.net"
]

MI_SERVERS = ['161.117.96.161', '20.157.18.26']

# Установка зависимостей
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

required_packages = ["requests", "ntplib", "pytz", "urllib3", "icmplib", "colorama", "linecache"]
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Устанавливаем пакет {package}...")
        install_package(package)

os.system('cls' if os.name == 'nt' else 'clear')

import hashlib
import linecache
import random
import time
from datetime import datetime, timezone, timedelta
import ntplib
import pytz
import urllib3
import json
import statistics
from icmplib import ping
from colorama import init, Fore, Style

#Задание цвета
init(autoreset=True)
col_g = Fore.GREEN #зеленый
col_gb = Style.BRIGHT + Fore.GREEN #ярко-зеленый
col_b = Fore.BLUE #синий
col_bb = Style.BRIGHT + Fore.BLUE #ярко-синий
col_y = Fore.YELLOW #желтый
col_yb = Style.BRIGHT + Fore.YELLOW #ярко-желтый
col_r = Fore.RED #красный
col_rb = Style.BRIGHT + Fore.RED #ярко-красный

#Версия и номер токена
token_number = int(input(col_g + f"[Номер строки токена]: " + Fore.RESET))
os.system('cls' if os.name == 'nt' else 'clear')
#token_number = 1
scriptversion = "ARU_FHL_v070425"

#Глобальные переменные
print(col_yb + f"{scriptversion}_токен_#{token_number}:")
print (col_y + f"Проверка статуса аккаунта" + Fore.RESET)
token = linecache.getline("token.txt" , token_number).strip ()
cookie_value = token
feedtime = float(linecache.getline("timeshift.txt" , token_number).strip ())
feed_time_shift = feedtime
feed_time_shift_1 = feed_time_shift / 1000

# Генерирует уникальный идентификатор устройства
def generate_device_id():
    random_data = f"{random.random()}-{time.time()}"
    device_id = hashlib.sha1(random_data.encode('utf-8')).hexdigest().upper()
    return device_id

# Получает текущее пекинское время NTP
def get_initial_beijing_time():
    client = ntplib.NTPClient()
    beijing_tz = pytz.timezone("Asia/Shanghai")
    for server in ntp_servers:
        try:
            print(col_y + f"\nОпределение текущего времени в Пекине" + Fore.RESET)
            response = client.request(server, version=3)
            ntp_time = datetime.fromtimestamp(response.tx_time, timezone.utc)
            beijing_time = ntp_time.astimezone(beijing_tz)
            print(col_g + f"[Пекинское время]: " + Fore.RESET +  f"{beijing_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
            return beijing_time
        except Exception as e:
            print(f"Ошибка подключения к {server}: {e}")
    print(f"Не удалось подключиться ни к одному из NTP серверов.")
    return None

# Синхронизирует пекинское время
def get_synchronized_beijing_time(start_beijing_time, start_timestamp):
    elapsed = time.time() - start_timestamp
    current_time = start_beijing_time + timedelta(seconds=elapsed)
    return current_time

# Ожидает наступления указанного времени с учётом пинга
def wait_until_target_time(start_beijing_time, start_timestamp):
    next_day = start_beijing_time + timedelta(days=1)
    print(col_y + f"\nПодача заявки на разблокировку загрузчика" + Fore.RESET)
    print (col_g + f"[Заданное смещение]: " + Fore.RESET + f"{feed_time_shift:.2f} мс.")
    target_time = next_day.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=feed_time_shift_1)
    print(col_g + f"[Ожидание до]: " + Fore.RESET + f"{target_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
    print(f"Не закрывайте окно...")
    
    while True:
        current_time = get_synchronized_beijing_time(start_beijing_time, start_timestamp)
        time_diff = target_time - current_time
        
        if time_diff.total_seconds() > 1:
            time.sleep(min(1.0, time_diff.total_seconds() - 1))
        elif current_time >= target_time:
            print(f"Время достигнуто: {current_time.strftime('%Y-%m-%d %H:%M:%S.%f')}. Начинаем отправку запросов...")
            break
        else:
            time.sleep(0.0001)

# Проверяет возможность разблокировки на аккаунте через API
def check_unlock_status(session, cookie_value, device_id):
    try:
        url = "https://sgp-api.buy.mi.com/bbs/api/global/user/bl-switch/state"
        headers = {
            "Cookie": f"new_bbs_serviceToken={cookie_value};versionCode=500411;versionName=5.4.11;deviceId={device_id};"
        }
        
        response = session.make_request('GET', url, headers=headers)
        if response is None:
            print(f"[Ошибка] Не удалось получить статус разблокировки.")
            return False

        response_data = json.loads(response.data.decode('utf-8'))
        response.release_conn()

        if response_data.get("code") == 100004:
            print(f"[Ошибка] Cookie устарел, требуется обновить!")
            input(f"Нажмите Enter, чтобы закрыть...")
            exit()

        data = response_data.get("data", {})
        is_pass = data.get("is_pass")
        button_state = data.get("button_state")
        deadline_format = data.get("deadline_format", "")

        if is_pass == 4:
            if button_state == 1:
                    print(col_g + f"[Статус аккаунта]: " + Fore.RESET + f"подача заявки возможна.")
                    return True

            elif button_state == 2:
                print(col_g + f"[Статус аккаунта]: " + Fore.RESET + f"блокировка на подачу до " f"{deadline_format} (Месяц/День).")
                status_2 = (input(f"Продолжить (" + col_b + f"Yes/No" +Fore.RESET + f")?: ") )
                if (status_2 == 'y' or status_2 == 'Y' or status_2 == 'yes' or status_2 == 'Yes' or status_2 == 'YES'):
                    return True
                else:
                    input(f"Нажмите Enter, чтобы закрыть...")
                    exit()
            elif button_state == 3:
                print(col_g + f"[Статус аккаунта]: " + Fore.RESET + f"аккаунт создан менее 30 дней назад.")
                status_3 = (input(f"Продолжить (" + col_b + f"Yes/No" +Fore.RESET + f")?: ") )
                if (status_3 == 'y' or status_3 == 'Y' or status_3 == 'yes' or status_3 == 'Yes' or status_3 == 'YES'):
                    return True
                else:
                    input(f"Нажмите Enter, чтобы закрыть...")
                    exit()
        elif is_pass == 1:
            print(col_g + f"[Статус аккаунта]: " + Fore.RESET + f"заявка одобрена, разблокировка возможна до " f"{deadline_format}.")
            input(f"Нажмите Enter, чтобы закрыть...")
            exit()
        else:
            print(col_g + f"[Статус аккаунта]: " + Fore.RESET + f"неизвестный статус.")
            input(f"Нажмите Enter, чтобы закрыть...")
            exit()
    except Exception as e:
        print(f"[Ошибка проверки статуса] {e}")
        return False

# wrapper для работы с HTTP-запросами
class HTTP11Session:
    def __init__(self):
        self.http = urllib3.PoolManager(
            maxsize=10,
            retries=True,
            timeout=urllib3.Timeout(connect=2.0, read=15.0),
            headers={}
        )

    def make_request(self, method, url, headers=None, body=None):
        try:
            request_headers = {}
            if headers:
                request_headers.update(headers)
                request_headers['Content-Type'] = 'application/json; charset=utf-8'
            
            if method == 'POST':
                if body is None:
                    body = '{"is_retry":true}'.encode('utf-8')
                request_headers['Content-Length'] = str(len(body))
                request_headers['Accept-Encoding'] = 'gzip, deflate, br'
                request_headers['User-Agent'] = 'okhttp/4.12.0'
                request_headers['Connection'] = 'keep-alive'
            
            response = self.http.request(
                method,
                url,
                headers=request_headers,
                body=body,
                preload_content=False
            )
            
            return response
        except Exception as e:
            print(f"[Ошибка сети] {e}")
            return None
 
def main():
        
    device_id = generate_device_id()
    session = HTTP11Session()

    if check_unlock_status(session, cookie_value, device_id):
        start_beijing_time = get_initial_beijing_time()
        if start_beijing_time is None:
            print(f"Не удалось установить начальное время. Нажмите Enter, чтобы закрыть...")
            input()
            exit()

        start_timestamp = time.time()
        
        wait_until_target_time(start_beijing_time, start_timestamp)

        url = "https://sgp-api.buy.mi.com/bbs/api/global/apply/bl-auth"
        headers = {
            "Cookie": f"new_bbs_serviceToken={cookie_value};versionCode=500411;versionName=5.4.11;deviceId={device_id};"
        }

        try:
            while True:
                request_time = get_synchronized_beijing_time(start_beijing_time, start_timestamp)
                print(col_g + f"[Запрос]: " + Fore.RESET + f"Отправка запроса в {request_time.strftime('%Y-%m-%d %H:%M:%S.%f')} (UTC+8)")
                
                response = session.make_request('POST', url, headers=headers)
                if response is None:
                    continue

                response_time = get_synchronized_beijing_time(start_beijing_time, start_timestamp)
                print(col_g + f"[Ответ]: " + Fore.RESET + f"Ответ получен в {response_time.strftime('%Y-%m-%d %H:%M:%S.%f')} (UTC+8)")

                try:
                    response_data = response.data
                    response.release_conn()
                    json_response = json.loads(response_data.decode('utf-8'))
                    code = json_response.get("code")
                    data = json_response.get("data", {})

                    if code == 0:
                        apply_result = data.get("apply_result")
                        if apply_result == 1:
                            print(col_g + f"[Статус]: " + Fore.RESET + f"Заявка одобрена, проверяем статус...")
                            check_unlock_status(session, cookie_value, device_id)
                        elif apply_result == 3:
                            deadline_format = data.get("deadline_format", "Не указано")
                            print(col_g + f"[Статус]: " + Fore.RESET + f"Заявка не подана, исчерпан лимит заявок, попробуйте снова в {deadline_format} (Месяц/День).")
                            input(f"Нажмите Enter, чтобы закрыть...")
                            exit()
                        elif apply_result == 4:
                            deadline_format = data.get("deadline_format", "Не указано")
                            print(col_g + f"[Статус]: " + Fore.RESET + f"Заявка не подана, выдана блокировка на подачу заявки до {deadline_format} (Месяц/День).")
                            input(f"Нажмите Enter, чтобы закрыть...")
                            exit()
                    elif code == 100001:
                        print(col_g + f"[Статус]: " + Fore.RESET + f"Заявка отклонена, ошибка запроса.")
                        print(col_g + f"[ПОЛНЫЙ ОТВЕТ]: " + Fore.RESET + f"{json_response}")
                    elif code == 100003:
                        print(col_g + f"[Статус]: " + Fore.RESET + f"Возможно заявка одобрена, проверяем статус...")
                        print(col_g + f"[Полный ответ]: " + Fore.RESET + f"{json_response}")
                        check_unlock_status(session, cookie_value, device_id)
                    elif code is not None:
                        print(col_g + f"[Статус]: " + Fore.RESET + f"Неизвестный статус заявки: {code}")
                        print(col_g + f"[Полный ответ]: " + Fore.RESET + f"{json_response}")
                    else:
                        print(col_g + f"[Ошибка]: " + Fore.RESET + f"Ответ не содержит необходимого кода.")
                        print(col_g + f"[Полный ответ]: " + Fore.RESET + f"{json_response}")

                except json.JSONDecodeError:
                    print(col_g + f"[Ошибка]: " + Fore.RESET + f"Не удалось декодировать JSON ответа.")
                    print(col_g + f"[Ответ сервера]: " + Fore.RESET + f"{response_data}")
                except Exception as e:
                    print(col_g + f"[Ошибка обработки ответа]: " + Fore.RESET + f"{e}")
                    continue

        except Exception as e:
            print(col_g + f"[Ошибка запроса]: " + Fore.RESET + f"{e}")
            input(f"Нажмите Enter, чтобы закрыть...")
            exit()

if __name__ == "__main__":
    main()