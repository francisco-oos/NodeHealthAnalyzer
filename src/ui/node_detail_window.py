from pathlib import Path
import tempfile
import uuid

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

from src.analysis.battery_life import (
    CRITICAL_VOLTAGE_MV,
    WARNING_VOLTAGE_MV,
    build_voltage_trend_line,
    calculate_battery_insight,
)
from src.database.database import get_records_by_serial
from src.translations.language_manager import LanguageManager


class NodeDetailWindow(QMainWindow):
    """
    Node detail window with Battery Intelligence.

    Important:
    - Raw CSV/database values are not translated.
    - Only visible UI labels are translated.
    - Battery prediction is simple V1.1 logic, not ML yet.
    """

    def __init__(self, node_data):
        super().__init__()

        self.node_data = node_data
        self.serial_number = node_data.get("serial_number", "")

        self.records_df = get_records_by_serial(
            self.serial_number
        )

        self.setWindowTitle(
            f"{self.t('node')} Details - {self.serial_number}"
        )

        self.resize(1100, 760)

        self.setup_ui()

    def t(self, key):
        return LanguageManager.translate(key)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        self.battery_insight_label = QLabel()
        self.battery_insight_label.setWordWrap(True)
        layout.addWidget(self.battery_insight_label)

        self.mode_slopes_label = QLabel()
        self.mode_slopes_label.setWordWrap(True)
        layout.addWidget(self.mode_slopes_label)

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
        self.acq_filter.addItem(
            self.t("no_acquisition"),
            "No acquisition"
        )
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

        self.start_date_label.setText(
            self.t("start_date")
        )

        self.end_date_label.setText(
            self.t("end_date")
        )

        self.apply_filter_button.setText(
            self.t("apply_filter")
        )

    def parse_timestamps(self, df):
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
        selected_metric = self.metric_filter.currentData()

        metric_config = {
            "Voltage": {
                "column": "voltage_mv",
                "title": self.t("voltage"),
                "axis": "Voltage (mV)",
                "trend_name": f"{self.t('voltage')} real",
            },
            "Charge": {
                "column": "charge_percent",
                "title": self.t("charge"),
                "axis": "Charge (%)",
                "trend_name": f"{self.t('charge')} real",
            },
            "Temperature": {
                "column": "temperature_c",
                "title": self.t("temperature"),
                "axis": "Temperature (°C)",
                "trend_name": f"{self.t('temperature')} real",
            },
            "GPS Quality": {
                "column": "gps_quality",
                "title": self.t("gps_quality"),
                "axis": "GPS Quality (%)",
                "trend_name": f"{self.t('gps_quality')} real",
            },
        }

        return metric_config.get(
            selected_metric,
            metric_config["Voltage"]
        )

    def format_number(self, value, decimals=2):
        if value is None or pd.isna(value):
            return "N/A"

        return f"{value:.{decimals}f}"

    def update_battery_insight(self, df):
        """
        Display Battery Intelligence summary.

        Equivalent cycles are estimated from accumulated charge drop,
        similar in concept to iPhone battery cycles, but based only on
        available CSV percentage data.
        """

        insight = calculate_battery_insight(df)

        voltage_slope = insight.get("voltage_slope_mv_day")
        charge_slope = insight.get("charge_slope_percent_day")
        remaining_days = insight.get("remaining_days")
        replacement_date = insight.get("replacement_date")
        battery_health = insight.get("battery_health")
        battery_condition = insight.get("battery_condition")
        battery_stability = insight.get("battery_stability")
        confidence = insight.get("confidence")

        if remaining_days is None:
            remaining_text = "N/A"
        else:
            remaining_text = f"{remaining_days:.0f} days"

        health_text = self.format_number(
            battery_health,
            decimals=0
        )

        if remaining_days is None:
            remaining_text = self.t("not_available")
        else:
            remaining_text = f"{remaining_days:.0f} {self.t('days')}"

        self.battery_insight_label.setText(
            f"{self.t('battery_insight')} | "
            f"{self.t('battery_health')}: {health_text}% | "
            f"{self.t('battery_condition')}: {battery_condition} | "
            f"{self.t('discharge_rate')}: {self.format_number(voltage_slope)} mV/day | "
            f"{self.t('charge_drop_rate')}: {self.format_number(charge_slope)} %/day | "
            f"{self.t('remaining_life')}: {remaining_text} | "
            f"{self.t('replacement_date')}: {replacement_date or self.t('not_available')} | "
            f"{self.t('battery_stability')}: {battery_stability} | "
            f"{self.t('confidence')}: {confidence}"
        )

        mode_slopes = insight.get("mode_slopes", {})

        seismic = mode_slopes.get("Seismic")
        bit = mode_slopes.get("BIT")
        no_acq = mode_slopes.get("No acquisition")

        self.mode_slopes_label.setText(
            "Consumption by mode | "
            f"Seismic: {self.format_number(seismic)} mV/day | "
            f"BIT: {self.format_number(bit)} mV/day | "
            f"No acquisition: {self.format_number(no_acq)} mV/day"
        )

        return insight

    def render_chart_html(self, html):
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
        df = self.records_df.copy()

        if df.empty:
            self.web_view.setHtml("<h3>No records found</h3>")
            return

        df = self.parse_timestamps(df)

        metric = self.get_metric_config()
        metric_column = metric["column"]

        df[metric_column] = pd.to_numeric(
            df[metric_column],
            errors="coerce"
        )

        if "voltage_mv" in df.columns:
            df["voltage_mv"] = pd.to_numeric(
                df["voltage_mv"],
                errors="coerce"
            )

        if "charge_percent" in df.columns:
            df["charge_percent"] = pd.to_numeric(
                df["charge_percent"],
                errors="coerce"
            )

        df = df.dropna(
            subset=["timestamp", metric_column]
        )

        if metric_column == "charge_percent":
            df = df[
                (df["charge_percent"] > 0)
                &
                (df["acq_type"] != "No acquisition")
            ]

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

        insight = self.update_battery_insight(df)

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

        if metric_column == "voltage_mv":
            latest_cycle_df = insight.get("analysis_df")
            slope = insight.get("voltage_slope_mv_day")
            intercept = insight.get("voltage_intercept")
            start_time = insight.get("voltage_start_time")

            trend_df = build_voltage_trend_line(
                latest_cycle_df,
                slope,
                intercept,
                start_time
            )

            if trend_df is not None:
                fig.add_trace(
                    go.Scatter(
                        x=trend_df["timestamp"],
                        y=trend_df["trend_voltage"],
                        mode="lines",
                        name=self.t("voltage_trend"),
                        line=dict(
                            dash="dash",
                            width=3
                        )
                    )
                )

            fig.add_hline(
                y=WARNING_VOLTAGE_MV,
                line_dash="dot",
                annotation_text=self.t("warning_threshold")
            )

            fig.add_hline(
                y=CRITICAL_VOLTAGE_MV,
                line_dash="dash",
                annotation_text=self.t("critical_threshold")
            )

            replacement_timestamp = insight.get(
                "replacement_timestamp"
            )

            if replacement_timestamp is not None:
                fig.add_trace(
                    go.Scatter(
                        x=[replacement_timestamp],
                        y=[CRITICAL_VOLTAGE_MV],
                        mode="markers+text",
                        name=self.t("estimated_replacement"),
                        text=[self.t("estimated_replacement")],
                        textposition="top center",
                        marker=dict(
                            size=12,
                            symbol="x"
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