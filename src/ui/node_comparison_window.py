import re
from pathlib import Path
import tempfile
import uuid

import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import Qt, QDate, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QCheckBox,
    QLineEdit,
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

from src.analysis.battery_life import calculate_battery_insight
from src.database.database import get_records_by_serial, get_record_date_range
from src.translations.language_manager import LanguageManager
from src.ui.node_detail_window import NodeDetailWindow


class NodeComparisonWindow(QMainWindow):
    def __init__(self, nodes):
        super().__init__()

        self.nodes = nodes
        self.last_figure_html = ""
        self.detail_windows = []

        self.setAcceptDrops(True)
        self.setWindowTitle(self.t("node_comparison"))
        self.resize(1200, 800)

        self.setup_ui()

    def t(self, key):
        return LanguageManager.translate(key)

    def tf(self, key, fallback):
        value = self.t(key)
        return fallback if value == key else value

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.node_selector_panel = QWidget()
        node_selector_layout = QVBoxLayout()
        node_selector_layout.setContentsMargins(0, 0, 0, 0)

        self.select_nodes_label = QLabel()
        node_selector_layout.addWidget(self.select_nodes_label)

        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.filter_node_list)
        node_selector_layout.addWidget(self.search_box)

        self.node_list = QListWidget()
        self.node_list.setSelectionMode(QAbstractItemView.NoSelection)

        for node in self.nodes:
            serial_number = node.get("serial_number", "")
            item = QListWidgetItem(serial_number)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Unchecked)
            self.node_list.addItem(item)

        self.node_list.itemChanged.connect(self.on_node_check_changed)
        self.node_list.itemDoubleClicked.connect(self.open_detail_from_item)
        node_selector_layout.addWidget(self.node_list)

        selection_layout = QHBoxLayout()

        self.select_all_button = QPushButton()
        self.select_all_button.clicked.connect(self.select_all_nodes)
        selection_layout.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton()
        self.clear_selection_button.clicked.connect(self.clear_selection)
        selection_layout.addWidget(self.clear_selection_button)

        node_selector_layout.addLayout(selection_layout)

        self.node_selector_panel.setLayout(node_selector_layout)
        layout.addWidget(self.node_selector_panel)

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

        self.metric_label = QLabel()
        filters_layout.addWidget(self.metric_label)

        self.metric_filter = QComboBox()
        self.metric_filter.addItem(self.t("voltage"), "Voltage")
        self.metric_filter.addItem(self.t("charge"), "Charge")
        self.metric_filter.addItem(self.t("temperature"), "Temperature")
        self.metric_filter.addItem(self.t("gps_quality"), "GPS Quality")
        self.metric_filter.currentIndexChanged.connect(self.on_filter_changed)
        filters_layout.addWidget(self.metric_filter)

        self.auto_update_checkbox = QCheckBox()
        self.auto_update_checkbox.setChecked(False)
        filters_layout.addWidget(self.auto_update_checkbox)

        self.compare_button = QPushButton()
        self.compare_button.clicked.connect(self.load_comparison_chart)
        self.compare_button.setVisible(False)
        filters_layout.addWidget(self.compare_button)

        self.export_html_button = QPushButton()
        self.export_html_button.clicked.connect(self.export_chart_html)
        filters_layout.addWidget(self.export_html_button)

        self.filters_panel.setLayout(filters_layout)
        layout.addWidget(self.filters_panel)

        self.summary_panel = QWidget()
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(0, 0, 0, 0)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)

        self.summary_panel.setLayout(summary_layout)
        layout.addWidget(self.summary_panel)

        controls_layout = QHBoxLayout()

        self.show_node_selector_checkbox = QCheckBox()
        self.show_node_selector_checkbox.setChecked(True)
        self.show_node_selector_checkbox.stateChanged.connect(self.update_panel_visibility)
        controls_layout.addWidget(self.show_node_selector_checkbox)

        self.show_filters_checkbox = QCheckBox()
        self.show_filters_checkbox.setChecked(True)
        self.show_filters_checkbox.stateChanged.connect(self.update_panel_visibility)
        controls_layout.addWidget(self.show_filters_checkbox)

        self.show_summary_checkbox = QCheckBox()
        self.show_summary_checkbox.setChecked(True)
        self.show_summary_checkbox.stateChanged.connect(self.update_panel_visibility)
        controls_layout.addWidget(self.show_summary_checkbox)

        self.maximize_chart_button = QPushButton()
        self.maximize_chart_button.clicked.connect(self.toggle_chart_maximized)
        controls_layout.addWidget(self.maximize_chart_button)

        layout.addLayout(controls_layout)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

        central_widget.setLayout(layout)

        self.chart_maximized = False
        self.apply_language()

    def apply_language(self):
        self.setWindowTitle(self.t("node_comparison"))
        self.title_label.setText(self.t("node_comparison"))

        self.info_label.setText(
            f"{self.t('select_nodes')}, {self.t('metric')}, "
            f"{self.t('compare_selected')}"
        )

        self.select_nodes_label.setText(self.t("select_nodes"))
        self.search_box.setPlaceholderText(self.t("search_node"))
        self.select_all_button.setText(self.t("select_all"))
        self.clear_selection_button.setText(self.t("clear_selection"))
        self.start_date_label.setText(self.t("start_date"))
        self.end_date_label.setText(self.t("end_date"))
        self.metric_label.setText(self.t("metric"))
        self.auto_update_checkbox.setText(self.t("sync_date_range"))
        self.compare_button.setText(self.t("compare_selected"))
        self.export_html_button.setText(self.t("export_chart_html"))
        self.show_node_selector_checkbox.setText(self.t("show_node_selector"))
        self.show_filters_checkbox.setText(self.t("show_filters"))
        self.show_summary_checkbox.setText(self.t("show_summary"))
        self.maximize_chart_button.setText(
            self.t("restore_view") if getattr(self, "chart_maximized", False)
            else self.t("maximize_chart")
        )

        self.web_view.setHtml(f"<h3>{self.t('select_nodes')}</h3>")

    def update_panel_visibility(self):
        if getattr(self, "chart_maximized", False):
            self.node_selector_panel.setVisible(False)
            self.filters_panel.setVisible(False)
            self.summary_panel.setVisible(False)
            return

        self.node_selector_panel.setVisible(self.show_node_selector_checkbox.isChecked())
        self.filters_panel.setVisible(self.show_filters_checkbox.isChecked())
        self.summary_panel.setVisible(self.show_summary_checkbox.isChecked())

    def toggle_chart_maximized(self):
        self.chart_maximized = not getattr(self, "chart_maximized", False)

        if self.chart_maximized:
            self.node_selector_panel.setVisible(False)
            self.filters_panel.setVisible(False)
            self.summary_panel.setVisible(False)
            self.show_node_selector_checkbox.setEnabled(False)
            self.show_filters_checkbox.setEnabled(False)
            self.show_summary_checkbox.setEnabled(False)
            self.maximize_chart_button.setText(self.t("restore_view"))
        else:
            self.show_node_selector_checkbox.setEnabled(True)
            self.show_filters_checkbox.setEnabled(True)
            self.show_summary_checkbox.setEnabled(True)
            self.maximize_chart_button.setText(self.t("maximize_chart"))
            self.update_panel_visibility()

    def filter_node_list(self):
        text = self.search_box.text().strip().lower()

        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            item.setHidden(text not in item.text().lower())

    def get_checked_serials(self):
        serials = []

        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            if item.checkState() == Qt.Checked:
                serials.append(item.text())

        return serials

    def on_node_check_changed(self, item):
        self.load_comparison_chart()

    def on_filter_changed(self, *args):
        if self.auto_update_checkbox.isChecked():
            self.sync_detail_windows_date_range()

        if self.get_checked_serials():
            self.load_comparison_chart()

    def sync_detail_windows_date_range(self):
        for window in list(NodeDetailWindow.open_windows):
            try:
                window.set_date_range_from_external(
                    self.start_date.date(),
                    self.end_date.date()
                )
            except Exception:
                pass

    def open_detail_from_item(self, item):
        serial_number = item.text()
        node_data = None

        for node in self.nodes:
            if node.get("serial_number", "") == serial_number:
                node_data = node
                break

        if node_data is None:
            node_data = {"serial_number": serial_number}

        detail_window = NodeDetailWindow(node_data)
        detail_window.show()
        self.detail_windows.append(detail_window)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        serials = self.extract_serials_from_drop(event.mimeData())

        if not serials:
            event.ignore()
            return

        for serial in serials:
            self.select_serial(serial)

        self.load_comparison_chart()
        event.acceptProposedAction()

    def extract_serials_from_drop(self, mime_data):
        candidates = []

        if mime_data.hasText():
            candidates.extend(re.findall(r"\d{5,}", mime_data.text()))

        for fmt in mime_data.formats():
            try:
                raw = bytes(mime_data.data(fmt))
            except Exception:
                continue

            for encoding in ("utf-8", "utf-16", "latin1"):
                try:
                    text = raw.decode(encoding, errors="ignore")
                except Exception:
                    continue

                candidates.extend(re.findall(r"\d{5,}", text))

        known = {node.get("serial_number", "") for node in self.nodes}
        result = []

        for candidate in candidates:
            if candidate in known and candidate not in result:
                result.append(candidate)

        return result

    def select_serial(self, serial_number):
        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            if item.text() == serial_number:
                item.setCheckState(Qt.Checked)
                self.node_list.scrollToItem(item)
                return True

        return False

    def select_all_nodes(self):
        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def clear_selection(self):
        for index in range(self.node_list.count()):
            self.node_list.item(index).setCheckState(Qt.Unchecked)

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
        min_date = None
        max_date = None

        for node in self.nodes:
            serial_number = node.get("serial_number", "")
            node_min, node_max, _ = get_record_date_range(serial_number)

            if not node_min or not node_max:
                continue

            node_min = pd.to_datetime(node_min, errors="coerce")
            node_max = pd.to_datetime(node_max, errors="coerce")

            if pd.isna(node_min) or pd.isna(node_max):
                continue

            if min_date is None or node_min < min_date:
                min_date = node_min

            if max_date is None or node_max > max_date:
                max_date = node_max

        if min_date is None or max_date is None:
            today = QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            return

        min_qdate = QDate(min_date.year, min_date.month, min_date.day)
        max_qdate = QDate(max_date.year, max_date.month, max_date.day)

        self.start_date.setMinimumDate(min_qdate)
        self.start_date.setMaximumDate(max_qdate)
        self.end_date.setMinimumDate(min_qdate)
        self.end_date.setMaximumDate(max_qdate)

        self.start_date.setDate(min_qdate)
        self.end_date.setDate(max_qdate)

    def get_metric_config(self):
        selected_metric = self.metric_filter.currentData()

        metric_config = {
            "Voltage": {
                "column": "voltage_mv",
                "title": self.tf("voltage_comparison", "Voltage Comparison"),
                "axis": f"{self.t('voltage')} (mV)",
            },
            "Charge": {
                "column": "charge_percent",
                "title": self.tf("charge_comparison", "Charge Comparison"),
                "axis": f"{self.t('charge')} (%)",
            },
            "Temperature": {
                "column": "temperature_c",
                "title": self.tf("temperature_comparison", "Temperature Comparison"),
                "axis": f"{self.t('temperature')} (°C)",
            },
            "GPS Quality": {
                "column": "gps_quality",
                "title": self.tf("gps_comparison", "GPS Quality Comparison"),
                "axis": f"{self.t('gps_quality')} (%)",
            },
        }

        return metric_config.get(selected_metric, metric_config["Voltage"])

    def format_remaining_days(self, value):
        if value is None or pd.isna(value):
            return self.t("not_available")

        return f"{value:.0f} {self.t('days')}"

    def get_priority_key(self, remaining_days, recommendation_key):
        if remaining_days is None or pd.isna(remaining_days):
            return "review"

        if recommendation_key == "recommendation_prediction_not_reliable":
            return "review"

        if remaining_days <= 30:
            return "immediate"

        if remaining_days <= 90:
            return "plan"

        return "monitor"

    def insert_breaks_on_large_jumps(self, df, metric_column, jump_limit=200):
        if metric_column != "voltage_mv":
            return df

        df = df.copy()
        df["voltage_jump"] = df["voltage_mv"].diff().abs()

        rows = []

        for _, row in df.iterrows():
            if (
                pd.notna(row.get("voltage_jump"))
                and row.get("voltage_jump") > jump_limit
            ):
                empty_row = row.copy()
                empty_row[metric_column] = None
                rows.append(empty_row)

            rows.append(row)

        return pd.DataFrame(rows)

    def build_hover_template(self):
        return (
            f"<b>{self.t('node')}:</b> %{{customdata[0]}}<br>"
            f"<b>{self.tf('date', 'Date')}:</b> %{{x}}<br>"
            f"<b>{self.t('voltage')}:</b> %{{customdata[1]}} mV<br>"
            f"<b>{self.t('charge')}:</b> %{{customdata[2]}} %<br>"
            f"<b>GPS:</b> %{{customdata[3]}} %<br>"
            f"<b>{self.t('temperature')}:</b> %{{customdata[4]}} °C<br>"
            f"<b>{self.tf('mode', 'Mode')}:</b> %{{customdata[5]}}<br>"
            f"<b>{self.t('battery_health')}:</b> %{{customdata[6]}} %<br>"
            f"<b>{self.t('slope')}:</b> %{{customdata[7]}} mV/day<br>"
            f"<b>{self.t('remaining_life')}:</b> %{{customdata[8]}}<br>"
            f"<b>{self.t('confidence')}:</b> %{{customdata[9]}}<br>"
            "<extra></extra>"
        )

    def get_customdata(
        self,
        df,
        serial_number,
        battery_health=None,
        slope=None,
        remaining_days=None,
        confidence=None,
    ):
        df = df.copy()

        required_columns = [
            "voltage_mv",
            "charge_percent",
            "gps_quality",
            "temperature_c",
            "acq_type",
        ]

        for column in required_columns:
            if column not in df.columns:
                df[column] = ""

        df["serial_number"] = serial_number

        df["battery_health"] = (
            ""
            if battery_health is None or pd.isna(battery_health)
            else f"{battery_health:.0f}"
        )

        df["slope"] = (
            ""
            if slope is None or pd.isna(slope)
            else f"{slope:.2f}"
        )

        df["remaining"] = (
            self.t("not_available")
            if remaining_days is None or pd.isna(remaining_days)
            else f"{remaining_days:.0f} {self.t('days')}"
        )

        df["confidence"] = str(confidence)

        return df[
            [
                "serial_number",
                "voltage_mv",
                "charge_percent",
                "gps_quality",
                "temperature_c",
                "acq_type",
                "battery_health",
                "slope",
                "remaining",
                "confidence",
            ]
        ]

    def render_chart_html(self, html):
        temp_dir = Path(tempfile.gettempdir()) / "node_health_analyzer"
        temp_dir.mkdir(parents=True, exist_ok=True)

        html_path = temp_dir / f"node_comparison_{uuid.uuid4().hex}.html"
        html_path.write_text(html, encoding="utf-8")

        self.web_view.load(QUrl.fromLocalFile(str(html_path)))

    def build_summary_html(self, summary_rows):
        if not summary_rows:
            self.summary_label.setText("")
            return

        html = f"""
        <table border="1" cellspacing="0" cellpadding="4">
            <tr>
                <th>{self.t('node')}</th>
                <th>{self.t('battery_health')}</th>
                <th>{self.t('slope')}</th>
                <th>{self.t('remaining_life')}</th>
                <th>{self.t('confidence')}</th>
                <th>{self.t('priority')}</th>
                <th>{self.t('recommendation')}</th>
            </tr>
        """

        for row in summary_rows:
            html += f"""
            <tr>
                <td>{row["serial"]}</td>
                <td>{row["battery_health"]}</td>
                <td>{row["slope"]}</td>
                <td>{row["remaining"]}</td>
                <td>{row["confidence"]}</td>
                <td>{row["priority"]}</td>
                <td>{row["recommendation"]}</td>
            </tr>
            """

        html += "</table><br>"
        self.summary_label.setText(html)

    def load_comparison_chart(self):
        selected_serials = self.get_checked_serials()

        if not selected_serials:
            self.web_view.setHtml(f"<h3>{self.t('select_nodes')}</h3>")
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
        ) + pd.Timedelta(days=1)

        fig = go.Figure()
        plotted_nodes = 0
        summary_rows = []

        self.info_label.setText(
            f"{self.t('compare_selected')}: "
            + ", ".join(selected_serials)
        )

        hover_template = self.build_hover_template()
        first_insight = None

        for serial_number in selected_serials:
            df = get_records_by_serial(
                serial_number,
                start_time=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            )

            if df.empty:
                continue

            df = self.parse_timestamps(df)

            if metric_column not in df.columns:
                continue

            numeric_columns = [
                "voltage_mv",
                "charge_percent",
                "gps_quality",
                "temperature_c",
                metric_column,
            ]

            for column in numeric_columns:
                if column in df.columns:
                    df[column] = pd.to_numeric(df[column], errors="coerce")

            df = df.dropna(subset=["timestamp", metric_column])

            df = df[
                (df["timestamp"] >= start_dt)
                &
                (df["timestamp"] < end_dt)
            ]

            if metric_column == "charge_percent":
                df = df[
                    (df["charge_percent"] > 0)
                    &
                    (df["acq_type"] != "No acquisition")
                ]

            if metric_column == "gps_quality":
                df = df[df["acq_type"] != "No acquisition"]

            df = df.sort_values(by="timestamp")

            if df.empty:
                continue

            insight = calculate_battery_insight(df)

            if first_insight is None:
                first_insight = insight

            battery_health = insight.get("battery_health")
            slope = insight.get("voltage_slope_mv_day")
            remaining_days = insight.get("remaining_days")
            confidence = insight.get("confidence")
            recommendation_key = insight.get("recommendation")

            battery_health_text = (
                self.t("not_available")
                if battery_health is None or pd.isna(battery_health)
                else f"{battery_health:.0f}%"
            )

            slope_text = (
                self.t("not_available")
                if slope is None or pd.isna(slope)
                else f"{slope:.2f} mV/day"
            )

            remaining_text = self.format_remaining_days(remaining_days)
            confidence_text = self.t(str(confidence).lower())
            recommendation_text = self.t(recommendation_key)

            priority_key = self.get_priority_key(
                remaining_days,
                recommendation_key
            )
            priority_text = self.t(priority_key)

            summary_rows.append({
                "serial": serial_number,
                "battery_health": battery_health_text,
                "slope": slope_text,
                "remaining": remaining_text,
                "confidence": confidence_text,
                "priority_key": priority_key,
                "priority": priority_text,
                "recommendation": recommendation_text,
            })

            trace_name = (
                f"{serial_number} | "
                f"{battery_health_text} | "
                f"{remaining_text}"
            )

            plot_df = self.insert_breaks_on_large_jumps(
                df,
                metric_column
            )

            fig.add_trace(
                go.Scatter(
                    x=plot_df["timestamp"],
                    y=plot_df[metric_column],
                    mode="lines+markers",
                    name=trace_name,
                    customdata=self.get_customdata(
                        plot_df,
                        serial_number,
                        battery_health,
                        slope,
                        remaining_days,
                        confidence_text,
                    ),
                    hovertemplate=hover_template,
                    line=dict(width=2),
                    marker=dict(size=4),
                    connectgaps=False
                )
            )

            plotted_nodes += 1

        if plotted_nodes == 0:
            self.web_view.setHtml(
                f"<h3>{self.tf('no_valid_data', 'No valid data found for selected nodes, metric and date range.')}</h3>"
            )
            self.last_figure_html = ""
            self.summary_label.setText("")
            return

        self.build_summary_html(summary_rows)

        critical_count = sum(
            1 for row in summary_rows if row["priority_key"] == "immediate"
        )
        warning_count = sum(
            1 for row in summary_rows if row["priority_key"] == "plan"
        )
        good_count = sum(
            1 for row in summary_rows
            if row["priority_key"] in ["monitor", "review"]
        )

        self.summary_label.setText(
            self.summary_label.text()
            +
            f"<b>{self.t('trend_summary')}</b><br>"
            f"🔴 {self.t('immediate_action')}: {critical_count}<br>"
            f"🟠 {self.t('plan_replacement')}: {warning_count}<br>"
            f"🟢 {self.t('monitor')}: {good_count}"
        )

        if metric_column == "voltage_mv" and first_insight is not None:
            warning_voltage = first_insight.get("warning_voltage")
            critical_voltage = first_insight.get("critical_voltage")

            fig.add_hline(
                y=warning_voltage,
                line_dash="dot",
                annotation_text=self.t("warning_threshold")
            )

            fig.add_hline(
                y=critical_voltage,
                line_dash="dash",
                annotation_text=self.t("critical_threshold")
            )

        fig.update_layout(
            title=metric["title"],
            xaxis_title=self.t("time"),
            yaxis_title=metric["axis"],
            template="plotly_white",
            legend_title=self.t("data"),
            hovermode="closest",
        )

        html = fig.to_html(include_plotlyjs=True)

        self.last_figure_html = html
        self.render_chart_html(html)

    def export_chart_html(self):
        if not self.last_figure_html:
            QMessageBox.warning(
                self,
                self.t("export_chart_html"),
                self.tf("no_chart_available", "No chart available to export. Generate a comparison first.")
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
                self.tf("chart_exported_successfully", "Comparison chart exported successfully.")
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                self.tf("export_chart_html_error", "Export Chart HTML Error"),
                str(e)
            )