# Python 3.8
# -*- coding: utf_8 -*-

import sys
import re
from selenium import webdriver
import time
from datetime import datetime
from PyQt5 import QtWidgets, QtGui, QtCore, Qt
from PyQt5.QtCore import QThread
from pr_design import Ui_MainWindow


class PRBot(QThread):
    progressChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent, child_list, parent_pr_topic, pr_code):
        super().__init__()
        self.parent = parent
        self.children = child_list
        self.parent_pr_topic = parent_pr_topic
        self.pr_code = pr_code
        self.driver = self.init_driver()
        self.parent_window = self.driver.window_handles[0]
        # параметры чайлдов
        self.first_post = None
        self.last_post = None
        self.form_answer = None
        # логи
        self.logs = {
            'Не удалось войти на форум': [],
            'Не удалось найти рекламную тему': [],
            'Не удалось проверить рекламную тему на соответствие': [],
            'Не удалось отправить рекламное сообщение': [],
        }

    @staticmethod
    def init_driver():
        """
        Иницилизируем вебдрайвер
        :return: webdriver.Chrome with options
        """
        options = webdriver.ChromeOptions()
        options.add_argument('--blink-settings=imagesEnabled=false')
        executable_path = './driver/chromedriver.exe'
        return webdriver.Chrome(options=options, executable_path=executable_path)

    def log_to_forum(self):
        """
        Логинимся на форум
        :return: None
        """
        try:
            pr_enter = self.driver.find_elements_by_tag_name('a')
            for elem in pr_enter:
                if elem.get_attribute('onclick') in ["PR['in_1']()", "PiarIn()"]:
                    elem.click()
                    time.sleep(3)
                    return True
        except:
            self.logs['Не удалось войти на форум'].append(self.driver.current_url)

    def find_child_pr_topic(self):
        """
        Находим рекламную тему на форуме
        :return: bool
        """
        try:
            pr_account = self.driver.find_element_by_css_selector('#navprofile > a > span')
            if pr_account.get_attribute('innerText').lower() == 'профиль':
                pr_account.click()
                messages = self.driver.find_element_by_css_selector('#user-posts')
                messages.click()
                self.driver.find_element_by_link_text('Перейти к теме').click()
                return True
        except:
            self.logs['Не удалось найти рекламную тему'].append(self.driver.current_url)

    def get_pr_params(self):
        """
        определяем параметры для проверки на соответствие рекламной теме
        :return: None
        """
        try:
            self.first_post = self.driver.find_element_by_class_name('firstpost')
            self.last_post = self.driver.find_element_by_class_name('endpost')
            self.form_answer = self.driver.find_element_by_id('main-reply')
            return True
        except:
            self.logs['Не удалось проверить рекламную тему на соответствие'].append(self.driver.current_url)

    def check_child_pr_topic(self):
        """
        проверяем, что зашли именно в рекламную тему
        :return: bool
        """
        try:
            if self.get_pr_params():
                xpath_image = "//img[contains(@class, 'postimg')]"
                xpath_code = "//div[contains(@class, 'code-box')]"
                if self.last_post.find_element_by_xpath(xpath_image) and self.first_post.find_element_by_xpath(
                        xpath_code) and self.form_answer:
                    return True
        except:
            self.logs['Не удалось проверить рекламную тему на соответствие'].append(self.driver.current_url)

    def get_child_pr_message(self):
        """
        получаем код рекламного сообщения
        :return: str
        """
        return self.first_post.find_element_by_xpath("//pre").get_attribute("innerHTML")

    def post_pr_message(self, pr_code: str, current_url: str):
        """
        отправляем ссобщение на форум
        :param pr_code: шаблон рекламного сообщения
        :param current_url: ссылка на последнее сообщение
        :return: ссылка на последнее сообщение
        """
        try:
            form_answer = self.driver.find_element_by_id('main-reply')
            pr_code = re.sub(r'<span>', '', pr_code).replace('</span>', '')
            form_answer.send_keys(f'{pr_code} {current_url}')
            self.driver.find_element_by_css_selector('#post > p > input.button.submit').click()
            return self.driver.current_url
        except:
            self.logs['Не удалось отправить рекламное сообщение'].append(self.driver.current_url)

    def write_logs(self):
        today = datetime.now()
        with open(f'Отчет о работе пиар-бота. {today}', 'w+', encoding='utf-8') as f_obj:
            for key, value in self.logs.items():
                f_obj.write(f'{key}: {value}\n')

    def run(self):
        self.driver.get(self.parent)
        if not self.log_to_forum():
            return None
        self.driver.get(self.parent_pr_topic)
        self.driver.execute_script("window.open()")
        window_after = self.driver.window_handles[1]
        self.driver.switch_to.window(window_after)
        progress = 0

        for child in self.children:
            progress += 100 / len(self.children)
            self.progressChanged.emit(progress)
            self.driver.get(child)
            if not self.log_to_forum():
                continue
            if not self.find_child_pr_topic():
                continue
            if not self.check_child_pr_topic():
                continue
            pr_code = self.get_child_pr_message()
            if not pr_code:
                continue
            self.driver.switch_to.window(self.parent_window)
            current_url = self.post_pr_message(pr_code=pr_code, current_url='')
            if not current_url:
                continue
            self.driver.switch_to.window(window_after)
            self.post_pr_message(pr_code=self.pr_code, current_url=current_url)
            self.write_logs()


class BotWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(BotWindow, self).__init__(*args, **kwargs)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.child_list = []
        self.forum_main_ui = ''
        self.forum_pr_topic = ''
        self.pr_code = ''

        self.thread = PRBot(parent=None, child_list=None, parent_pr_topic=None, pr_code=None)
        self.ui.pushButton.clicked.connect(self.set_variables_to_bot)
        self.ui.pushButton_2.clicked.connect(self.run_bot)

    def set_variables_to_bot(self):
        """
        Устанавливаем переменные для работы бота
        :return: None
        """
        self.child_list = self.ui.textEdit_2.toPlainText().split(', ')
        self.forum_main_ui = self.ui.lineEdit.text()
        self.forum_pr_topic = self.ui.lineEdit_2.text()
        self.pr_code = self.ui.textEdit.toPlainText()
        self.ui.pushButton.setEnabled(False)
        self.ui.textEdit_2.setEnabled(False)
        self.ui.lineEdit.setEnabled(False)
        self.ui.lineEdit_2.setEnabled(False)
        self.ui.textEdit.setEnabled(False)

        #передаем переменные в поток
        self.thread.child_list = self.child_list
        self.thread.parent = self.forum_main_ui
        self.thread.parent_pr_topic = self.forum_pr_topic
        self.thread.pr_code = self.pr_code
        self.bot = PRBot(parent=self.forum_main_ui, child_list=self.child_list, parent_pr_topic=self.forum_pr_topic,
                         pr_code=self.pr_code)

    def on_about_check_url(self, data):
        self.ui.progressBar.setValue(data)

    def run_bot(self):
        self.bot.start()
        self.thread.progressChanged.connect(self.on_about_check_url)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    ico = QtGui.QIcon('./icons/icon.ico')
    app.setWindowIcon(ico)
    # стиль отображения интерфейса
    app.setStyle("Fusion")
    app.processEvents()
    application = BotWindow()

    # указываем заголовок окна
    application.setWindowTitle("PR-Bot")
    # задаем минимальный размер окна, до которого его можно ужимать
    application.setMaximumSize(800, 600)
    application.show()
    sys.exit(app.exec())
