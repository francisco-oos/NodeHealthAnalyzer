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
    QCheckBox,
)

from src.analysis.battery_life import (
    build_voltage_trend_line,
    calculate_battery_insight,
)
from src.database.database import get_records_by_serial, get_record_date_range
from src.translations.language_manager import LanguageManager


class NodeDetailWindow(QMainWindow):
    open_windows = []

    def __init__(self, node_data):
        super().__init__()

        self.node_data = node_data
        self.serial_number = node_data.get("serial_number", "")
        self.records_df = pd.DataFrame()
        self._syncing_dates = False
        NodeDetailWindow.open_windows.append(self)

        self.setWindowTitle(f"{self.t('node')} {self.tf('details', 'Details')} - {self.serial_number}")
        self.resize(1100, 790)

        self.setup_ui()

    def t(self, key):
        return LanguageManager.translate(key)

    def tf(self, key, fallback):
        value = self.t(key)
        return fallback if value == key else value

    def closeEvent(self, event):
        try:
            if self in NodeDetailWindow.open_windows:
                NodeDetailWindow.open_windows.remove(self)
        except Exception:
            pass
        super().closeEvent(event)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.info_panel = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel()
        info_layout.addWidget(self.title_label)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        info_layout.addWidget(self.summary_label)

        self.available_range_label = QLabel()
        self.available_range_label.setWordWrap(True)
        info_layout.addWidget(self.available_range_label)

        self.info_panel.setLayout(info_layout)
        layout.addWidget(self.info_panel)

        self.metrics_panel = QWidget()
        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)

        self.battery_insight_label = QLabel()
        self.battery_insight_label.setWordWrap(True)
        metrics_layout.addWidget(self.battery_insight_label)

        self.trend_summary_label = QLabel()
        self.trend_summary_label.setWordWrap(True)
        metrics_layout.addWidget(self.trend_summary_label)

        self.mode_slopes_label = QLabel()
        self.mode_slopes_label.setWordWrap(True)
        metrics_layout.addWidget(self.mode_slopes_label)

        self.metrics_panel.setLayout(metrics_layout)
        layout.addWidget(self.metrics_panel)

        self.filters_panel = QWidget()
        filters_layout = QVBoxLayout()
        filters_layout.setContentsMargins(0, 0, 0, 0)

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

        self.start_date.dateChanged.connect(self.on_filter_changed)
        self.end_date.dateChanged.connect(self.on_filter_changed)

        date_layout.addWidget(self.start_date_label)
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(self.end_date_label)
        date_layout.addWidget(self.end_date)

        filters_layout.addLayout(date_layout)

        self.metric_filter = QComboBox()
        self.metric_filter.addItem(self.t("voltage"), "Voltage")
        self.metric_filter.addItem(self.t("charge"), "Charge")
        self.metric_filter.addItem(self.t("temperature"), "Temperature")
        self.metric_filter.addItem(self.t("gps_quality"), "GPS Quality")
        self.metric_filter.currentIndexChanged.connect(self.on_filter_changed)
        filters_layout.addWidget(self.metric_filter)

        self.acq_filter = QComboBox()
        self.acq_filter.addItem(self.t("all"), "All")
        self.acq_filter.addItem(self.t("seismic"), "Seismic")
        self.acq_filter.addItem(self.t("bit"), "BIT")
        self.acq_filter.addItem(self.t("no_acquisition"), "No acquisition")
        self.acq_filter.currentIndexChanged.connect(self.on_filter_changed)
        filters_layout.addWidget(self.acq_filter)

        self.advanced_trend_checkbox = QCheckBox()
        self.advanced_trend_checkbox.stateChanged.connect(self.load_metric_chart)
        filters_layout.addWidget(self.advanced_trend_checkbox)

        # Kept for compatibility, but hidden because filters update automatically.
        self.apply_filter_button = QPushButton()
        self.apply_filter_button.clicked.connect(self.load_metric_chart)
        self.apply_filter_button.setVisible(False)
        filters_layout.addWidget(self.apply_filter_button)

        self.filters_panel.setLayout(filters_layout)
        layout.addWidget(self.filters_panel)

        controls_layout = QHBoxLayout()

        self.show_summary_checkbox = QCheckBox()
        self.show_summary_checkbox.setChecked(True)
        self.show_summary_checkbox.stateChanged.connect(self.update_panel_visibility)
        controls_layout.addWidget(self.show_summary_checkbox)

        self.show_metrics_checkbox = QCheckBox()
        self.show_metrics_checkbox.setChecked(True)
        self.show_metrics_checkbox.stateChanged.connect(self.update_panel_visibility)
        controls_layout.addWidget(self.show_metrics_checkbox)

        self.show_filters_checkbox = QCheckBox()
        self.show_filters_checkbox.setChecked(True)
        self.show_filters_checkbox.stateChanged.connect(self.update_panel_visibility)
        controls_layout.addWidget(self.show_filters_checkbox)

        self.maximize_chart_button = QPushButton()
        self.maximize_chart_button.clicked.connect(self.toggle_chart_maximized)
        controls_layout.addWidget(self.maximize_chart_button)

        layout.addLayout(controls_layout)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

        central_widget.setLayout(layout)

        self.chart_maximized = False

        self.apply_language()
        self.load_metric_chart()

    def update_panel_visibility(self):
        if getattr(self, "chart_maximized", False):
            self.info_panel.setVisible(False)
            self.metrics_panel.setVisible(False)
            self.filters_panel.setVisible(False)
            return

        self.info_panel.setVisible(self.show_summary_checkbox.isChecked())
        self.metrics_panel.setVisible(self.show_metrics_checkbox.isChecked())
        self.filters_panel.setVisible(self.show_filters_checkbox.isChecked())

    def toggle_chart_maximized(self):
        self.chart_maximized = not getattr(self, "chart_maximized", False)

        if self.chart_maximized:
            self.info_panel.setVisible(False)
            self.metrics_panel.setVisible(False)
            self.filters_panel.setVisible(False)
            self.show_summary_checkbox.setEnabled(False)
            self.show_metrics_checkbox.setEnabled(False)
            self.show_filters_checkbox.setEnabled(False)
            self.maximize_chart_button.setText(self.t("restore_view"))
        else:
            self.show_summary_checkbox.setEnabled(True)
            self.show_metrics_checkbox.setEnabled(True)
            self.show_filters_checkbox.setEnabled(True)
            self.maximize_chart_button.setText(self.t("maximize_chart"))
            self.update_panel_visibility()

    def apply_language(self):
        self.setWindowTitle(f"{self.t('node')} {self.tf('details', 'Details')} - {self.serial_number}")

        self.title_label.setText(f"{self.t('node')}: {self.serial_number}")

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

        self.advanced_trend_checkbox.setText(
            self.t("show_advanced_trend_info")
            if self.t("show_advanced_trend_info") != "show_advanced_trend_info"
            else "Show advanced trend info"
        )

        self.show_summary_checkbox.setText(self.t("show_summary"))
        self.show_metrics_checkbox.setText(self.t("show_metrics"))
        self.show_filters_checkbox.setText(self.t("show_filters"))
        self.maximize_chart_button.setText(
            self.t("restore_view") if getattr(self, "chart_maximized", False)
            else self.t("maximize_chart")
        )

    def on_filter_changed(self, *args):
        """
        Update the chart automatically when the user changes date, metric,
        or acquisition type. This replaces the need for the visible
        'Apply Filter' button.
        """
        if getattr(self, "_syncing_dates", False):
            return

        self.load_metric_chart()

    def set_date_range_from_external(self, start_qdate, end_qdate):
        """
        Helper for future synchronized date ranges between windows.
        It is safe even if synchronization is not used.
        """
        self._syncing_dates = True
        try:
            self.start_date.setDate(start_qdate)
            self.end_date.setDate(end_qdate)
        finally:
            self._syncing_dates = False

        self.load_metric_chart()

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
        min_timestamp, max_timestamp, record_count = get_record_date_range(self.serial_number)

        if not min_timestamp or not max_timestamp:
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            self.available_range_label.setText(self.t("no_records_found"))
            return

        min_date = pd.to_datetime(min_timestamp, errors="coerce")
        max_date = pd.to_datetime(max_timestamp, errors="coerce")

        if pd.isna(min_date) or pd.isna(max_date):
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            self.available_range_label.setText(self.t("no_records_found"))
            return

        min_qdate = QDate(min_date.year, min_date.month, min_date.day)
        max_qdate = QDate(max_date.year, max_date.month, max_date.day)

        self.start_date.setMinimumDate(min_qdate)
        self.start_date.setMaximumDate(max_qdate)
        self.end_date.setMinimumDate(min_qdate)
        self.end_date.setMaximumDate(max_qdate)

        self.start_date.setDate(min_qdate)
        self.end_date.setDate(max_qdate)

        self.available_range_label.setText(
            f"{self.t('available_data')}: "
            f"{min_date.strftime('%d/%m/%Y %H:%M')} "
            f"{self.t('to')} "
            f"{max_date.strftime('%d/%m/%Y %H:%M')} | "
            f"{self.t('records')}: {record_count}"
        )

    def get_metric_config(self):
        selected_metric = self.metric_filter.currentData()

        metric_config = {
            "Voltage": {
                "column": "voltage_mv",
                "title": self.t("voltage"),
                "axis": f"{self.t('voltage')} (mV)",
                "trend_name": f"{self.t('voltage')} real",
            },
            "Charge": {
                "column": "charge_percent",
                "title": self.t("charge"),
                "axis": f"{self.t('charge')} (%)",
                "trend_name": f"{self.t('charge')} real",
            },
            "Temperature": {
                "column": "temperature_c",
                "title": self.t("temperature"),
                "axis": f"{self.t('temperature')} (°C)",
                "trend_name": f"{self.t('temperature')} real",
            },
            "GPS Quality": {
                "column": "gps_quality",
                "title": self.t("gps_quality"),
                "axis": f"{self.t('gps_quality')} (%)",
                "trend_name": f"{self.t('gps_quality')} real",
            },
        }

        return metric_config.get(selected_metric, metric_config["Voltage"])

    def format_number(self, value, decimals=2):
        if value is None or pd.isna(value):
            return self.t("not_available")
        return f"{value:.{decimals}f}"

    def get_trend_status(self, slope):
        if slope is None or pd.isna(slope):
            return "unknown", self.t("not_available")

        if slope > 0:
            return "indeterminate", f"⚪ {self.t('indeterminate')}"

        if slope >= -0.5:
            return "stable", f"🔵 {self.t('stable')}"

        if slope >= -2:
            return "slow", f"🟢 {self.t('slow')}"

        if slope >= -10:
            return "moderate", f"🟠 {self.t('moderate')}"

        if slope >= -20:
            return "fast", f"🟠 {self.t('fast')}"

        return "critical", f"🔴 {self.t('critical')}"

    def update_battery_insight(self, df):
        insight = calculate_battery_insight(df)

        voltage_slope = insight.get("voltage_slope_mv_day")
        charge_slope = insight.get("charge_slope_percent_day")
        remaining_days = insight.get("remaining_days")
        replacement_date = insight.get("replacement_date")
        battery_health = insight.get("battery_health")
        battery_condition = insight.get("battery_condition")
        battery_stability = insight.get("battery_stability")
        confidence = insight.get("confidence")

        health_text = self.format_number(battery_health, decimals=0)

        if remaining_days is None:
            remaining_text = self.t("not_available")
        else:
            remaining_text = f"{remaining_days:.0f} {self.t('days')}"

        confidence_text = self.t(str(confidence).lower())

        self.battery_insight_label.setText(
            f"{self.t('battery_insight')} | "
            f"{self.t('battery_health')}: {health_text}% | "
            f"{self.t('battery_condition')}: {self.t(str(battery_condition).lower())} | "
            f"{self.t('discharge_rate')}: {self.format_number(voltage_slope)} mV/day | "
            f"{self.t('charge_drop_rate')}: {self.format_number(charge_slope)} %/day | "
            f"{self.t('remaining_life')}: {remaining_text} | "
            f"{self.t('replacement_date')}: {replacement_date or self.t('not_available')} | "
            f"{self.t('battery_stability')}: {self.t(str(battery_stability).lower())} | "
            f"{self.t('prediction_confidence')}: {confidence_text}"
        )

        _, trend_text = self.get_trend_status(voltage_slope)

        self.trend_summary_label.setText(
            f"<b>{self.t('trend_summary')}</b> | "
            f"{trend_text} | "
            f"{self.t('slope')}: {self.format_number(voltage_slope)} mV/day | "
            f"{self.t('confidence')}: {confidence_text} | "
            f"{self.t('replacement_date')}: {replacement_date or self.t('not_available')}"
        )

        mode_slopes = insight.get("mode_slopes", {})

        self.mode_slopes_label.setText(
            f"{self.t('consumption_by_mode')} | "
            f"{self.t('seismic')}: {self.format_number(mode_slopes.get('Seismic'))} mV/day | "
            f"{self.t('bit')}: {self.format_number(mode_slopes.get('BIT'))} mV/day | "
            f"{self.t('no_acquisition')}: {self.format_number(mode_slopes.get('No acquisition'))} mV/day"
        )

        return insight

    def render_chart_html(self, html):
        temp_dir = Path(tempfile.gettempdir()) / "node_health_analyzer"
        temp_dir.mkdir(parents=True, exist_ok=True)

        html_path = temp_dir / f"node_detail_{uuid.uuid4().hex}.html"
        html_path.write_text(html, encoding="utf-8")

        self.web_view.load(QUrl.fromLocalFile(str(html_path)))

    def translate_acq_type(self, acq_type):
        mapping = {
            "All": self.t("all"),
            "Seismic": self.t("seismic"),
            "BIT": self.t("bit"),
            "No acquisition": self.t("no_acquisition"),
        }
        return mapping.get(acq_type, acq_type)

    def build_hover_template(self):
        return (
            f"<b>{self.t('node')}:</b> {self.serial_number}<br>"
            f"<b>{self.t('date')}:</b> %{{x}}<br>"
            f"<b>{self.t('voltage')}:</b> %{{customdata[0]}} mV<br>"
            f"<b>{self.t('charge')}:</b> %{{customdata[1]}} %<br>"
            f"<b>GPS:</b> %{{customdata[2]}} %<br>"
            f"<b>{self.t('temperature')}:</b> %{{customdata[3]}} °C<br>"
            f"<b>{self.t('mode')}:</b> %{{customdata[4]}}<br>"
            "<extra></extra>"
        )

    def get_customdata_columns(self, df):
        required_columns = [
            "voltage_mv",
            "charge_percent",
            "gps_quality",
            "temperature_c",
            "acq_type",
        ]

        df = df.copy()

        for column in required_columns:
            if column not in df.columns:
                df[column] = ""

        return df[required_columns]

    def build_trend_hover_template(self, insight):
        slope = insight.get("voltage_slope_mv_day")
        remaining_days = insight.get("remaining_days")
        replacement_date = insight.get("replacement_date")
        confidence = insight.get("confidence")

        _, trend_text = self.get_trend_status(slope)

        if remaining_days is None:
            remaining_text = self.t("not_available")
        else:
            remaining_text = f"{remaining_days:.0f} {self.t('days')}"

        return (
            f"<b>{self.t('voltage_trend')}</b><br>"
            f"{self.t('trend')}: {trend_text}<br>"
            f"{self.t('slope')}: {self.format_number(slope)} mV/day<br>"
            f"{self.t('confidence')}: {self.t(str(confidence).lower())}<br>"
            f"{self.t('remaining_life')}: {remaining_text}<br>"
            f"{self.t('replacement_date')}: {replacement_date or self.t('not_available')}<br>"
            f"{self.t('estimated_voltage')}: %{{y:.0f}} mV<br>"
            f"{self.t('date')}: %{{x}}<br>"
            "<extra></extra>"
        )

    def load_metric_chart(self):
        start_dt = pd.to_datetime(
            self.start_date.date().toString("dd/MM/yyyy"),
            format="%d/%m/%Y",
            errors="coerce"
        )

        end_dt = pd.to_datetime(
            self.end_date.date().toString("dd/MM/yyyy"),
            format="%d/%m/%Y",
            errors="coerce"
        ) + pd.Timedelta(days=1)

        df = get_records_by_serial(
            self.serial_number,
            start_time=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        )

        if df.empty:
            self.web_view.setHtml(f"<h3>{self.t('no_records_found')}</h3>")
            return

        df = self.parse_timestamps(df)

        metric = self.get_metric_config()
        metric_column = metric["column"]

        df[metric_column] = pd.to_numeric(df[metric_column], errors="coerce")

        for column in [
            "voltage_mv",
            "charge_percent",
            "gps_quality",
            "temperature_c",
        ]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.dropna(subset=["timestamp", metric_column])

        if metric_column == "charge_percent":
            df = df[
                (df["charge_percent"] > 0)
                &
                (df["acq_type"] != "No acquisition")
            ]

        if metric_column == "gps_quality":
            df = df[df["acq_type"] != "No acquisition"]

        df = df.sort_values(by="timestamp")

        selected_acq = self.acq_filter.currentData()

        if selected_acq != "All":
            df = df[df["acq_type"] == selected_acq]

        if df.empty:
            self.web_view.setHtml(f"<h3>{self.t('no_records_for_filter')}</h3>")
            return

        insight = self.update_battery_insight(df)

        fig = go.Figure()

        color_map = {
            "Seismic": "#1f77b4",
            "BIT": "#ff7f0e",
            "No acquisition": "#d62728",
        }

        hover_template = self.build_hover_template()

        if selected_acq == "All":
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[metric_column],
                    mode="lines",
                    name=metric["trend_name"],
                    line=dict(color="#444444", width=2),
                    hoverinfo="skip"
                )
            )

            for acq_type, color in color_map.items():
                filtered_df = df[df["acq_type"] == acq_type]

                if filtered_df.empty:
                    continue

                fig.add_trace(
                    go.Scatter(
                        x=filtered_df["timestamp"],
                        y=filtered_df[metric_column],
                        mode="markers",
                        name=self.translate_acq_type(acq_type),
                        customdata=self.get_customdata_columns(filtered_df),
                        hovertemplate=hover_template,
                        marker=dict(color=color, size=6)
                    )
                )
        else:
            color = color_map.get(selected_acq, "#1f77b4")

            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[metric_column],
                    mode="lines+markers",
                    name=f"{metric['title']} ({self.translate_acq_type(selected_acq)})",
                    customdata=self.get_customdata_columns(df),
                    hovertemplate=hover_template,
                    line=dict(color=color, width=2),
                    marker=dict(color=color, size=6)
                )
            )

        if metric_column == "voltage_mv":
            analysis_df = insight.get("analysis_df")
            slope = insight.get("voltage_slope_mv_day")
            intercept = insight.get("voltage_intercept")
            start_time = insight.get("voltage_start_time")

            trend_df = build_voltage_trend_line(
                analysis_df,
                slope,
                intercept,
                start_time
            )

            if trend_df is not None:
                if self.advanced_trend_checkbox.isChecked():
                    trend_hover = self.build_trend_hover_template(insight)
                else:
                    trend_hover = None

                fig.add_trace(
                    go.Scatter(
                        x=trend_df["timestamp"],
                        y=trend_df["trend_voltage"],
                        mode="lines",
                        name=self.t("voltage_trend"),
                        line=dict(dash="dash", width=3),
                        hovertemplate=trend_hover,
                        hoverinfo=None if trend_hover else "skip"
                    )
                )

            fig.add_hline(
                y=insight.get("warning_voltage"),
                line_dash="dot",
                annotation_text=self.t("warning_threshold")
            )

            fig.add_hline(
                y=insight.get("critical_voltage"),
                line_dash="dash",
                annotation_text=self.t("critical_threshold")
            )

            replacement_timestamp = insight.get("replacement_timestamp")

            if replacement_timestamp is not None:
                critical_voltage = insight.get("critical_voltage")
                replacement_label_y = critical_voltage - 80

                fig.add_trace(
                    go.Scatter(
                        x=[replacement_timestamp],
                        y=[replacement_label_y],
                        mode="markers+text",
                        name=self.t("estimated_replacement"),
                        text=[self.t("estimated_replacement")],
                        textposition="bottom center",
                        marker=dict(size=12, symbol="x"),
                        hovertemplate=(
                            f"<b>{self.t('estimated_replacement')}</b><br>"
                            f"{self.t('date')}: %{{x}}<br>"
                            f"{self.t('critical_threshold')}: "
                            f"{critical_voltage} mV<br>"
                            "<extra></extra>"
                        )
                    )
                )

        fig.update_layout(
            title=f"{metric['title']} - {self.t('node')} {self.serial_number}",
            xaxis_title=self.t("time"),
            yaxis_title=metric["axis"],
            template="plotly_white",
            legend_title=self.t("data"),
            hovermode="closest",
        )

        html = fig.to_html(include_plotlyjs=True)
        self.render_chart_html(html)