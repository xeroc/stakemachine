import importlib

from PyQt5 import QtWidgets, QtCore, QtGui


class AutoStrategyFormWidget(QtWidgets.QWidget):
    """ Automatic strategy form UI generator
    """

    def __init__(self, view, strategy_module, config):
        super().__init__()
        self.index = 0

        self.vertical_layout = QtWidgets.QVBoxLayout(view)
        self.vertical_layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QtWidgets.QGroupBox(view)
        self.group_box.setTitle("Worker Parameters")
        self.vertical_layout.addWidget(self.group_box)
        self.form_layout = QtWidgets.QFormLayout(self.group_box)

        strategy = getattr(
            importlib.import_module(strategy_module),
            'Strategy'
        )
        configure = strategy.configure(False)

        for config in configure:
            self.add_element(config)

    def add_element(self, config):
        extra = config.extra
        if config.type == 'float':
            self.add_double_spin_box(
                config.title, config.default, extra[0], extra[1], extra[2], extra[3], config.description)
        elif config.type == 'int':
            self.add_spin_box(config.title, config.default, extra[0], extra[1], extra[2], config.description)
        elif config.type == 'string':
            self.add_line_edit(config.title, config.default, config.description)
        elif config.type == 'bool':
            self.add_checkbox(config.title, config.default, config.description)

    def _add_label_wrap(self):
        wrap = QtWidgets.QWidget(self.group_box)
        wrap.setMinimumSize(QtCore.QSize(110, 0))
        wrap.setMaximumSize(QtCore.QSize(110, 16777215))

        layout = QtWidgets.QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.form_layout.setWidget(self.index, QtWidgets.QFormLayout.LabelRole, wrap)
        return wrap

    def add_tooltip(self, tooltip_text, container):
        tooltip = QtWidgets.QLabel(container)
        font = QtGui.QFont()
        font.setBold(True)
        tooltip.setFont(font)
        tooltip.setCursor(QtGui.QCursor(QtCore.Qt.WhatsThisCursor))

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        tooltip.setSizePolicy(size_policy)

        tooltip.setText('?')
        tooltip.setToolTip(tooltip_text)

        layout = container.layout()
        layout.addWidget(tooltip)

    def _add_label(self, text, description=''):
        wrap = self._add_label_wrap()
        label = QtWidgets.QLabel(wrap)
        label.setWordWrap(True)

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        label.setSizePolicy(size_policy)

        layout = wrap.layout()
        layout.addWidget(label)
        label.setText(text)

        if description:
            self.add_tooltip(description, wrap)

    def add_double_spin_box(self, text, default, minimum, maximum, precision, suffix='', description=''):
        self._add_label(text, description)

        input_field = QtWidgets.QDoubleSpinBox(self.group_box)
        input_field.setDecimals(precision)
        if minimum is not None:
            input_field.setMinimum(minimum)
        if maximum is not None:
            input_field.setMaximum(maximum)
        if suffix:
            input_field.setSuffix(suffix)
        input_field.setProperty('value', default)

        input_field.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        input_field.setSizePolicy(size_policy)
        input_field.setMinimumSize(QtCore.QSize(151, 0))

        self.form_layout.setWidget(self.index, QtWidgets.QFormLayout.FieldRole, input_field)
        self.index += 1

    def add_spin_box(self, text, default, minimum, maximum, suffix='', description=''):
        self._add_label(text, description)

        input_field = QtWidgets.QSpinBox(self.group_box)
        if minimum is not None:
            input_field.setMinimum(minimum)
        if maximum is not None:
            input_field.setMaximum(maximum)
        if suffix:
            input_field.setSuffix(suffix)
        input_field.setProperty('value', default)

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        input_field.setSizePolicy(size_policy)
        input_field.setMinimumSize(QtCore.QSize(151, 0))

        self.form_layout.setWidget(self.index, QtWidgets.QFormLayout.FieldRole, input_field)
        self.index += 1

    def add_line_edit(self, text, default, description=''):
        self._add_label(text, description)

        input_field = QtWidgets.QLineEdit(self.group_box)
        input_field.setProperty('value', default)
        self.form_layout.setWidget(self.index, QtWidgets.QFormLayout.FieldRole, input_field)
        self.index += 1

    def add_checkbox(self, text, default, description=''):
        self._add_label('', description)

        input_field = QtWidgets.QCheckBox(self.group_box)
        input_field.setText(text)
        input_field.setChecked(default)
        self.form_layout.setWidget(self.index, QtWidgets.QFormLayout.FieldRole, input_field)
        self.index += 1

