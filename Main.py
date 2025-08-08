import sys
import subprocess
import os
import hashlib
import random
import time
import json
from datetime import datetime, timezone, timedelta

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit, QHBoxLayout, QGroupBox, QSpinBox, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import ntplib
import pytz
import urllib3


# Установка зависимостей
def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except:
        return False


required_packages = ["ntplib", "pytz", "urllib3"]
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        install_package(package)

# Массивы серверов
ntp_servers = [
    "ntp0.ntp-servers.net", "ntp1.ntp-servers.net", "ntp2.ntp-servers.net",
    "ntp3.ntp-servers.net", "ntp4.ntp-servers.net", "ntp5.ntp-servers.net",
    "ntp6.ntp-servers.net"
]


# Wrapper для работы с HTTP-запросами
class HTTP11Session:
    def __init__(self):
        self.http = urllib3.PoolManager(
            maxsize=10, retries=True,
            timeout=urllib3.Timeout(connect=2.0, read=15.0)
        )

    def make_request(self, method, url, headers=None, body=None):
        try:
            request_headers = headers or {}
            request_headers['Content-Type'] = 'application/json; charset=utf-8'

            if method == 'POST':
                body = body or '{"is_retry":true}'.encode('utf-8')
                request_headers.update({
                    'Content-Length': str(len(body)),
                    'Accept-Encoding': 'gzip, deflate, br',
                    'User-Agent': 'okhttp/4.12.0',
                    'Connection': 'keep-alive'
                })

            response = self.http.request(
                method, url, headers=request_headers, body=body,
                preload_content=False
            )
            return response
        except Exception as e:
            print(f"[Ошибка сети] {e}")
            return None


