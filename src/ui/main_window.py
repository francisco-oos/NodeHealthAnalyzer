import pandas as pd

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.database.database import clear_database
from src.importers.importer import CSVImporter
from src.ui.node_detail_window import NodeDetailWindow


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Node Health Analyzer")
        self.resize(1200, 800)

        self.importer = CSVImporter()
        self.nodes = []
        self.detail_windows = []

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel("Node Health Analyzer")
        layout.addWidget(self.title_label)

        self.import_button = QPushButton("Import Folder")
        self.import_button.clicked.connect(self.import_folder)
        layout.addWidget(self.import_button)

        self.export_excel_button = QPushButton("Export Excel")
        self.export_excel_button.clicked.connect(
            self.export_excel
        )
        layout.addWidget(self.export_excel_button)

        self.nodes_label = QLabel("Nodes Loaded: 0")
        layout.addWidget(self.nodes_label)

        self.health_summary_label = QLabel(
            "Excellent: 0 | Good: 0 | Warning: 0 | Critical: 0"
        )
        layout.addWidget(self.health_summary_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Node...")
        self.search_box.textChanged.connect(self.update_table)
        layout.addWidget(self.search_box)

        self.classification_filter = QComboBox()
        self.classification_filter.addItems(
            [
                "All",
                "Excellent",
                "Good",
                "Warning",
                "Critical",
            ]
        )
        self.classification_filter.currentTextChanged.connect(
            self.update_table
        )
        layout.addWidget(self.classification_filter)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "Node",
                "Records",
                "Voltage (mV)",
                "Charge (%)",
                "Acq Type",
                "GPS (%)",
                "Temp (°C)",
                "Last Time",
                "Health Score",
                "Classification",
            ]
        )

        self.table.cellDoubleClicked.connect(
            self.open_node_detail
        )

        layout.addWidget(self.table)
        central_widget.setLayout(layout)

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )

        if not folder:
            return

        self.nodes = []
        self.table.clearContents()
        self.table.setRowCount(0)

        self.nodes_label.setText("Nodes Loaded: 0")
        self.health_summary_label.setText(
            "Excellent: 0 | Good: 0 | Warning: 0 | Critical: 0"
        )

        self.search_box.clear()
        self.classification_filter.setCurrentText("All")

        # BORRAR PARA PRODUCCION
        clear_database()

        self.nodes = self.importer.load_folder(folder)

        self.update_table()

    def get_filtered_nodes(self):
        filtered_nodes = self.nodes

        search_text = self.search_box.text().strip()

        if search_text:
            filtered_nodes = [
                node
                for node in filtered_nodes
                if search_text in node.get("serial_number", "")
            ]

        selected_classification = self.classification_filter.currentText()

        if selected_classification != "All":
            filtered_nodes = [
                node
                for node in filtered_nodes
                if node.get("classification") == selected_classification
            ]

        return filtered_nodes

    def update_health_summary(self):
        excellent = sum(
            1 for node in self.nodes
            if node.get("classification") == "Excellent"
        )

        good = sum(
            1 for node in self.nodes
            if node.get("classification") == "Good"
        )

        warning = sum(
            1 for node in self.nodes
            if node.get("classification") == "Warning"
        )

        critical = sum(
            1 for node in self.nodes
            if node.get("classification") == "Critical"
        )

        self.health_summary_label.setText(
            f"Excellent: {excellent} | "
            f"Good: {good} | "
            f"Warning: {warning} | "
            f"Critical: {critical}"
        )

    def update_table(self):
        self.table.clearContents()
        self.table.setRowCount(0)

        self.nodes_label.setText(
            f"Nodes Loaded: {len(self.nodes)}"
        )

        self.update_health_summary()

        filtered_nodes = self.get_filtered_nodes()

        self.table.setRowCount(len(filtered_nodes))

        classification_colors = {
            "Excellent": QColor(0, 180, 0),
            "Good": QColor(0, 120, 255),
            "Warning": QColor(255, 165, 0),
            "Critical": QColor(255, 60, 60),
        }

        for row, node in enumerate(filtered_nodes):

            values = [
                node.get("serial_number", ""),
                node.get("records", ""),
                node.get("voltage", ""),
                node.get("charge", ""),
                node.get("acq_type", ""),
                node.get("gps_quality", ""),
                node.get("temperature", ""),
                node.get("last_time", ""),
                node.get("health_score", ""),
                node.get("classification", ""),
            ]

            classification = node.get("classification", "")
            classification_color = classification_colors.get(
                classification,
                QColor(255, 255, 255)
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in [8, 9]:
                    item.setForeground(classification_color)
                    item.setFont(QFont("", -1, QFont.Bold))

                self.table.setItem(
                    row,
                    column,
                    item
                )

        self.table.resizeColumnsToContents()

    def export_excel(self):
        filtered_nodes = self.get_filtered_nodes()

        if not filtered_nodes:
            QMessageBox.warning(
                self,
                "Export Excel",
                "No data available to export."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel Report",
            "node_health_report.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        rows = []

        for node in filtered_nodes:
            rows.append({
                "Node": node.get("serial_number", ""),
                "Records": node.get("records", ""),
                "Voltage (mV)": node.get("voltage", ""),
                "Charge (%)": node.get("charge", ""),
                "Acq Type": node.get("acq_type", ""),
                "GPS (%)": node.get("gps_quality", ""),
                "Temp (°C)": node.get("temperature", ""),
                "Last Time": node.get("last_time", ""),
                "Health Score": node.get("health_score", ""),
                "Classification": node.get("classification", ""),
            })

        df = pd.DataFrame(rows)

        try:
            df.to_excel(
                file_path,
                index=False
            )

            QMessageBox.information(
                self,
                "Export Excel",
                "Excel report exported successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Excel Error",
                str(e)
            )

    def open_node_detail(self, row, column):
        filtered_nodes = self.get_filtered_nodes()

        if row < 0 or row >= len(filtered_nodes):
            return

        node_data = filtered_nodes[row]

        detail_window = NodeDetailWindow(node_data)
        detail_window.show()

        self.detail_windows.append(detail_window)