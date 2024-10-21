from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import (
    QMainWindow, QTreeWidget, QTreeWidgetItem, QTextBrowser, QVBoxLayout, 
    QHBoxLayout, QSplitter, QWidget, QAction, QInputDialog, QMessageBox, 
    QToolBar, QLabel, QProgressBar, QLineEdit, QFileDialog, QListWidget, 
    QListWidgetItem, QGroupBox, QPushButton, QDialog, QMenu, QTextEdit, QFontDialog, QColorDialog
)
from PyQt5.QtCore import Qt, QRegularExpression, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap, QTextCursor, QTextCharFormat
from PyQt5.QtPrintSupport import QPrinter
from database import Database
from utils import get_mime_type, read_file, write_file
import json
import os
import sys
import shutil
import mimetypes
import logging
import subprocess
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices


# Настройка логирования
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

class SearchThread(QThread):
    progress_updated = pyqtSignal(int)
    search_completed = pyqtSignal(list)

    def __init__(self, db, search_text):
        super().__init__()
        self.db = db
        self.search_text = search_text

    def run(self):
        results = []
        total = len(self.db.data["content"])
        for i, (key, content) in enumerate(self.db.data["content"].items()):
            # Преобразуем HTML в простой текст
            doc = QTextBrowser()
            doc.setHtml(content)
            plain_text = doc.toPlainText()
            if self.search_text.lower() in plain_text.lower():
                # Находим индекс вхождения поискового запроса
                index = plain_text.lower().find(self.search_text.lower())
                # Извлекаем контекст вокруг найденного слова
                start = max(0, index - 50)
                end = min(len(plain_text), index + 50)
                context = plain_text[start:end]
                results.append((key, context))
            progress = int((i + 1) / total * 100) if total > 0 else 100
            self.progress_updated.emit(progress)
        self.search_completed.emit(results)

class SearchResultsDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Результаты поиска")
        size = self.parent().config.get("search_window_size", [600, 400])
        self.resize(*size)
        self.results = results
        self.parent = parent  # Сохраняем ссылку на родителя
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)  # Добавляем список в макет один раз
        for key, context in results:
            item = QListWidgetItem(f"{key}: {context}")
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)  # Добавляем элемент в список
        self.list_widget.itemDoubleClicked.connect(self.go_to_result)
        self.setLayout(layout)

    def closeEvent(self, event):
        if self.parent:
            self.parent.config["search_window_size"] = [self.width(), self.height()]
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.parent.config, f, ensure_ascii=False, indent=4)
        event.accept()

    def go_to_result(self, item):
        key = item.data(Qt.UserRole)
        self.parent.navigate_to_key(key)  # Используем self.parent
        self.close()

