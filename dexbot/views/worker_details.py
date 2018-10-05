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

        # Testing that each tab works as intended, Todo: Remove these after dynamic creation works
        self.tab_1 = QWidget(self)
        self.tab_2 = QWidget(self)
        self.tab_3 = QWidget(self)
        self.tab_4 = QWidget(self)

        graph_tab = Ui_Graph_Tab()
        table_tab = Ui_Table_Tab()
        table_tab_2 = Ui_Table_Tab()
        text_tab = Ui_Text_Tab()

        graph_tab.setupUi(self.tab_1)
        table_tab.setupUi(self.tab_2)
        table_tab_2.setupUi(self.tab_4)
        text_tab.setupUi(self.tab_3)

        graph_tab.graph_wrap.setTitle('Profit estimate')
        table_tab.table_wrap.setTitle('Worker\'s buy orders in the market')
        table_tab_2.table_wrap.setTitle('Worker\'s sell orders in the market')
        text_tab.text_wrap.setTitle('Local log')

        self.tabs_widget.addTab(self.tab_1, 'Profit')
        self.tabs_widget.addTab(self.tab_2, 'Buy Orders')
        self.tabs_widget.addTab(self.tab_4, 'Sell Orders')
        self.tabs_widget.addTab(self.tab_3, 'Log')

        # Dialog controls
        self.button_box.rejected.connect(self.reject)

        # Add tabs to the details view
        # Todo: Continue from here
