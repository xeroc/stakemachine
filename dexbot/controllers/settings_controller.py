from dexbot.config import Config

from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtCore import Qt


class SettingsController:

    def __init__(self, view):
        self.config = Config()
        self.view = view

    def add_node(self):
        item = QTreeWidgetItem(self.view.nodes_tree_widget)
        item.setText(0, '')
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

        # Scroll to the new item and activate editing
        self.view.nodes_tree_widget.scrollToItem(item)
        self.view.nodes_tree_widget.editItem(item)

        self.view.notification_label.setText('Unsaved changes detected; Node added.')

    def move_up(self):
        """  Move item up in the widget tree list
        """
        current_index = self.view.nodes_tree_widget.indexOfTopLevelItem(self.view.nodes_tree_widget.currentItem())

        # This prevents moving item out of the list
        if current_index > 0:
            # Take the item out of the widget list
            item = self.view.nodes_tree_widget.takeTopLevelItem(current_index)

            # Put item back to the list in new position
            self.view.root_item.insertChild(current_index - 1, item)

            # Keep moved item selected
            self.view.nodes_tree_widget.setCurrentItem(item)
            self.view.notification_label.setText('Unsaved changes detected; List order has changed.')

    def move_down(self):
        """  Move item down in the widget tree list
        """
        current_index = self.view.nodes_tree_widget.indexOfTopLevelItem(self.view.nodes_tree_widget.currentItem())

        # This prevents moving item out of the list
        if current_index < (self.view.root_item.childCount() - 1):
            # Take the item out of the widget list
            item = self.view.nodes_tree_widget.takeTopLevelItem(current_index)

            # Put item back to the list in new position
            self.view.root_item.insertChild(current_index + 1, item)

            # Keep moved item selected
            self.view.nodes_tree_widget.setCurrentItem(item)
            self.view.notification_label.setText('Unsaved changes detected; List order has changed.')

    def save_settings(self):
        nodes = []

        child_count = self.view.root_item.childCount()

        for index in range(child_count):
            nodes.append(self.view.root_item.child(index).text(0))

        # Send the nodes to controller to handle the save
        self.save_nodes_to_config(nodes)
        self.initialize_node_list()

    def remove_node(self):
        node = self.view.nodes_tree_widget.currentItem()

        if node:
            # Delete only if node selected,
            index = self.view.nodes_tree_widget.indexOfTopLevelItem(node)
            self.view.nodes_tree_widget.takeTopLevelItem(index)
            self.view.notification_label.setText('Unsaved changes detected; Node removed.')

    def initialize_node_list(self, nodes=None):
        """ Populates Tree Widget with nodes

            :param nodes: List of nodes that can be applied to the widget instead of getting them from the config file.
        """
        # Make sure there are no widgets in the list
        self.view.nodes_tree_widget.clear()

        # Get nodes from the config file
        if nodes is None:
            nodes = self.view.controller.nodes

        # Add nodes to the widget list
        for node in nodes:
            item = QTreeWidgetItem(self.view.nodes_tree_widget)
            item.setText(0, node)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

    def save_nodes_to_config(self, nodes):
        """ Save nodes to the config file
        """
        # Remove empty nodes before saving, this is just to make sure no empty strings end up in config file
        nodes = self.remove_empty_items(nodes)

        self.config['node'] = nodes
        self.config.save_config()
        # Update status
        self.view.notification_label.setText('Settings successfully saved!')

    def restore_defaults(self):
        self.initialize_node_list(nodes=self.config.node_list)
        self.view.notification_label.setText('Restored default nodes. Remember to save changes!')

    @staticmethod
    def remove_empty_items(items_list):
        """ Removes empty strings from a list
        """
        return list(filter(None, items_list))

    @property
    def nodes(self):
        """ Returns nodes list from the config file

            :return: Nodes list
        """
        return self.config.get('node')
