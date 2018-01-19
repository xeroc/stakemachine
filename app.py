import sys

from PyQt5 import Qt

from dexbot.controllers.main_controller import MainController


class App(Qt.QApplication):
    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)
        self.main_ctrl = MainController()

if __name__ == '__main__':
    app = App(sys.argv)
    sys.exit(app.exec_())