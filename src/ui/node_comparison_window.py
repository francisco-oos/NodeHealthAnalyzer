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
from src.translations.language_manager import LanguageManager


class NodeComparisonWindow(QMainWindow):
    """
    Multi-node comparison window.

    Important:
    - Internal metric values stay in English.
    - Only visible UI text is translated.
    - CSV/database values are not modified.
    """

    def __init__(self, nodes):
        super().__init__()

        self.nodes = nodes
        self.last_figure_html = ""

        self.setWindowTitle(
            self.t("node_comparison")
        )

        self.resize(1100, 750)

        self.setup_ui()

    def t(self, key):
        """
        Translate visible UI text using global LanguageManager.
        """

        return LanguageManager.translate(key)

    def setup_ui(self):
        """
        Build comparison window interface.
        """

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        self.select_nodes_label = QLabel()
        layout.addWidget(self.select_nodes_label)

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

        self.select_all_button = QPushButton()
        self.select_all_button.clicked.connect(self.select_all_nodes)
        selection_layout.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton()
        self.clear_selection_button.clicked.connect(self.clear_selection)
        selection_layout.addWidget(self.clear_selection_button)

        layout.addLayout(selection_layout)

        date_layout = QHBoxLayout()

        self.start_date_label = QLabel()
        self.end_date_label = QLabel()

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd/MM/yyyy")

        self.configure_date_range()

        date_layout.addWidget(self.start_date_label)
        date_layout.addWidget(self.start_date)

        date_layout.addWidget(self.end_date_label)
        date_layout.addWidget(self.end_date)

        layout.addLayout(date_layout)

        self.metric_label = QLabel()
        layout.addWidget(self.metric_label)

        self.metric_filter = QComboBox()
        self.metric_filter.addItem(self.t("voltage"), "Voltage")
        self.metric_filter.addItem(self.t("charge"), "Charge")
        self.metric_filter.addItem(self.t("temperature"), "Temperature")
        self.metric_filter.addItem(self.t("gps_quality"), "GPS Quality")
        layout.addWidget(self.metric_filter)

        self.compare_button = QPushButton()
        self.compare_button.clicked.connect(
            self.load_comparison_chart
        )
        layout.addWidget(self.compare_button)

        self.export_html_button = QPushButton()
        self.export_html_button.clicked.connect(
            self.export_chart_html
        )
        layout.addWidget(self.export_html_button)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        central_widget.setLayout(layout)

        self.apply_language()

    def apply_language(self):
        """
        Apply translations to visible controls.
        """

        self.setWindowTitle(
            self.t("node_comparison")
        )

        self.title_label.setText(
            self.t("node_comparison")
        )

        self.info_label.setText(
            f"{self.t('select_nodes')}, {self.t('metric')}, "
            f"{self.t('compare_selected')}"
        )

        self.select_nodes_label.setText(
            self.t("select_nodes")
        )

        self.select_all_button.setText(
            self.t("select_all")
        )

        self.clear_selection_button.setText(
            self.t("clear_selection")
        )

        self.start_date_label.setText(
            self.t("start_date")
        )

        self.end_date_label.setText(
            self.t("end_date")
        )

        self.metric_label.setText(
            self.t("metric")
        )

        self.compare_button.setText(
            self.t("compare_selected")
        )

        self.export_html_button.setText(
            self.t("export_chart_html")
        )

        self.web_view.setHtml(
            f"<h3>{self.t('select_nodes')}</h3>"
        )

    def select_all_nodes(self):
        """
        Select all visible nodes in the list.
        """

        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            item.setSelected(True)

    def clear_selection(self):
        """
        Clear node selection.
        """

        self.node_list.clearSelection()

    def get_metric_config(self):
        """
        Return selected metric configuration.
        itemData keeps the internal value.
        """

        selected_metric = self.metric_filter.currentData()

        metric_config = {
            "Voltage": {
                "column": "voltage_mv",
                "title": f"{self.t('voltage')} Comparison",
                "axis": "Voltage (mV)",
            },
            "Charge": {
                "column": "charge_percent",
                "title": f"{self.t('charge')} Comparison",
                "axis": "Charge (%)",
            },
            "Temperature": {
                "column": "temperature_c",
                "title": f"{self.t('temperature')} Comparison",
                "axis": "Temperature (°C)",
            },
            "GPS Quality": {
                "column": "gps_quality",
                "title": f"{self.t('gps_quality')} Comparison",
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
        Configure comparison date range using all loaded nodes.
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
        Build and render comparison chart.
        """

        selected_items = self.node_list.selectedItems()

        if not selected_items:
            self.web_view.setHtml(
                f"<h3>{self.t('select_nodes')}</h3>"
            )
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
            f"{self.t('compare_selected')}: "
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

            # GPS during No acquisition can distort operational interpretation.
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
            legend_title=self.t("node"),
        )

        html = fig.to_html(
            include_plotlyjs="cdn"
        )

        self.last_figure_html = html
        self.web_view.setHtml(html)

    def export_chart_html(self):
        """
        Export last generated chart as interactive HTML.
        """

        if not self.last_figure_html:
            QMessageBox.warning(
                self,
                self.t("export_chart_html"),
                "No chart available to export. Generate a comparison first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.t("export_chart_html"),
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
                self.t("export_chart_html"),
                "Comparison chart exported successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Chart HTML Error",
                str(e)
            )