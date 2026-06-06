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

from src.importers.importer import CSVImporter


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Node Health Analyzer")
        self.resize(1200, 800)

        self.importer = CSVImporter()
        self.nodes = []

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

        self.table = QTableWidget()
        self.table.setColumnCount(8)
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
            ]
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

        self.nodes = self.importer.load_folder(folder)

        self.update_table()

    def update_table(self):
        self.table.clearContents()
        self.table.setRowCount(0)

        self.nodes_label.setText(
            f"Nodes Loaded: {len(self.nodes)}"
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
            ]

            for column, value in enumerate(values):
                self.table.setItem(
                    row,
                    column,
                    QTableWidgetItem(str(value))
                )

        self.table.resizeColumnsToContents()