from PyQt5.QtWidgets import QApplication
import sys
from knowledge_base_app import KnowledgeBaseApp

def main():
    app = QApplication(sys.argv)
    window = KnowledgeBaseApp(mode='user')  # Запуск в пользовательском режиме
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