class KnowledgeBaseApp(QMainWindow):
    def __init__(self, mode='user'):
        super(KnowledgeBaseApp, self).__init__()
        self.config = self.load_config()
        self.db = Database(self.config["db_file"])
        self.mode = mode
        self.init_ui()

    def open_link(self, url):
        QDesktopServices.openUrl(url)

    def load_config(self):
        default_config = {
            "window_size": [1024, 768],
            "splitter_sizes": [200, 600, 200],
            "db_file": "data.db",
            "files_folder": "files",
            "icons_folder": "icons",
            "log_file": "app.log",
            "search_window_size": [600, 400]
        }
        config_file = 'config.json'
        if not os.path.exists(config_file):
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=4)
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        # Проверка наличия всех ключей, добавление отсутствующих
        updated = False
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
                updated = True
        if updated:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        return config

    def closeEvent(self, event):
        # Сохранение состояния окна
        self.config["splitter_sizes"] = self.splitter.sizes()
        self.config["window_geometry"] = self.saveGeometry().data().hex()
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)
        event.accept()

    def init_ui(self):
        # Основная настройка интерфейса
        self.setWindowTitle("Приложение базы знаний")
        self.setGeometry(100, 100, *self.config["window_size"])
        self.statusBar().showMessage("Готово")
        self.setup_menus()
        self.setup_layout()
        self.load_sections()
        if self.mode == 'user':
            self.disable_editing()
        self.load_main_page()

    def setup_menus(self):
        # Создание меню
        menubar = self.menuBar()
        file_menu = menubar.addMenu('Файл')

        home_action = QAction('Главная страница', self)
        home_action.setShortcut('Ctrl+H')
        home_action.triggered.connect(self.load_main_page)
        file_menu.addAction(home_action)

        save_pdf_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'pdf.png')), 'Сохранить в PDF', self)
        save_pdf_action.triggered.connect(self.save_as_pdf)
        file_menu.addAction(save_pdf_action)

        login_admin_action = QAction('Войти как администратор', self)
        login_admin_action.triggered.connect(self.login_as_admin)
        file_menu.addAction(login_admin_action)

        logout_admin_action = QAction('Выйти из режима администратора', self)
        logout_admin_action.triggered.connect(self.logout_admin)
        logout_admin_action.setVisible(False)
        file_menu.addAction(logout_admin_action)

        self.login_admin_action = login_admin_action
        self.logout_admin_action = logout_admin_action

    def setup_layout(self):
        # Основной макет и панели
        main_layout = QHBoxLayout()
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Разделы и Категории")
        self.tree.itemClicked.connect(self.on_item_clicked)

        central_widget = QWidget()
        central_layout = QVBoxLayout()
        central_widget.setLayout(central_layout)

        self.text_editor = QTextBrowser()
        self.text_editor.setReadOnly(False)
        self.text_editor.setOpenExternalLinks(False)
        self.text_editor.setOpenLinks(False)
        self.text_editor.anchorClicked.connect(self.open_link)
        self.text_editor.textChanged.connect(self.on_text_changed)

        self.text_toolbar = QToolBar("Форматирование текста")
        self.add_text_formatting_actions(self.text_toolbar)

        central_layout.addWidget(self.text_toolbar)
        central_layout.addWidget(self.text_editor)

        self.init_files_panel()

        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(central_widget)
        self.splitter.addWidget(self.files_widget)
        self.splitter.setSizes(self.config["splitter_sizes"])

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Поиск...")
        self.search_bar.returnPressed.connect(self.perform_search)
        search_toolbar = self.addToolBar("Поиск")
        search_toolbar.addWidget(QLabel("Поиск: "))
        search_toolbar.addWidget(self.search_bar)

        self.progress_bar = QProgressBar()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()

        if "window_geometry" in self.config:
            self.restoreGeometry(bytes.fromhex(self.config["window_geometry"]))

    def save_as_pdf(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить как PDF", "", "PDF Files (*.pdf)")
        if file_path:
            printer.setOutputFileName(file_path)
            self.text_editor.document().print_(printer)
            QMessageBox.information(self, "Сохранение в PDF", "Файл успешно сохранён.")

    def load_main_page(self):
        self.tree.clearSelection()
        key = "Главная"
        content = self.db.load_content(key)
        self.text_editor.setText(content)
        self.load_files(key)
        self.text_editor.setReadOnly(self.mode != 'admin')

    def load_sections(self):
        self.tree.clear()
        sections = self.db.get_sections()
        for section_name, categories in sections.items():
            section_item = QTreeWidgetItem([section_name])
            self.tree.addTopLevelItem(section_item)
            for category_name in categories:
                category_item = QTreeWidgetItem([category_name])
                section_item.addChild(category_item)
        self.tree.expandAll()

    def on_item_clicked(self, item, column):
        key = self.get_item_key(item)
        content = self.db.load_content(key)
        self.text_editor.setText(content)
        self.load_files(key)
        self.text_editor.setReadOnly(self.mode != 'admin')

    def login_as_admin(self):
        text, ok = QInputDialog.getText(self, "Пароль администратора", "Введите пароль:", QLineEdit.Password)
        if ok and text == "123":
            self.mode = 'admin'
            self.enable_editing()
            QMessageBox.information(self, "Режим администратора", "Вы вошли в режим администратора.")
            self.login_admin_action.setVisible(False)
            self.logout_admin_action.setVisible(True)
        elif ok:
            QMessageBox.warning(self, "Ошибка", "Неверный пароль.")

    def logout_admin(self):
        reply = QMessageBox.question(
            self, 'Выход из режима администратора',
            "Вы уверены, что хотите выйти из режима администратора?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.mode = 'user'
            self.disable_editing()
            QMessageBox.information(self, "Режим пользователя", "Вы вышли из режима администратора.")
            self.login_admin_action.setVisible(True)
            self.logout_admin_action.setVisible(False)

    def enable_editing(self):
        # Активируем элементы редактирования
        self.text_editor.setReadOnly(False)
        self.text_toolbar.setDisabled(False)
        self.load_file_button.setDisabled(False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)

    def disable_editing(self):
        self.text_editor.setReadOnly(True)
        self.text_toolbar.setDisabled(True)
        self.load_file_button.setDisabled(True)
        self.tree.setContextMenuPolicy(Qt.NoContextMenu)

    def add_text_formatting_actions(self, toolbar):
        # Добавляем кнопки форматирования текста
        insert_table_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'table.png')), "Вставить таблицу из Excel", self)
        insert_table_action.triggered.connect(self.insert_table_from_excel)
        toolbar.addAction(insert_table_action)

        toolbar.addSeparator()
        link_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'link.png')), "Вставить ссылку", self)
        link_action.triggered.connect(self.insert_link)
        toolbar.addAction(link_action)

        align_left_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'align_left.png')), "Выровнять по левому краю", self)
        align_left_action.triggered.connect(lambda: self.text_editor.setAlignment(Qt.AlignLeft))
        toolbar.addAction(align_left_action)

        align_center_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'align_center.png')), "Выровнять по центру", self)
        align_center_action.triggered.connect(lambda: self.text_editor.setAlignment(Qt.AlignCenter))
        toolbar.addAction(align_center_action)

        font_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'font.png')), "Шрифт", self)
        font_action.triggered.connect(self.select_font)
        toolbar.addAction(font_action)

        color_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'color.png')), "Цвет", self)
        color_action.triggered.connect(self.select_color)
        toolbar.addAction(color_action)

        bold_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'bold.png')), "Полужирный", self)
        bold_action.setCheckable(True)
        bold_action.toggled.connect(lambda: self.text_editor.setFontWeight(QFont.Bold if bold_action.isChecked() else QFont.Normal))
        toolbar.addAction(bold_action)

        italic_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'italic.png')), "Курсив", self)
        italic_action.setCheckable(True)
        italic_action.toggled.connect(self.text_editor.setFontItalic)
        toolbar.addAction(italic_action)

        underline_action = QAction(QIcon(os.path.join(self.config["icons_folder"], 'underline.png')), "Подчёркивание", self)
        underline_action.setCheckable(True)
        underline_action.toggled.connect(self.text_editor.setFontUnderline)
        toolbar.addAction(underline_action)

    def insert_link(self):
        cursor = self.text_editor.textCursor()
        url, ok = QInputDialog.getText(self, "Вставить ссылку", "Введите URL:")
        if ok and url:
            text, ok = QInputDialog.getText(self, "Вставить ссылку", "Текст ссылки:")
            if ok and text:
                html = f'<a href="{url}">{text}</a>'
                cursor.insertHtml(html)

    def insert_table_from_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл Excel", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            try:
                import pandas as pd
                df = pd.read_excel(file_path)
                html = df.to_html(index=False)
                self.text_editor.insertHtml(html)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось вставить таблицу: {e}")

    def init_files_panel(self):
        # Создаем панель для управления файлами
        self.files_widget = QWidget()
        files_layout = QVBoxLayout()
        self.files_widget.setLayout(files_layout)

        self.load_file_button = QPushButton(QIcon(os.path.join(self.config["icons_folder"], 'upload.png')), "Загрузить файл")
        self.load_file_button.clicked.connect(self.load_file)
        files_layout.addWidget(self.load_file_button)

        self.files_splitter = QSplitter(Qt.Vertical)
        files_layout.addWidget(self.files_splitter)

        image_group = QGroupBox("Изображения")
        image_layout = QVBoxLayout()
        image_group.setLayout(image_layout)

        self.image_list = QListWidget()
        self.image_list.setViewMode(QListWidget.IconMode)
        self.image_list.setIconSize(QSize(100, 100))
        self.image_list.setResizeMode(QListWidget.Adjust)
        self.image_list.itemDoubleClicked.connect(self.open_file)
        image_layout.addWidget(self.image_list)

        document_group = QGroupBox("Документы")
        document_layout = QVBoxLayout()
        document_group.setLayout(document_layout)

        self.other_file_list = QListWidget()
        self.other_file_list.setViewMode(QListWidget.ListMode)
        self.other_file_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.other_file_list.itemDoubleClicked.connect(self.open_file)
        document_layout.addWidget(self.other_file_list)

        self.files_splitter.addWidget(image_group)
        self.files_splitter.addWidget(document_group)

    def load_file(self):
        # Загрузка файлов в систему
        current_item = self.tree.currentItem()
        key = self.get_item_key(current_item) if current_item else "Главная"

        files, _ = QFileDialog.getOpenFileNames(self, "Выбрать файлы")
        if files:
            for file_path in files:
                file_name = os.path.basename(file_path)
                dest_folder = os.path.join(self.config.get("files_folder", "files"), *key.split('/'))
                os.makedirs(dest_folder, exist_ok=True)
                dest_path = os.path.join(dest_folder, file_name)

                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(file_name)
                    counter = 1
                    while os.path.exists(dest_path):
                        file_name = f"{base}_{counter}{ext}"
                        dest_path = os.path.join(dest_folder, file_name)
                        counter += 1

                try:
                    shutil.copy(file_path, dest_path)
                    # Чтение содержимого файла
                    file_content = read_file(dest_path)
                    self.db.add_file(key, file_name, file_content)
                except Exception as e:
                    logging.error(f"Ошибка при копировании файла: {e}")
                    QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить файл '{file_name}': {e}")
            self.load_files(key)

    def load_files(self, key):
        # Загрузка и отображение файлов в списках
        self.image_list.clear()
        self.other_file_list.clear()
        files = self.db.get_files(key)

        for file_name, file_content in files.items():
            file_path = os.path.join(self.config.get("files_folder", "files"), *key.split('/'), file_name)
            if not os.path.exists(file_path):
                logging.warning(f"Файл '{file_name}' не найден.")
                continue
            mime_type = get_mime_type(file_path)
            item = QListWidgetItem(file_name)
            item.setData(Qt.UserRole, file_path)
            if mime_type and mime_type.startswith('image'):
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
                    item.setIcon(icon)
                self.image_list.addItem(item)
            else:
                icon = QIcon.fromTheme('text-x-generic')
                if icon.isNull():
                    icon = QIcon(os.path.join(self.config["icons_folder"], 'document.png'))
                item.setIcon(icon)
                self.other_file_list.addItem(item)

    def open_file(self, item):
        # Открытие файла в системе
        file_path = item.data(Qt.UserRole)
        if os.path.exists(file_path):
            try:
                if sys.platform.startswith('darwin'):
                    subprocess.call(('open', file_path))
                elif os.name == 'nt':
                    os.startfile(file_path)
                elif os.name == 'posix':
                    subprocess.call(('xdg-open', file_path))
            except Exception as e:
                logging.error(f"Ошибка при открытии файла: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть файл '{file_path}': {e}")
        else:
            QMessageBox.warning(self, "Ошибка", f"Файл '{file_path}' не найден.")

    def perform_search(self):
        # Поиск по тексту
        search_text = self.search_bar.text()
        if search_text:
            self.progress_bar.show()
            self.progress_bar.setValue(0)
            self.search_thread = SearchThread(self.db, search_text)
            self.search_thread.progress_updated.connect(self.update_progress)
            self.search_thread.search_completed.connect(self.display_search_results)
            self.search_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_search_results(self, results):
        # Показ результатов поиска
        self.progress_bar.hide()
        if results:
            self.search_results_dialog = SearchResultsDialog(results, parent=self)
            self.search_results_dialog.show()
        else:
            QMessageBox.information(self, "Результаты поиска", "Ничего не найдено.")

    def on_text_changed(self):
        # Сохранение изменений текста
        current_item = self.tree.currentItem()
        key = self.get_item_key(current_item) if current_item else "Главная"
        content = self.text_editor.toHtml()
        self.db.save_content(key, content)

    def get_item_key(self, item):
        # Получение ключа элемента в дереве
        keys = []
        while item:
            keys.append(item.text(0))
            item = item.parent()
        return '/'.join(reversed(keys))

    def highlight_search_term(self, term):
        # Подсветка поискового термина в тексте
        self.text_editor.moveCursor(QTextCursor.Start)
        self.text_editor.setExtraSelections([])

        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(Qt.yellow))

        regex = QRegularExpression(term)
        regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)

        document = self.text_editor.document()
        plain_text = document.toPlainText()

        matches = regex.globalMatch(plain_text)
        extra_selections = []
        while matches.hasNext():
            match = matches.next()
            start = match.capturedStart()
            end = match.capturedEnd()
            cursor = self.text_editor.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            selection = QTextBrowser.ExtraSelection()
            selection.cursor = cursor
            selection.format = highlight_format
            extra_selections.append(selection)

        self.text_editor.setExtraSelections(extra_selections)

    def navigate_to_key(self, key):
        # Навигация к элементу по ключу
        item = self.find_tree_item_by_key(key)
        if item:
            self.tree.setCurrentItem(item)
            self.on_item_clicked(item, 0)
            self.highlight_search_term(self.search_bar.text())

    def find_tree_item_by_key(self, key):
        # Поиск элемента в дереве по ключу
        keys = key.split('/')
        root_items = self.tree.findItems(keys[0], Qt.MatchExactly)
        if root_items:
            item = root_items[0]
            for k in keys[1:]:
                found = False
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.text(0) == k:
                        item = child
                        found = True
                        break
                if not found:
                    return None
            return item
        return None

    def delete_files(self, key):
        # Удаление файлов, связанных с ключом
        files = self.db.get_files(key)
        dest_folder = os.path.join(self.config.get("files_folder", "files"), *key.split('/'))
        for file_name in files:
            file_path = os.path.join(dest_folder, file_name)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logging.info(f"Файл '{file_path}' удалён при удалении '{key}'.")
                except Exception as e:
                    logging.error(f"Ошибка при удалении файла '{file_path}': {e}")
        self.db.delete_files(key)

    def open_context_menu(self, position):
        selected_item = self.tree.itemAt(position)
        if selected_item:
            menu = QMenu()
            add_section_action = menu.addAction("Добавить раздел")
            add_category_action = menu.addAction("Добавить категорию")
            rename_action = menu.addAction("Переименовать")
            delete_action = menu.addAction("Удалить")
            action = menu.exec_(self.tree.viewport().mapToGlobal(position))
            if action == add_section_action:
                self.add_section()
            elif action == add_category_action:
                self.add_category(selected_item)
            elif action == rename_action:
                self.rename_item(selected_item)
            elif action == delete_action:
                self.delete_item(selected_item)

    def add_section(self):
        text, ok = QInputDialog.getText(self, "Добавить раздел", "Название раздела:")
        if ok and text:
            if self.db.add_section(text):
                self.load_sections()

    def add_category(self, parent_item):
        if parent_item:
            section_name = parent_item.text(0)
            text, ok = QInputDialog.getText(self, "Добавить категорию", "Название категории:")
            if ok and text:
                if self.db.add_category(section_name, text):
                    self.load_sections()

    def rename_item(self, item):
        old_name = item.text(0)
        text, ok = QInputDialog.getText(self, "Переименовать элемент", "Новое имя:", text=old_name)
        if ok and text and text != old_name:
            parent = item.parent()
            if parent:
                # Переименование категории
                section_name = parent.text(0)
                category_name = old_name
                new_category_name = text

                # Проверка, существует ли новая категория
                if new_category_name in self.db.data["sections"][section_name]:
                    QMessageBox.warning(self, "Ошибка", f"Категория '{new_category_name}' уже существует в разделе '{section_name}'.")
                    return

                # Добавляем новую категорию
                if self.db.add_category(section_name, new_category_name):
                    # Перенос содержимого
                    old_key = f"{section_name}/{category_name}"
                    new_key = f"{section_name}/{new_category_name}"
                    content = self.db.load_content(old_key)
                    self.db.save_content(new_key, content)
                    self.db.delete_content(old_key)

                    # Перенос файлов
                    files = self.db.get_files(old_key)
                    for file_name, file_content in files.items():
                        self.db.add_file(new_key, file_name, file_content)
                    self.db.delete_files(old_key)

                    # Удаление старой категории
                    self.db.delete_category(section_name, category_name)
                    self.load_sections()

            else:
                # Переименование раздела
                section_name = old_name
                new_section_name = text

                # Проверка, существует ли новый раздел
                if new_section_name in self.db.data["sections"]:
                    QMessageBox.warning(self, "Ошибка", f"Раздел '{new_section_name}' уже существует.")
                    return

                # Добавляем новый раздел
                if self.db.add_section(new_section_name):
                    # Перенос категорий
                    old_categories = self.db.data["sections"].get(section_name, [])
                    for category in old_categories:
                        self.db.add_category(new_section_name, category)

                    # Перенос содержимого раздела
                    old_key = section_name
                    new_key = new_section_name
                    content = self.db.load_content(old_key)
                    self.db.save_content(new_key, content)
                    self.db.delete_content(old_key)

                    # Перенос файлов раздела
                    files = self.db.get_files(old_key)
                    for file_name, file_content in files.items():
                        self.db.add_file(new_key, file_name, file_content)
                    self.db.delete_files(old_key)

                    # Удаление старого раздела
                    self.db.delete_section(section_name)
                    self.load_sections()

    def delete_item(self, item):
        reply = QMessageBox.question(
            self, 'Удалить элемент',
            f"Вы уверены, что хотите удалить '{item.text(0)}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            parent = item.parent()
            if parent:
                # Удаление категории
                section_name = parent.text(0)
                category_name = item.text(0)
                if self.db.delete_category(section_name, category_name):
                    self.load_sections()
            else:
                # Удаление раздела
                section_name = item.text(0)
                if self.db.delete_section(section_name):
                    self.load_sections()

    def select_font(self):
        font, ok = QFontDialog.getFont()
        if ok:
            self.text_editor.setCurrentFont(font)

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_editor.setTextColor(color)
