from dexbot.controllers.worker_details_controller import WorkerDetailsController
from dexbot.views.ui.worker_details_window_ui import Ui_details_dialog

from PyQt5 import QtWidgets


class WorkerDetailsView(QtWidgets.QDialog, Ui_details_dialog):

    def __init__(self, worker_name, config):
        super().__init__()

        self.config = config

        # Initialize view controller
        self.controller = WorkerDetailsController(self, worker_name, self.config)

        self.setupUi(self)

        # Add worker's name to the dialog title
        self.setWindowTitle("DEXBot - {} details".format(worker_name))

        # Initialize other data to the dialog
        self.controller.initialize_worker_data()

        # Dialog controls
        self.button_box.rejected.connect(self.reject)
