import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QDate
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.database.database import get_records_by_serial


class NodeComparisonWindow(QMainWindow):
    """
    Multi-node comparison window.

    Responsibilities:
    - Select multiple nodes.
    - Select a metric.
    - Filter by date range.
    - Plot selected nodes on the same chart.
    """

    def __init__(self, nodes):
        super().__init__()

        self.nodes = nodes
        self.last_figure_html = ""

        self.setWindowTitle("Node Comparison")
        self.resize(1100, 750)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        title = QLabel("Node Comparison")
        layout.addWidget(title)

        self.info_label = QLabel(
            "Select one or more nodes, choose a metric, then click Compare."
        )
        layout.addWidget(self.info_label)

        layout.addWidget(QLabel("Select Nodes"))

        self.node_list = QListWidget()
        self.node_list.setSelectionMode(
            QAbstractItemView.MultiSelection
        )

        for node in self.nodes:
            serial_number = node.get("serial_number", "")
            item = QListWidgetItem(serial_number)
            self.node_list.addItem(item)

        layout.addWidget(self.node_list)

        selection_layout = QHBoxLayout()

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.select_all_nodes)
        selection_layout.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        selection_layout.addWidget(self.clear_selection_button)

        layout.addLayout(selection_layout)

        date_layout = QHBoxLayout()

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd/MM/yyyy")

        self.configure_date_range()

        date_layout.addWidget(QLabel("Start Date"))
        date_layout.addWidget(self.start_date)

        date_layout.addWidget(QLabel("End Date"))
        date_layout.addWidget(self.end_date)

        layout.addLayout(date_layout)

        layout.addWidget(QLabel("Metric"))

        self.metric_filter = QComboBox()
        self.metric_filter.addItems(
            [
                "Voltage",
                "Charge",
                "Temperature",
                "GPS Quality",
            ]
        )
        layout.addWidget(self.metric_filter)

        self.compare_button = QPushButton("Compare Selected Nodes")
        self.compare_button.clicked.connect(
            self.load_comparison_chart
        )
        layout.addWidget(self.compare_button)

        self.export_html_button = QPushButton("Export Chart HTML")
        self.export_html_button.clicked.connect(
            self.export_chart_html
        )
        layout.addWidget(self.export_html_button)

        self.web_view = QWebEngineView()
        self.web_view.setHtml(
            "<h3>Select nodes and click Compare Selected Nodes</h3>"
        )
        layout.addWidget(self.web_view)

        central_widget.setLayout(layout)

    def select_all_nodes(self):
        """
        Select all nodes in the list.
        Useful when comparing all currently filtered dashboard nodes.
        """

        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            item.setSelected(True)

    def clear_selection(self):
        """
        Clear current node selection.
        """

        self.node_list.clearSelection()

    def get_metric_config(self):
        """
        Return selected metric configuration.
        """

        selected_metric = self.metric_filter.currentText()

        metric_config = {
            "Voltage": {
                "column": "voltage_mv",
                "title": "Voltage Comparison",
                "axis": "Voltage (mV)",
            },
            "Charge": {
                "column": "charge_percent",
                "title": "Charge Comparison",
                "axis": "Charge (%)",
            },
            "Temperature": {
                "column": "temperature_c",
                "title": "Temperature Comparison",
                "axis": "Temperature (°C)",
            },
            "GPS Quality": {
                "column": "gps_quality",
                "title": "GPS Quality Comparison",
                "axis": "GPS Quality (%)",
            },
        }

        return metric_config.get(
            selected_metric,
            metric_config["Voltage"]
        )

    def parse_timestamps(self, df):
        """
        Parse Sercel and SQLite timestamp formats.

        Supported formats:
        - dd/mm/yyyy HH:MM:SS
        - dd/mm/yyyy HH:MM
        - yyyy-mm-dd HH:MM:SS
        """

        df = df.copy()

        if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            return df

        raw_timestamp = df["timestamp"].astype(str).str.strip()

        parsed = pd.to_datetime(
            raw_timestamp,
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce"
        )

        missing_mask = parsed.isna()

        if missing_mask.any():
            parsed_no_seconds = pd.to_datetime(
                raw_timestamp[missing_mask],
                format="%d/%m/%Y %H:%M",
                errors="coerce"
            )
            parsed.loc[missing_mask] = parsed_no_seconds

        missing_mask = parsed.isna()

        if missing_mask.any():
            parsed_iso = pd.to_datetime(
                raw_timestamp[missing_mask],
                errors="coerce"
            )
            parsed.loc[missing_mask] = parsed_iso

        df["timestamp"] = parsed

        return df

    def configure_date_range(self):
        """
        Configure comparison date filter using the minimum and maximum
        timestamp available across all nodes passed to this window.
        """

        min_date = None
        max_date = None

        for node in self.nodes:
            serial_number = node.get("serial_number", "")
            df = get_records_by_serial(serial_number)

            if df.empty:
                continue

            df = self.parse_timestamps(df)
            df = df.dropna(subset=["timestamp"])

            if df.empty:
                continue

            node_min = df["timestamp"].min()
            node_max = df["timestamp"].max()

            if min_date is None or node_min < min_date:
                min_date = node_min

            if max_date is None or node_max > max_date:
                max_date = node_max

        if min_date is None or max_date is None:
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            return

        min_qdate = QDate(
            min_date.year,
            min_date.month,
            min_date.day
        )

        max_qdate = QDate(
            max_date.year,
            max_date.month,
            max_date.day
        )

        self.start_date.setMinimumDate(min_qdate)
        self.start_date.setMaximumDate(max_qdate)
        self.end_date.setMinimumDate(min_qdate)
        self.end_date.setMaximumDate(max_qdate)

        self.start_date.setDate(min_qdate)
        self.end_date.setDate(max_qdate)

    def load_comparison_chart(self):
        """
        Build and render the comparison chart.
        """

        selected_items = self.node_list.selectedItems()

        if not selected_items:
            self.web_view.setHtml("<h3>Select at least one node.</h3>")
            return

        metric = self.get_metric_config()
        metric_column = metric["column"]

        start_dt = pd.to_datetime(
            self.start_date.date().toString("dd/MM/yyyy"),
            format="%d/%m/%Y",
            errors="coerce"
        )

        end_dt = pd.to_datetime(
            self.end_date.date().toString("dd/MM/yyyy"),
            format="%d/%m/%Y",
            errors="coerce"
        )

        end_dt = end_dt + pd.Timedelta(days=1)

        fig = go.Figure()
        plotted_nodes = 0

        selected_serials = [
            item.text()
            for item in selected_items
        ]

        self.info_label.setText(
            f"Comparing {len(selected_serials)} node(s): "
            + ", ".join(selected_serials)
        )

        for serial_number in selected_serials:
            df = get_records_by_serial(serial_number)

            if df.empty:
                continue

            df = self.parse_timestamps(df)

            if metric_column not in df.columns:
                continue

            df[metric_column] = pd.to_numeric(
                df[metric_column],
                errors="coerce"
            )

            df = df.dropna(
                subset=["timestamp", metric_column]
            )

            df = df[
                (df["timestamp"] >= start_dt)
                &
                (df["timestamp"] < end_dt)
            ]

            # Charge sometimes reports 0 when the node is not acquiring.
            # Those records distort the real battery curve.
            if metric_column == "charge_percent":
                df = df[
                    (df["charge_percent"] > 0)
                    &
                    (df["acq_type"] != "No acquisition")
                ]

            # GPS Quality during "No acquisition" is often not useful
            # for operational acquisition analysis.
            if metric_column == "gps_quality":
                df = df[
                    df["acq_type"] != "No acquisition"
                ]

            df = df.sort_values(
                by="timestamp"
            )

            if df.empty:
                continue

            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[metric_column],
                    mode="lines",
                    name=serial_number
                )
            )

            plotted_nodes += 1

        if plotted_nodes == 0:
            self.web_view.setHtml(
                "<h3>No valid data found for selected nodes, metric and date range.</h3>"
            )
            self.last_figure_html = ""
            return

        fig.update_layout(
            title=metric["title"],
            xaxis_title="Time",
            yaxis_title=metric["axis"],
            template="plotly_white",
            legend_title="Nodes",
        )

        html = fig.to_html(
            include_plotlyjs="cdn"
        )

        self.last_figure_html = html
        self.web_view.setHtml(html)

    def export_chart_html(self):
        """
        Export last generated comparison chart as an interactive HTML file.
        """

        if not self.last_figure_html:
            QMessageBox.warning(
                self,
                "Export Chart HTML",
                "No chart available to export. Generate a comparison first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Comparison Chart",
            "node_comparison_chart.html",
            "HTML Files (*.html)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(self.last_figure_html)

            QMessageBox.information(
                self,
                "Export Chart HTML",
                "Comparison chart exported successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Chart HTML Error",
                str(e)
            )