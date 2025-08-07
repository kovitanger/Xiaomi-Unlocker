import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QTextEdit, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class LoginThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto("https://account.xiaomi.com/pass/serviceLogin")

                # Ждем поля ввода логина
                try:
                    page.wait_for_selector('input[name="user"]', timeout=10000)
                    user_selector = 'input[name="user"]'
                except PlaywrightTimeoutError:
                    page.wait_for_selector('input[name="account"]', timeout=10000)
                    user_selector = 'input[name="account"]'

                page.fill(user_selector, self.username)
                page.fill('input[name="password"]', self.password)

                page.click('button[type="submit"]')

                # Ждем 7 секунд для входа
                page.wait_for_timeout(7000)

                cookies = page.context.cookies()
                browser.close()

                self.finished.emit(cookies)

        except Exception as e:
            self.error.emit(str(e))


class MiLoginGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mi Account Login (Playwright)")
        self.setFixedSize(400, 400)

        self.layout = QVBoxLayout()

        self.label_user = QLabel("Email или Mi ID:")
        self.input_user = QLineEdit()
        self.layout.addWidget(self.label_user)
        self.layout.addWidget(self.input_user)

        self.label_pass = QLabel("Пароль:")
        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.label_pass)
        self.layout.addWidget(self.input_pass)

        self.btn_login = QPushButton("Войти")
        self.btn_login.clicked.connect(self.start_login)
        self.layout.addWidget(self.btn_login)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.layout.addWidget(self.output)

        self.setLayout(self.layout)

        self.login_thread = None

    def start_login(self):
        user = self.input_user.text().strip()
        password = self.input_pass.text().strip()

        if not user or not password:
            QMessageBox.warning(self, "Ошибка", "Введите Email/Mi ID и пароль")
            return

        self.btn_login.setEnabled(False)
        self.output.clear()
        self.output.append("Запуск авторизации...")

        self.login_thread = LoginThread(user, password)
        self.login_thread.finished.connect(self.login_success)
        self.login_thread.error.connect(self.login_error)
        self.login_thread.start()

    def login_success(self, cookies):
        self.btn_login.setEnabled(True)
        self.output.append("Успешно вошли! Вот куки сессии:\n")
        self.output.append(json.dumps(cookies, indent=4, ensure_ascii=False))

        with open("mi_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4, ensure_ascii=False)

        QMessageBox.information(self, "Успех", "Авторизация успешна, cookies сохранены в mi_cookies.json")

    def login_error(self, error_msg):
        self.btn_login.setEnabled(True)
        self.output.append(f"Ошибка при входе:\n{error_msg}")
        QMessageBox.critical(self, "Ошибка", error_msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MiLoginGUI()
    window.show()
    sys.exit(app.exec_())
