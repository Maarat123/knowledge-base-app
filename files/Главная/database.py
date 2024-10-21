import pickle
import threading
import os
import logging

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

class Database:
    def __init__(self, db_file='data.db'):
        self.db_file = db_file
        self.lock = threading.Lock()
        self.data = {
            "sections": {},
            "content": {},
            "files": {}
        }
        self.load_data()

    def load_data(self):
        # Проверяем, существует ли файл базы данных
        if os.path.exists(self.db_file):
            with open(self.db_file, 'rb') as f:
                try:
                    self.data = pickle.load(f)
                    logging.info("База данных успешно загружена.")
                except Exception as e:
                    logging.error(f"Ошибка при загрузке базы данных: {e}")
                    self.data = {"sections": {}, "content": {}, "files": {}}
        else:
            logging.info("Файл данных не найден. Начинаем с пустой базы данных.")

    def save_data(self):
        # Сохраняем данные в файл
        with self.lock:
            try:
                with open(self.db_file, 'wb') as f:
                    pickle.dump(self.data, f)
                logging.info("База данных успешно сохранена.")
            except Exception as e:
                logging.error(f"Ошибка при сохранении базы данных: {e}")

    def add_section(self, section_name):
        if section_name not in self.data["sections"]:
            self.data["sections"][section_name] = []
            self.save_data()
            logging.info(f"Раздел '{section_name}' добавлен.")
            return True
        logging.warning(f"Раздел '{section_name}' уже существует.")
        return False

    def delete_section(self, section_name):
        if section_name in self.data["sections"]:
            del self.data["sections"][section_name]
            self.delete_content(section_name)
            self.delete_files(section_name)
            self.save_data()
            logging.info(f"Раздел '{section_name}' удалён.")
            return True
        logging.warning(f"Раздел '{section_name}' не существует.")
        return False

    def add_category(self, section_name, category_name):
        if section_name in self.data["sections"] and category_name not in self.data["sections"][section_name]:
            self.data["sections"][section_name].append(category_name)
            self.save_data()
            logging.info(f"Категория '{category_name}' добавлена в раздел '{section_name}'.")
            return True
        logging.warning(f"Категория '{category_name}' уже существует в разделе '{section_name}'.")
        return False

    def delete_category(self, section_name, category_name):
        if section_name in self.data["sections"]:
            if category_name in self.data["sections"][section_name]:
                self.data["sections"][section_name].remove(category_name)
                self.delete_content(f"{section_name}/{category_name}")
                self.delete_files(f"{section_name}/{category_name}")
                self.save_data()
                logging.info(f"Категория '{category_name}' удалена из раздела '{section_name}'.")
                return True
        logging.warning(f"Категория '{category_name}' не существует в разделе '{section_name}'.")
        return False

    def save_content(self, key, content):
        self.data["content"][key] = content
        self.save_data()
        logging.info(f"Содержимое для '{key}' сохранено.")

    def load_content(self, key):
        return self.data["content"].get(key, "")

    def add_file(self, key, file_name, file_content):
        if key not in self.data["files"]:
            self.data["files"][key] = {}
        self.data["files"][key][file_name] = file_content
        self.save_data()
        logging.info(f"Файл '{file_name}' добавлен для ключа '{key}'.")

    def load_file(self, key, file_name):
        return self.data["files"].get(key, {}).get(file_name)

    def delete_content(self, key):
        if key in self.data["content"]:
            del self.data["content"][key]
            self.save_data()
            logging.info(f"Содержимое с ключом '{key}' удалено.")

    def delete_files(self, key):
        if key in self.data["files"]:
            del self.data["files"][key]
            self.save_data()
            logging.info(f"Файлы, связанные с ключом '{key}', удалены.")

    def get_sections(self):
        return self.data["sections"]

    def get_files(self, key):
        return self.data["files"].get(key, {})

    def update_file_order(self, key, files):
        self.data["files"][key] = files
        self.save_data()
        logging.info(f"Обновлён порядок файлов для ключа '{key}'.")
