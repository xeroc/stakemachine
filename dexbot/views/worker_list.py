from .ui.worker_list_window_ui import Ui_MainWindow
from .create_worker import CreateWorkerView
from .worker_item import WorkerItemWidget
from dexbot.controllers.create_worker_controller import CreateWorkerController
from dexbot.queue.queue_dispatcher import ThreadDispatcher

from PyQt5 import QtWidgets


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
