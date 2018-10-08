from dexbot.controllers.worker_details_controller import WorkerDetailsController
from dexbot.helper import *
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

        # DetailElements that are used to configure worker's detail view
        details = strategy_class.configure_details()

        # Initialize other data to the dialog
        self.controller.initialize_worker_data()

        # Add tabs to the details view
        # Todo: Make this prettier
        for detail in details:
            widget = QWidget(self)

            if detail.type == 'graph':
                tab = Ui_Graph_Tab()
                tab.setupUi(widget)
                tab.graph_wrap.setTitle(detail.title)

                # Get image path
                # Todo: Pass the image name from the strategy as well as the location
                directory = get_data_directory() + '/graphs'
                filename = os.path.join(directory, 'graph.jpg')

                # Create pixmap of the image
                pixmap = QtGui.QPixmap(filename)

                # Set graph image to the label
                tab.graph.setPixmap(pixmap)

                # Resize label to fit the image
                # Todo: Resize the tab to fit the image nicely
            elif detail.type == 'table':
                tab = Ui_Table_Tab()
                tab.setupUi(widget)
                tab.table_wrap.setTitle(detail.title)
            elif detail.type == 'text':
                tab = Ui_Text_Tab()
                tab.setupUi(widget)
                tab.text_wrap.setTitle(detail.title)

            self.tabs_widget.addTab(widget, detail.name)

        # Dialog controls
        self.button_box.rejected.connect(self.reject)
