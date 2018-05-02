import time
from threading import Thread

from dexbot import __version__
from .ui.worker_list_window_ui import Ui_MainWindow
from .create_worker import CreateWorkerView
from .worker_item import WorkerItemWidget
from dexbot.controllers.create_worker_controller import CreateWorkerController
from dexbot.queue.queue_dispatcher import ThreadDispatcher
from dexbot.queue.idle_queue import idle_add

from PyQt5 import QtWidgets
from bitsharesapi.bitsharesnoderpc import BitSharesNodeRPC


class MainView(QtWidgets.QMainWindow):

    def __init__(self, main_ctrl):
        self.main_ctrl = main_ctrl
        super(MainView, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.worker_container = self.ui.verticalLayout
        self.max_workers = 10
        self.num_of_workers = 0
        self.worker_widgets = {}
        self.closing = False
        self.statusbar_updater = None
        self.statusbar_updater_first_run = True

        self.ui.add_worker_button.clicked.connect(self.handle_add_worker)

        # Load worker widgets from config file
        workers = main_ctrl.get_workers_data()
        for worker_name in workers:
            self.add_worker_widget(worker_name)

            # Limit the max amount of workers so that the performance isn't greatly affected
            self.num_of_workers += 1
            if self.num_of_workers >= self.max_workers:
                self.ui.add_worker_button.setEnabled(False)
                break

        # Dispatcher polls for events from the workers that are used to change the ui
        self.dispatcher = ThreadDispatcher(self)
        self.dispatcher.start()

        self.ui.status_bar.showMessage("ver {} - Node delay: - ms".format(__version__))
        self.statusbar_updater = Thread(
            target=self._update_statusbar_message
        )
        self.statusbar_updater.start()

    def add_worker_widget(self, worker_name):
        config = self.main_ctrl.get_worker_config(worker_name)
        widget = WorkerItemWidget(worker_name, config, self.main_ctrl, self)
        widget.setFixedSize(widget.frameSize())
        self.worker_container.addWidget(widget)
        self.worker_widgets[worker_name] = widget

        self.num_of_workers += 1
        if self.num_of_workers >= self.max_workers:
            self.ui.add_worker_button.setEnabled(False)

    def remove_worker_widget(self, worker_name):
        self.worker_widgets.pop(worker_name, None)

        self.num_of_workers -= 1
        if self.num_of_workers < self.max_workers:
            self.ui.add_worker_button.setEnabled(True)

    def handle_add_worker(self):
        controller = CreateWorkerController(self.main_ctrl)
        create_worker_dialog = CreateWorkerView(controller)
        return_value = create_worker_dialog.exec_()

        # User clicked save
        if return_value == 1:
            worker_name = create_worker_dialog.worker_name
            self.main_ctrl.add_worker_config(worker_name, create_worker_dialog.worker_data)
            self.add_worker_widget(worker_name)

    def set_worker_name(self, worker_name, value):
        self.worker_widgets[worker_name].set_worker_name(value)

    def set_worker_account(self, worker_name, value):
        self.worker_widgets[worker_name].set_worker_account(value)

    def set_worker_profit(self, worker_name, value):
        self.worker_widgets[worker_name].set_worker_profit(value)

    def set_worker_market(self, worker_name, value):
        self.worker_widgets[worker_name].set_worker_market(value)

    def set_worker_slider(self, worker_name, value):
        self.worker_widgets[worker_name].set_worker_slider(value)

    def customEvent(self, event):
        # Process idle_queue_dispatcher events
        event.callback()

    def closeEvent(self, event):
        self.closing = True
        self.ui.status_bar.showMessage("Closing app...")
        if self.statusbar_updater and self.statusbar_updater.is_alive():
            self.statusbar_updater.join()

    def _update_statusbar_message(self):
        while not self.closing:
            # When running first time the workers are also interrupting with the connection
            # so we delay the first time to get correct information
            if self.statusbar_updater_first_run:
                self.statusbar_updater_first_run = False
                time.sleep(1)

            idle_add(self.set_statusbar_message)
            runner_count = 0
            # Wait for 30s but do it in 0.5s pieces to not prevent closing the app
            while not self.closing and runner_count < 60:
                runner_count += 1
                time.sleep(0.5)

    def set_statusbar_message(self):
        config = self.main_ctrl.load_config()
        node = config['node']

        try:
            start = time.time()
            BitSharesNodeRPC(node, num_retries=1)
            latency = (time.time() - start) * 1000
        except BaseException:
            latency = -1

        if latency != -1:
            self.ui.status_bar.showMessage("ver {} - Node delay: {:.2f}ms".format(__version__, latency))
        else:
            self.ui.status_bar.showMessage("ver {} - Node disconnected".format(__version__))