# Поток для основной логики разблокировки
class UnlockThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, token_number, feed_time_shift):
        super().__init__()
        self.token_number = token_number
        self.feed_time_shift = feed_time_shift
        self.feed_time_shift_1 = feed_time_shift / 1000

    def generate_device_id(self):
        random_data = f"{random.random()}-{time.time()}"
        return hashlib.sha1(random_data.encode('utf-8')).hexdigest().upper()

    def get_initial_beijing_time(self):
        client = ntplib.NTPClient()
        beijing_tz = pytz.timezone("Asia/Shanghai")
        for server in ntp_servers:
            try:
                self.log_signal.emit("\nОпределение текущего времени в Пекине")
                response = client.request(server, version=3)
                ntp_time = datetime.fromtimestamp(response.tx_time, timezone.utc)
                beijing_time = ntp_time.astimezone(beijing_tz)
                self.log_signal.emit(f"[Пекинское время]: {beijing_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
                return beijing_time
            except Exception as e:
                self.log_signal.emit(f"Ошибка подключения к {server}: {e}")
        self.log_signal.emit("Не удалось подключиться ни к одному из NTP серверов.")
        return None

    def get_synchronized_beijing_time(self, start_beijing_time, start_timestamp):
        elapsed = time.time() - start_timestamp
        return start_beijing_time + timedelta(seconds=elapsed)

    def check_unlock_status(self, session, cookie_value, device_id):
        try:
            url = "https://sgp-api.buy.mi.com/bbs/api/global/user/bl-switch/state"
            headers = {
                "Cookie": f"new_bbs_serviceToken={cookie_value};versionCode=500411;versionName=5.4.11;deviceId={device_id};"
            }

            response = session.make_request('GET', url, headers=headers)
            if response is None:
                self.log_signal.emit("[Ошибка] Не удалось получить статус разблокировки.")
                return False

            response_data = json.loads(response.data.decode('utf-8'))
            response.release_conn()

            if response_data.get("code") == 100004:
                self.log_signal.emit("[Ошибка] Cookie устарел, требуется обновить!")
                return False

            data = response_data.get("data", {})
            is_pass = data.get("is_pass")
            button_state = data.get("button_state")
            deadline_format = data.get("deadline_format", "")

            if is_pass == 4:
                if button_state == 1:
                    self.log_signal.emit("[Статус аккаунта]: подача заявки возможна.")
                    return True
                elif button_state in [2, 3]:
                    status_msg = {
                        2: f"блокировка на подачу до {deadline_format} (Месяц/День)",
                        3: "аккаунт создан менее 30 дней назад"
                    }
                    self.log_signal.emit(f"[Статус аккаунта]: {status_msg[button_state]}.")
                    return True
            elif is_pass == 1:
                self.log_signal.emit(
                    f"[Статус аккаунта]: заявка одобрена, разблокировка возможна до {deadline_format}.")
                return False
            else:
                self.log_signal.emit("[Статус аккаунта]: неизвестный статус.")
                return False
        except Exception as e:
            self.log_signal.emit(f"[Ошибка проверки статуса] {e}")
            return False

    def run(self):
        # Получаем токен из файла
        try:
            with open("token.txt", "r") as f:
                lines = f.readlines()
                if len(lines) >= self.token_number:
                    token = lines[self.token_number - 1].strip()
                else:
                    self.log_signal.emit("Ошибка: недостаточно строк в файле token.txt")
                    self.finished_signal.emit()
                    return
        except FileNotFoundError:
            self.log_signal.emit("Ошибка: файл token.txt не найден")
            self.finished_signal.emit()
            return
        except Exception:
            self.log_signal.emit("Ошибка: не удалось прочитать файл token.txt")
            self.finished_signal.emit()
            return

        if not token:
            self.log_signal.emit("Ошибка: не удалось получить токен")
            self.finished_signal.emit()
            return

        device_id = self.generate_device_id()
        session = HTTP11Session()

        if not self.check_unlock_status(session, token, device_id):
            self.finished_signal.emit()
            return

        start_beijing_time = self.get_initial_beijing_time()
        if start_beijing_time is None:
            self.log_signal.emit("Не удалось установить начальное время.")
            self.finished_signal.emit()
            return

        start_timestamp = time.time()

        # Ожидание времени
        next_day = start_beijing_time + timedelta(days=1)
        self.log_signal.emit("\nПодача заявки на разблокировку загрузчика")
        self.log_signal.emit(f"[Заданное смещение]: {self.feed_time_shift:.2f} мс.")
        target_time = next_day.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            seconds=self.feed_time_shift_1)
        self.log_signal.emit(f"[Ожидание до]: {target_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
        self.log_signal.emit("Не закрывайте окно...")

        while True:
            current_time = self.get_synchronized_beijing_time(start_beijing_time, start_timestamp)
            time_diff = target_time - current_time

            if time_diff.total_seconds() > 1:
                time.sleep(min(1.0, time_diff.total_seconds() - 1))
            elif current_time >= target_time:
                self.log_signal.emit(
                    f"Время достигнуто: {current_time.strftime('%Y-%m-%d %H:%M:%S.%f')}. Начинаем отправку запросов...")
                break
            else:
                time.sleep(0.0001)

        # Отправка запросов
        url = "https://sgp-api.buy.mi.com/bbs/api/global/apply/bl-auth"
        headers = {
            "Cookie": f"new_bbs_serviceToken={token};versionCode=500411;versionName=5.4.11;deviceId={device_id};"
        }

        try:
            while True:
                request_time = self.get_synchronized_beijing_time(start_beijing_time, start_timestamp)
                self.log_signal.emit(
                    f"[Запрос]: Отправка запроса в {request_time.strftime('%Y-%m-%d %H:%M:%S.%f')} (UTC+8)")

                response = session.make_request('POST', url, headers=headers)
                if response is None:
                    continue

                response_time = self.get_synchronized_beijing_time(start_beijing_time, start_timestamp)
                self.log_signal.emit(
                    f"[Ответ]: Ответ получен в {response_time.strftime('%Y-%m-%d %H:%M:%S.%f')} (UTC+8)")

                try:
                    response_data = response.data
                    response.release_conn()
                    json_response = json.loads(response_data.decode('utf-8'))
                    code = json_response.get("code")
                    data = json_response.get("data", {})

                    if code == 0:
                        apply_result = data.get("apply_result")
                        if apply_result == 1:
                            self.log_signal.emit("[Статус]: Заявка одобрена, проверяем статус...")
                            self.check_unlock_status(session, token, device_id)
                            break
                        elif apply_result in [3, 4]:
                            deadline_format = data.get("deadline_format", "Не указано")
                            status_msg = {
                                3: f"Заявка не подана, исчерпан лимит заявок, попробуйте снова в {deadline_format} (Месяц/День)",
                                4: f"Заявка не подана, выдана блокировка на подачу заявки до {deadline_format} (Месяц/День)"
                            }
                            self.log_signal.emit(f"[Статус]: {status_msg[apply_result]}.")
                            break
                    elif code == 100001:
                        self.log_signal.emit("[Статус]: Заявка отклонена, ошибка запроса.")
                        self.log_signal.emit(f"[ПОЛНЫЙ ОТВЕТ]: {json_response}")
                    elif code == 100003:
                        self.log_signal.emit("[Статус]: Возможно заявка одобрена, проверяем статус...")
                        self.log_signal.emit(f"[Полный ответ]: {json_response}")
                        self.check_unlock_status(session, token, device_id)
                        break
                    elif code is not None:
                        self.log_signal.emit(f"[Статус]: Неизвестный статус заявки: {code}")
                        self.log_signal.emit(f"[Полный ответ]: {json_response}")
                    else:
                        self.log_signal.emit("[Ошибка]: Ответ не содержит необходимого кода.")
                        self.log_signal.emit(f"[Полный ответ]: {json_response}")

                except json.JSONDecodeError:
                    self.log_signal.emit("[Ошибка]: Не удалось декодировать JSON ответа.")
                    self.log_signal.emit(f"[Ответ сервера]: {response_data}")
                except Exception as e:
                    self.log_signal.emit(f"[Ошибка обработки ответа]: {e}")
                    continue

        except Exception as e:
            self.log_signal.emit(f"[Ошибка запроса]: {e}")

        self.finished_signal.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xiaomi Unlocker")
        self.setFixedSize(800, 600)
        self.unlock_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Заголовок
        title = QLabel("Xiaomi Unlocker - Автоматическая разблокировка")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Настройки
        settings_group = QGroupBox("Настройки")
        settings_layout = QHBoxLayout()

        # Номер токена
        token_layout = QVBoxLayout()
        token_layout.addWidget(QLabel("Номер строки токена:"))
        self.token_spinbox = QSpinBox()
        self.token_spinbox.setRange(1, 1000)
        self.token_spinbox.setValue(1)
        token_layout.addWidget(self.token_spinbox)
        settings_layout.addLayout(token_layout)

        # Смещение времени
        time_layout = QVBoxLayout()
        time_layout.addWidget(QLabel("Смещение времени (мс):"))
        self.time_shift_spinbox = QSpinBox()
        self.time_shift_spinbox.setRange(0, 10000)
        self.time_shift_spinbox.setValue(500)
        time_layout.addWidget(self.time_shift_spinbox)
        settings_layout.addLayout(time_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        self.start_unlock_button = QPushButton("Начать разблокировку")
        self.start_unlock_button.setStyleSheet("""
            background-color: #FF9800; 
            color: white; 
            padding: 15px; 
            font-weight: bold; 
            font-size: 14px;
        """)
        self.start_unlock_button.clicked.connect(self.start_unlock_process)
        buttons_layout.addWidget(self.start_unlock_button)

        self.stop_button = QPushButton("Остановить")
        self.stop_button.setStyleSheet("""
            background-color: #f44336; 
            color: white; 
            padding: 15px; 
            font-size: 14px;
        """)
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_button)
        layout.addLayout(buttons_layout)

        # Логи
        results_group = QGroupBox("Результаты и логи")
        results_layout = QVBoxLayout()

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)

        self.clear_button = QPushButton("Очистить логи")
        self.clear_button.setStyleSheet("""
            background-color: #9E9E9E; 
            color: white; 
            padding: 8px;
        """)
        self.clear_button.clicked.connect(self.clear_results)
        results_layout.addWidget(self.clear_button)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        self.setLayout(layout)

    def start_unlock_process(self):
        if self.unlock_thread and self.unlock_thread.isRunning():
            QMessageBox.warning(self, "Предупреждение", "Процесс уже запущен!")
            return

        # Проверяем наличие файла token.txt
        if not os.path.exists("token.txt"):
            QMessageBox.warning(self, "Ошибка", "Файл token.txt не найден!")
            return

        # Блокируем кнопки
        self.clear_button.setEnabled(False)
        self.start_unlock_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Запускаем процесс
        token_number = self.token_spinbox.value()
        feed_time_shift = self.time_shift_spinbox.value()

        self.unlock_thread = UnlockThread(token_number, feed_time_shift)
        self.unlock_thread.log_signal.connect(self.append_log)
        self.unlock_thread.finished_signal.connect(self.unlock_finished)
        self.unlock_thread.start()

    def stop_process(self):
        if self.unlock_thread and self.unlock_thread.isRunning():
            self.unlock_thread.terminate()
            self.unlock_thread.wait()

        # Разблокируем кнопки
        self.stop_button.setEnabled(False)
        self.start_unlock_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.append_log("Процесс остановлен пользователем.")

    def unlock_finished(self):
        self.start_unlock_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.clear_button.setEnabled(True)
        self.append_log("Процесс разблокировки завершен.")

    def append_log(self, text):
        self.results_text.append(text)
        self.results_text.verticalScrollBar().setValue(
            self.results_text.verticalScrollBar().maximum()
        )

    def clear_results(self):
        self.results_text.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())