import csv
import os

from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QTableWidgetItem


class WorkerDetailsController:
    def __init__(self, view, worker_name, config):
        """ Initializes controller

            :param view: WorkerDetailsView
            :param worker_name: Worker's name
            :param config: Worker's config
        """
        self.view = view
        self.worker_name = worker_name
        self.config = config

    def initialize_worker_data(self):
        """ Initializes details view with worker's data

        """
        # Worker information
        self.view.worker_name.setText(self.worker_name)
        self.view.worker_account.setText(self.config.get('account'))

        # Common strategy information
        self.view.strategy_name.setText(self.config.get('module'))
        self.view.market.setText(self.config.get('market'))
        self.view.fee_asset.setText(self.config.get('fee_asset'))

    def add_graph(self, tab, file):
        # Fixme: If there is better way to print an image and scale it, fix this
        if os.path.isfile(file):
            tab.graph.setHtml('<img src=\'{}\'/>'.format(file))
            self.status_file_loaded(tab, file)
        else:
            self.status_file_not_found(tab, file)

        return tab.graph

    def populate_table_from_csv(self, tab, file, delimiter=';', first_item_header=True):
        try:
            with open(file, 'r') as csv_file:
                file_reader = csv.reader(csv_file, delimiter=delimiter)
                rows = list(file_reader)
        except FileNotFoundError:
            self.status_file_not_found(tab, file)
            return

        tab.table.setColumnCount(len(rows[0]))

        # Set headers
        if first_item_header:
            headers = rows.pop(0)
            for header_index, header in enumerate(headers):
                item = QTableWidgetItem()
                item.setText(header)
                tab.table.setHorizontalHeaderItem(header_index, item)

        # Set rows data
        tab.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, column in enumerate(row):
                item = QTableWidgetItem()
                item.setText(column)
                tab.table.setItem(row_index, column_index, item)

        self.status_file_loaded(tab, file)

        return tab.table

    def populate_text_from_file(self, tab, file):
        try:
            tab.text.setPlainText(open(file).read())
            tab.text.moveCursor(QTextCursor.End)
            self.status_file_loaded(tab, file)
            return tab.text
        except FileNotFoundError:
            self.status_file_not_found(tab, file)
            return

    @staticmethod
    def status_file_not_found(tab, file):
        tab.status_label.setStyleSheet('color: red;')
        return tab.status_label.setText('File \'{}\' not found'.format(file))

    @staticmethod
    def status_file_loaded(tab, file):
        tab.status_label.setStyleSheet('')
        return tab.status_label.setText('File \'{}\' loaded'.format(file))
