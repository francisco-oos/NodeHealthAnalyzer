from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)


class NodeDetailWindow(QMainWindow):

    def __init__(self, node_data):
        super().__init__()

        self.node_data = node_data

        self.setWindowTitle(
            f"Node Details - {node_data.get('serial_number', '')}"
        )

        self.resize(600, 400)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        title = QLabel(
            f"Node: {self.node_data.get('serial_number', '')}"
        )
        layout.addWidget(title)

        details = [
            f"Records: {self.node_data.get('records', '')}",
            f"Voltage: {self.node_data.get('voltage', '')} mV",
            f"Charge: {self.node_data.get('charge', '')} %",
            f"Acq Type: {self.node_data.get('acq_type', '')}",
            f"GPS Quality: {self.node_data.get('gps_quality', '')} %",
            f"Temperature: {self.node_data.get('temperature', '')} °C",
            f"Last Time: {self.node_data.get('last_time', '')}",
            f"Health Score: {self.node_data.get('health_score', '')}",
            f"Classification: {self.node_data.get('classification', '')}",
        ]

        for item in details:
            layout.addWidget(QLabel(item))

        central_widget.setLayout(layout)