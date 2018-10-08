from dexbot.controllers.worker_details_controller import WorkerDetailsController
from dexbot.views.ui.worker_details_window_ui import Ui_details_dialog
from dexbot.views.ui.tabs.graph_tab_ui import Ui_Graph_Tab
from dexbot.views.ui.tabs.table_tab_ui import Ui_Table_Tab
from dexbot.views.ui.tabs.text_tab_ui import Ui_Text_Tab

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget

import importlib


class WorkerDetailsView(QtWidgets.QDialog, Ui_details_dialog, Ui_Graph_Tab, Ui_Table_Tab, Ui_Text_Tab):

    def __init__(self, worker_name, config):
        super().__init__()

        self.config = config['workers'].get(worker_name)

        # Initialize view controller
        self.controller = WorkerDetailsController(self, worker_name, self.config)

        self.setupUi(self)

        # Add worker's name to the dialog title
        self.setWindowTitle("DEXBot - {} details".format(worker_name))

        # Get strategy class from the config
        strategy_class = getattr(importlib.import_module(self.config.get('module')), 'Strategy')
        details = strategy_class.configure_details()

        # Initialize other data to the dialog
        self.controller.initialize_worker_data()


        # Dialog controls
        self.button_box.rejected.connect(self.reject)

        # Add tabs to the details view
        # Todo: Continue from here
