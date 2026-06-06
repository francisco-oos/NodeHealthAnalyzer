from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
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

        self.nodes_label = QLabel("Nodes Loaded: 0")
        layout.addWidget(self.nodes_label)
        
        self.health_summary_label = QLabel(
        "Excellent: 0 | Good: 0 | Warning: 0 | Critical: 0"
        )
        layout.addWidget(self.health_summary_label)

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
        #BORRAR PARA PRODUCCION
        clear_database()
        self.nodes = self.importer.load_folder(folder)
        #BORRAR PARA PRODUCCION
        self.update_table()

    def update_table(self):
        self.table.clearContents()
        self.table.setRowCount(0)

        self.nodes_label.setText(
            f"Nodes Loaded: {len(self.nodes)}"
        )
        
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

        self.table.setRowCount(len(self.nodes))

        for row, node in enumerate(self.nodes):
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

            for column, value in enumerate(values):
                self.table.setItem(
                    row,
                    column,
                    QTableWidgetItem(str(value))
                )

        self.table.resizeColumnsToContents()

    def open_node_detail(self, row, column):
        if row < 0 or row >= len(self.nodes):
            return

        node_data = self.nodes[row]

        detail_window = NodeDetailWindow(node_data)
        detail_window.show()

        self.detail_windows.append(detail_window)