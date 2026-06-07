import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QDate, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QPushButton,
    QDateEdit,
    QHBoxLayout,
)

from src.database.database import get_records_by_serial
from src.translations.language_manager import LanguageManager
from pathlib import Path
import tempfile
import uuid

from PySide6.QtCore import QDate, QUrl

class NodeDetailWindow(QMainWindow):
    """
    Node detail window.

    Important:
    - Internal CSV/database values are NOT translated.
    - Only user-visible labels are translated.
    - Acquisition values remain:
      Seismic, BIT, No acquisition.
    - Metric internal values remain:
      Voltage, Charge, Temperature, GPS Quality.
    """

    def __init__(self, node_data):
        super().__init__()

        self.node_data = node_data
        self.serial_number = node_data.get("serial_number", "")

        self.records_df = get_records_by_serial(self.serial_number)

        self.setWindowTitle(
            f"{self.t('node')} Details - {self.serial_number}"
        )

        self.resize(1000, 700)

        self.setup_ui()

    def t(self, key):
        """
        Translate visible text using the global language manager.
        """
        return LanguageManager.translate(key)

    def setup_ui(self):
        """
        Build node detail interface.
        """

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        self.available_range_label = QLabel()
        layout.addWidget(self.available_range_label)

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

        self.metric_filter = QComboBox()
        self.metric_filter.addItem(self.t("voltage"), "Voltage")
        self.metric_filter.addItem(self.t("charge"), "Charge")
        self.metric_filter.addItem(self.t("temperature"), "Temperature")
        self.metric_filter.addItem(self.t("gps_quality"), "GPS Quality")
        layout.addWidget(self.metric_filter)

        self.acq_filter = QComboBox()
        self.acq_filter.addItem(self.t("all"), "All")
        self.acq_filter.addItem(self.t("seismic"), "Seismic")
        self.acq_filter.addItem(self.t("bit"), "BIT")
        self.acq_filter.addItem(self.t("no_acquisition"), "No acquisition")
        layout.addWidget(self.acq_filter)

        self.apply_filter_button = QPushButton()
        self.apply_filter_button.clicked.connect(
            self.load_metric_chart
        )
        layout.addWidget(self.apply_filter_button)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        central_widget.setLayout(layout)

        self.apply_language()
        self.load_metric_chart()

    def apply_language(self):
        """
        Apply translations to static visible labels.
        """
        self.setWindowTitle(
            f"{self.t('node')} Details - {self.serial_number}"
        )

        self.title_label.setText(
            f"{self.t('node')}: {self.serial_number}"
        )

        self.summary_label.setText(
            f"{self.t('voltage')}: {self.node_data.get('voltage', '')} mV | "
            f"{self.t('charge')}: {self.node_data.get('charge', '')}% | "
            f"GPS: {self.node_data.get('gps_quality', '')}% | "
            f"{self.t('health_score')}: {self.node_data.get('health_score', '')} | "
            f"{self.t('classification')}: {self.node_data.get('classification', '')}"
        )

        self.start_date_label.setText(self.t("start_date"))
        self.end_date_label.setText(self.t("end_date"))
        self.apply_filter_button.setText(self.t("apply_filter"))

    def parse_timestamps(self, df):
        """
        Parse Sercel/SQLite timestamps.

        Supported:
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
        Configure min/max date based on node records.
        """

        if self.records_df.empty:
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            return

        self.records_df = self.parse_timestamps(
            self.records_df
        )

        valid_dates = self.records_df.dropna(
            subset=["timestamp"]
        )

        if valid_dates.empty:
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            return

        min_date = valid_dates["timestamp"].min()
        max_date = valid_dates["timestamp"].max()

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

        self.available_range_label.setText(
            f"{self.t('available_data')}: "
            f"{min_date.strftime('%d/%m/%Y %H:%M')} "
            "to "
            f"{max_date.strftime('%d/%m/%Y %H:%M')}"
        )

    def get_metric_config(self):
        """
        Return selected metric config.
        Combo display text may be translated.
        itemData keeps internal value.
        """

        selected_metric = self.metric_filter.currentData()

        metric_config = {
            "Voltage": {
                "column": "voltage_mv",
                "title": self.t("voltage"),
                "axis": "Voltage (mV)",
                "trend_name": f"{self.t('voltage')} trend",
            },
            "Charge": {
                "column": "charge_percent",
                "title": self.t("charge"),
                "axis": "Charge (%)",
                "trend_name": f"{self.t('charge')} trend",
            },
            "Temperature": {
                "column": "temperature_c",
                "title": self.t("temperature"),
                "axis": "Temperature (°C)",
                "trend_name": f"{self.t('temperature')} trend",
            },
            "GPS Quality": {
                "column": "gps_quality",
                "title": self.t("gps_quality"),
                "axis": "GPS Quality (%)",
                "trend_name": f"{self.t('gps_quality')} trend",
            },
        }

        return metric_config.get(
            selected_metric,
            metric_config["Voltage"]
        )
    def render_chart_html(self, html):
        """
        Render Plotly HTML from a temporary file.

        This is more reliable than QWebEngineView.setHtml()
        when the application is packaged as an EXE.
        """

        temp_dir = Path(tempfile.gettempdir()) / "node_health_analyzer"
        temp_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        html_path = temp_dir / f"node_detail_{uuid.uuid4().hex}.html"

        html_path.write_text(
            html,
            encoding="utf-8"
        )

        self.web_view.load(
            QUrl.fromLocalFile(str(html_path))
        )

    def load_metric_chart(self):
        """
        Load and render selected metric chart.
        """

        df = self.records_df.copy()

        if df.empty:
            self.web_view.setHtml("<h3>No records found</h3>")
            return

        metric = self.get_metric_config()
        metric_column = metric["column"]

        df = self.parse_timestamps(df)

        df[metric_column] = pd.to_numeric(
            df[metric_column],
            errors="coerce"
        )

        df = df.dropna(
            subset=["timestamp", metric_column]
        )

        # Charge sometimes reports 0 or invalid values during no acquisition.
        # These points distort battery interpretation.
        if metric_column == "charge_percent":
            df = df[
                (df["charge_percent"] > 0)
                &
                (df["acq_type"] != "No acquisition")
            ]

        # GPS during no acquisition is usually not useful
        # for operational acquisition analysis.
        if metric_column == "gps_quality":
            df = df[
                df["acq_type"] != "No acquisition"
            ]

        df = df.sort_values(
            by="timestamp"
        )

        selected_acq = self.acq_filter.currentData()

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

        df = df[
            (df["timestamp"] >= start_dt)
            &
            (df["timestamp"] < end_dt)
        ]

        if selected_acq != "All":
            df = df[
                df["acq_type"] == selected_acq
            ]

        if df.empty:
            self.web_view.setHtml(
                "<h3>No records for selected filter</h3>"
            )
            return

        fig = go.Figure()

        color_map = {
            "Seismic": "#1f77b4",
            "BIT": "#ff7f0e",
            "No acquisition": "#d62728",
        }

        if selected_acq == "All":
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[metric_column],
                    mode="lines",
                    name=metric["trend_name"],
                    line=dict(
                        color="#444444",
                        width=2
                    )
                )
            )

            for acq_type, color in color_map.items():
                filtered_df = df[
                    df["acq_type"] == acq_type
                ]

                if filtered_df.empty:
                    continue

                fig.add_trace(
                    go.Scatter(
                        x=filtered_df["timestamp"],
                        y=filtered_df[metric_column],
                        mode="markers",
                        name=acq_type,
                        marker=dict(
                            color=color,
                            size=6
                        )
                    )
                )

        else:
            color = color_map.get(
                selected_acq,
                "#1f77b4"
            )

            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[metric_column],
                    mode="lines+markers",
                    name=f"{metric['title']} ({selected_acq})",
                    line=dict(
                        color=color,
                        width=2
                    ),
                    marker=dict(
                        color=color,
                        size=6
                    )
                )
            )

        fig.update_layout(
            title=f"{metric['title']} - {self.t('node')} {self.serial_number}",
            xaxis_title="Time",
            yaxis_title=metric["axis"],
            template="plotly_white",
            legend_title="Data",
        )

        html = fig.to_html(
            include_plotlyjs=True
        )

        self.render_chart_html(html)
        