import importlib

import dexbot.controllers.strategy_controller

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

        # Invoke the correct controller
        class_name = ''
        if self.module_name == 'relative_orders':
            class_name = 'RelativeOrdersController'
        elif self.module_name == 'staggered_orders':
            class_name = 'StaggeredOrdersController'

        strategy_controller = getattr(
            dexbot.controllers.strategy_controller,
            class_name
        )
        self.strategy_controller = strategy_controller(self, controller, config)

    @property
    def values(self):
        """ Returns values all the form values based on selected strategy
        """
        return self.strategy_controller.values
