import re

from .ui.worker_item_widget_ui import Ui_widget
from .confirmation import ConfirmationDialog
from .edit_worker import EditWorkerView
from dexbot.storage import db_worker
from dexbot.controllers.create_worker_controller import CreateWorkerController
from dexbot.views.errors import gui_error
from dexbot.resources import icons_rc

from PyQt5 import QtCore, QtWidgets


class WorkerItemWidget(QtWidgets.QWidget, Ui_widget):

    def __init__(self, worker_name, config, main_ctrl, view):
        super().__init__()

        self.main_ctrl = main_ctrl
        self.running = False
        self.worker_name = worker_name
        self.worker_config = config
        self.view = view

        self.setupUi(self)

        self.edit_button.clicked.connect(self.handle_edit_worker)

        self.toggle.mouseReleaseEvent=self.toggle_worker
        self.onoff.mouseReleaseEvent=self.toggle_worker

        self.setup_ui_data(config)

    def setup_ui_data(self, config):
        worker_name = list(config['workers'].keys())[0]
        self.set_worker_name(worker_name)

        market = config['workers'][worker_name]['market']
        self.set_worker_market(market)

        profit = db_worker.execute(db_worker.get_item, worker_name, 'profit')
        if profit:
            self.set_worker_profit(profit)
        else:
            self.set_worker_profit(0)

        percentage = db_worker.execute(db_worker.get_item, worker_name, 'slider')
        if percentage:
            self.set_worker_slider(percentage)
        else:
            self.set_worker_slider(50)

    @gui_error
    def toggle_worker(self):
        if self.horizontalLayout_5.alignment() != QtCore.Qt.AlignRight:
            toggle_alignment = QtCore.Qt.AlignRight
            toggle_label_text = "TURN WORKER OFF"
        else:
            toggle_alignment = QtCore.Qt.AlignLeft
            toggle_label_text = "TURN WORKER ON"

        _translate = QtCore.QCoreApplication.translate
        self.toggle_label.setText(_translate("widget", toggle_label_text))
        self.horizontalLayout_5.setAlignment(toggle_alignment)

        # TODO: better way of repainting the widget
        self.toggle.hide()
        self.toggle.show()

    @gui_error
    def start_worker(self):
        self._start_worker()
        self.main_ctrl.create_worker(self.worker_name, self.worker_config, self.view)

    def _start_worker(self):
        self.running = True
        self.pause_button.show()
        self.play_button.hide()

    @gui_error
    def pause_worker(self):
        self._pause_worker()
        self.main_ctrl.stop_worker(self.worker_name)

    def _pause_worker(self):
        self.running = False
        self.pause_button.hide()
        self.play_button.show()

    def set_worker_name(self, value):
        self.worker_name_label.setText(value)

    def set_worker_account(self, value):
        pass

    def set_worker_market(self, value):
        self.currency_label.setText(value)

        values = re.split("[/:]", value)
        self.base_asset_label.setText(values[0])
        self.quote_asset_label.setText(values[1])

    def set_worker_profit(self, value):
        value = float(value)
        if value >= 0:
            value = '+' + str(value)

        value = str(value) + '%'
        self.profit_label.setText(value)

    def set_worker_slider(self, value):
        barWidth = self.bar.width();

        spacing = self.bar.layout().spacing();
        margin_left = self.bar.layout().contentsMargins().left()
        margin_right = self.bar.layout().contentsMargins().right()
        total_padding = spacing + margin_left + margin_right

        base_width = (barWidth-total_padding) * (value/100)

        self.base_asset_label.setMaximumWidth(base_width)
        self.base_asset_label.setMinimumWidth(base_width)

    @gui_error
    def remove_widget_dialog(self):
        dialog = ConfirmationDialog('Are you sure you want to remove worker "{}"?'.format(self.worker_name))
        return_value = dialog.exec_()
        if return_value:
            self.remove_widget()
            self.main_ctrl.remove_worker_config(self.worker_name)

    def remove_widget(self):
        self.main_ctrl.remove_worker(self.worker_name)
        self.deleteLater()
        self.view.remove_worker_widget(self.worker_name)
        self.view.ui.add_worker_button.setEnabled(True)

    def reload_widget(self, worker_name):
        """ Reload the data of the widget
        """
        self.worker_config = self.main_ctrl.get_worker_config(worker_name)
        self.setup_ui_data(self.worker_config)
        self._pause_worker()

    @gui_error
    def handle_edit_worker(self):
        controller = CreateWorkerController(self.main_ctrl)
        edit_worker_dialog = EditWorkerView(self, controller, self.worker_name, self.worker_config)
        return_value = edit_worker_dialog.exec_()

        # User clicked save
        if return_value:
            new_worker_name = edit_worker_dialog.worker_name
            self.main_ctrl.remove_worker(self.worker_name)
            self.main_ctrl.replace_worker_config(self.worker_name, new_worker_name, edit_worker_dialog.worker_data)
            self.reload_widget(new_worker_name)
            self.worker_name = new_worker_name

