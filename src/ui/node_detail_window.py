import plotly.graph_objects as go

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from src.database.database import get_records_by_serial


class NodeDetailWindow(QMainWindow):

    def __init__(self, node_data):
        super().__init__()

        self.node_data = node_data
        self.serial_number = node_data.get("serial_number", "")

        self.setWindowTitle(
            f"Node Details - {self.serial_number}"
        )

        self.resize(1000, 700)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        title = QLabel(
            f"Node: {self.serial_number}"
        )
        layout.addWidget(title)

        summary = QLabel(
            f"Voltage: {self.node_data.get('voltage', '')} mV | "
            f"Charge: {self.node_data.get('charge', '')}% | "
            f"GPS: {self.node_data.get('gps_quality', '')}% | "
            f"Health Score: {self.node_data.get('health_score', '')} | "
            f"Classification: {self.node_data.get('classification', '')}"
        )
        layout.addWidget(summary)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        central_widget.setLayout(layout)

        self.load_voltage_chart()

    def load_voltage_chart(self):
        df = get_records_by_serial(self.serial_number)

        if df.empty:
            self.web_view.setHtml("<h3>No records found</h3>")
            return

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["voltage_mv"],
                mode="lines+markers",
                name="Voltage (mV)"
            )
        )

        fig.update_layout(
            title=f"Voltage History - Node {self.serial_number}",
            xaxis_title="Time",
            yaxis_title="Voltage (mV)",
            template="plotly_white"
        )

        html = fig.to_html(
            include_plotlyjs="cdn"
        )

        self.web_view.setHtml(html)