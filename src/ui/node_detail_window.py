import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QDate
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


class NodeDetailWindow(QMainWindow):

    def __init__(self, node_data):
        super().__init__()

        self.node_data = node_data
        self.serial_number = node_data.get("serial_number", "")

        self.records_df = get_records_by_serial(self.serial_number)

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

        self.available_range_label = QLabel("Available Data: -")
        layout.addWidget(self.available_range_label)

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

        self.acq_filter = QComboBox()
        self.acq_filter.addItems(
            [
                "All",
                "Seismic",
                "BIT",
                "No acquisition",
            ]
        )
        layout.addWidget(self.acq_filter)

        self.apply_filter_button = QPushButton("Apply Filter")
        self.apply_filter_button.clicked.connect(
            self.load_voltage_chart
        )
        layout.addWidget(self.apply_filter_button)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        central_widget.setLayout(layout)

        self.load_voltage_chart()

    def parse_timestamps(self, df):
        df = df.copy()

        if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            return df

        raw_timestamp = df["timestamp"].astype(str).str.strip()

        # 1) Formato Sercel con segundos: 05/03/2026 22:19:30
        parsed = pd.to_datetime(
            raw_timestamp,
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce"
        )

        # 2) Formato Sercel sin segundos: 05/03/2026 22:19
        missing_mask = parsed.isna()

        if missing_mask.any():
            parsed_no_seconds = pd.to_datetime(
                raw_timestamp[missing_mask],
                format="%d/%m/%Y %H:%M",
                errors="coerce"
            )

            parsed.loc[missing_mask] = parsed_no_seconds

        # 3) Formato ISO/Pandas: 2026-03-05 22:19:00
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
        if self.records_df.empty:
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            self.available_range_label.setText(
                "Available Data: no records found"
            )
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
            self.available_range_label.setText(
                "Available Data: no valid dates found"
            )
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
            "Available Data: "
            f"{min_date.strftime('%d/%m/%Y %H:%M')} "
            "to "
            f"{max_date.strftime('%d/%m/%Y %H:%M')}"
        )

    def load_voltage_chart(self):
        df = self.records_df.copy()

        if df.empty:
            self.web_view.setHtml("<h3>No records found</h3>")
            return

        df = self.parse_timestamps(df)

        df = df.dropna(
            subset=["timestamp", "voltage_mv"]
        )

        df = df.sort_values(
            by="timestamp"
        )

        selected_acq = self.acq_filter.currentText()

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
            df = df[df["acq_type"] == selected_acq]

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
                    y=df["voltage_mv"],
                    mode="lines",
                    name="Voltage trend",
                    line=dict(
                        color="#444444",
                        width=2
                    )
                )
            )

            for acq_type, color in color_map.items():
                filtered_df = df[df["acq_type"] == acq_type]

                if filtered_df.empty:
                    continue

                fig.add_trace(
                    go.Scatter(
                        x=filtered_df["timestamp"],
                        y=filtered_df["voltage_mv"],
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
                    y=df["voltage_mv"],
                    mode="lines+markers",
                    name=f"Voltage ({selected_acq})",
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
            title=f"Voltage History - Node {self.serial_number}",
            xaxis_title="Time",
            yaxis_title="Voltage (mV)",
            template="plotly_white",
            legend_title="Acq Type",
        )

        html = fig.to_html(
            include_plotlyjs="cdn"
        )

        self.web_view.setHtml(html)