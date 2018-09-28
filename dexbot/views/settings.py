from dexbot.controllers.settings_controller import SettingsController
from dexbot.views.ui.settings_window_ui import Ui_settings_dialog

from PyQt5 import QtWidgets


class SettingsView(QtWidgets.QDialog, Ui_settings_dialog):

    def __init__(self):
        super().__init__()

        # Initialize view controller
        self.controller = SettingsController(self)

        self.setupUi(self)

        # Initialize list of nodes
        self.controller.initialize_node_list()

        # Since we are using "parents" for listing the nodes, they are actually "children" for the root item
        self.root_item = self.nodes_tree_widget.invisibleRootItem()

        # List controls
        self.add_button.clicked.connect(self.controller.add_node)
        self.remove_button.clicked.connect(self.controller.remove_node)
        self.move_up_button.clicked.connect(self.controller.move_up)
        self.move_down_button.clicked.connect(self.controller.move_down)
        self.restore_defaults_button.clicked.connect(self.controller.restore_defaults)

        # Dialog controls
        self.button_box.rejected.connect(self.reject)
        self.button_box.accepted.connect(self.controller.save_settings)
