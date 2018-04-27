import importlib

from PyQt5 import QtWidgets


class StrategyFormWidget(QtWidgets.QWidget):

    def __init__(self, controller, strategy_module, config=None):
        super().__init__()
        self.controller = controller
        self.module_name = strategy_module.split('.')[-1]

        form_module = controller.strategies[strategy_module]['form_module']
        widget = getattr(
            importlib.import_module(form_module),
            'Ui_Form'
        )
        self.strategy_widget = widget()
        self.strategy_widget.setupUi(self)

        # Call methods based on the selected strategy
        if self.module_name == 'relative_orders':
            self.strategy_widget.relative_order_size_checkbox.toggled.connect(
                self.onchange_relative_order_size_checkbox)
            if config:
                self.set_relative_orders_values(config)
        elif self.module_name == 'staggered_orders':
            if config:
                self.set_staggered_orders_values(config)

    def onchange_relative_order_size_checkbox(self, checked):
        if checked:
            self.order_size_input_to_relative()
        else:
            self.order_size_input_to_static()

    def order_size_input_to_relative(self):
        self.strategy_widget.amount_input.setSuffix('%')
        self.strategy_widget.amount_input.setDecimals(2)
        self.strategy_widget.amount_input.setMaximum(100.00)
        self.strategy_widget.amount_input.setMinimumWidth(151)
        self.strategy_widget.amount_input.setValue(10.00)

    def order_size_input_to_static(self):
        self.strategy_widget.amount_input.setSuffix('')
        self.strategy_widget.amount_input.setDecimals(8)
        self.strategy_widget.amount_input.setMaximum(1000000000.000000)
        self.strategy_widget.amount_input.setValue(0.000000)

    @property
    def values(self):
        """ Returns values all the form values based on selected strategy
        """
        if self.module_name == 'relative_orders':
            return self.relative_orders_values
        elif self.module_name == 'staggered_orders':
            return self.staggered_orders_values

    def set_relative_orders_values(self, worker_data):
        if worker_data.get('amount_relative', False):
            self.order_size_input_to_relative()
            self.strategy_widget.relative_order_size_checkbox.setChecked(True)
        else:
            self.order_size_input_to_static()
            self.strategy_widget.relative_order_size_checkbox.setChecked(False)

        self.strategy_widget.amount_input.setValue(float(worker_data.get('amount', 0)))
        self.strategy_widget.center_price_input.setValue(worker_data.get('center_price', 0))
        self.strategy_widget.spread_input.setValue(worker_data.get('spread', 5))

        if worker_data.get('center_price_dynamic', True):
            self.strategy_widget.center_price_dynamic_checkbox.setChecked(True)
        else:
            self.strategy_widget.center_price_dynamic_checkbox.setChecked(False)

    def set_staggered_orders_values(self, worker_data):
        self.strategy_widget.increment_input.setValue(worker_data.get('increment', 2.5))
        self.strategy_widget.spread_input.setValue(worker_data.get('spread', 5))
        self.strategy_widget.lower_bound_input.setValue(worker_data.get('lower_bound', 0.000001))
        self.strategy_widget.upper_bound_input.setValue(worker_data.get('upper_bound', 1000000))

    @property
    def relative_orders_values(self):
        # Remove the percentage character from the end
        spread = float(self.strategy_widget.spread_input.text()[:-1])

        # If order size is relative, remove percentage character from the end
        if self.strategy_widget.relative_order_size_checkbox.isChecked():
            amount = float(self.strategy_widget.amount_input.text()[:-1])
        else:
            amount = self.strategy_widget.amount_input.text()

        data = {
            'amount': amount,
            'amount_relative': bool(self.strategy_widget.relative_order_size_checkbox.isChecked()),
            'center_price': float(self.strategy_widget.center_price_input.text()),
            'center_price_dynamic': bool(self.strategy_widget.center_price_dynamic_checkbox.isChecked()),
            'spread': spread
        }
        return data

    @property
    def staggered_orders_values(self):
        # Remove the percentage character from the end
        spread = float(self.strategy_widget.spread_input.text()[:-1])
        increment = float(self.strategy_widget.increment_input.text()[:-1])

        data = {
            'spread': spread,
            'increment': increment,
            'lower_bound': float(self.strategy_widget.lower_bound_input.text()),
            'upper_bound': float(self.strategy_widget.upper_bound_input.text())
        }
        return data
