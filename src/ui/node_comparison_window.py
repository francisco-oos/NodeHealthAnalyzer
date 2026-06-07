from pathlib import Path
import tempfile
import uuid

import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QDate, QUrl
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

from src.analysis.battery_life import calculate_battery_insight
from src.database.database import get_records_by_serial
from src.translations.language_manager import LanguageManager


class NodeComparisonWindow(QMainWindow):
    """
    Multi-node comparison window.

    V1.1:
    - Summary table.
    - Clear tooltip.
    - Warning / critical thresholds.
    - Breaks voltage lines on large jumps.
    - Priority column for decision making.
    """

    def __init__(self, nodes):
        super().__init__()

        self.nodes = nodes
        self.last_figure_html = ""

        self.setWindowTitle(self.t("node_comparison"))
        self.resize(1200, 800)

        self.setup_ui()

    def t(self, key):
        return LanguageManager.translate(key)

    def setup_ui(self):
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
        self.node_list.setSelectionMode(QAbstractItemView.MultiSelection)

        for node in self.nodes:
            serial_number = node.get("serial_number", "")
            self.node_list.addItem(QListWidgetItem(serial_number))

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
        self.compare_button.clicked.connect(self.load_comparison_chart)
        layout.addWidget(self.compare_button)

        self.export_html_button = QPushButton()
        self.export_html_button.clicked.connect(self.export_chart_html)
        layout.addWidget(self.export_html_button)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        central_widget.setLayout(layout)

        self.apply_language()

    def apply_language(self):
        self.setWindowTitle(self.t("node_comparison"))
        self.title_label.setText(self.t("node_comparison"))

        self.info_label.setText(
            f"{self.t('select_nodes')}, {self.t('metric')}, "
            f"{self.t('compare_selected')}"
        )

        self.select_nodes_label.setText(self.t("select_nodes"))
        self.select_all_button.setText(self.t("select_all"))
        self.clear_selection_button.setText(self.t("clear_selection"))
        self.start_date_label.setText(self.t("start_date"))
        self.end_date_label.setText(self.t("end_date"))
        self.metric_label.setText(self.t("metric"))
        self.compare_button.setText(self.t("compare_selected"))
        self.export_html_button.setText(self.t("export_chart_html"))

        self.web_view.setHtml(f"<h3>{self.t('select_nodes')}</h3>")

    def select_all_nodes(self):
        for index in range(self.node_list.count()):
            self.node_list.item(index).setSelected(True)

    def clear_selection(self):
        self.node_list.clearSelection()

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

        return metric_config.get(selected_metric, metric_config["Voltage"])

    def format_remaining_days(self, value):
        if value is None or pd.isna(value):
            return self.t("not_available")

        return f"{value:.0f} {self.t('days')}"

    def get_priority(self, remaining_days, recommendation_key):
        """
        Operational priority for comparison summary.
        """

        if remaining_days is None or pd.isna(remaining_days):
            return "Review"

        if remaining_days <= 30:
            return "Immediate"

        if remaining_days <= 90:
            return "Plan"

        if recommendation_key == "recommendation_prediction_not_reliable":
            return "Review"

        return "Monitor"

    def insert_breaks_on_large_jumps(self, df, metric_column, jump_limit=200):
        """
        Break chart lines when voltage jumps are too large.

        This prevents recharge / battery replacement jumps from being
        displayed as normal continuous discharge.
        """

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
            "<b>Nodo:</b> %{customdata[0]}<br>"
            "<b>Fecha:</b> %{x}<br>"
            "<b>Valor:</b> %{y}<br>"
            "<b>Voltaje:</b> %{customdata[1]} mV<br>"
            "<b>Carga:</b> %{customdata[2]} %<br>"
            "<b>GPS:</b> %{customdata[3]} %<br>"
            "<b>Temperatura:</b> %{customdata[4]} °C<br>"
            "<b>Modo:</b> %{customdata[5]}<br>"
            "<extra></extra>"
        )

    def get_customdata(self, df, serial_number):
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

        df["serial_number"] = serial_number

        return df[
            [
                "serial_number",
                "voltage_mv",
                "charge_percent",
                "gps_quality",
                "temperature_c",
                "acq_type",
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

        html = """
        <table border="1" cellspacing="0" cellpadding="4">
            <tr>
                <th>Nodo</th>
                <th>Salud batería</th>
                <th>Pendiente</th>
                <th>Vida restante</th>
                <th>Confianza</th>
                <th>Prioridad</th>
                <th>Recomendación</th>
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

        html += "</table>"
        self.summary_label.setText(html)

    def load_comparison_chart(self):
        selected_items = self.node_list.selectedItems()

        if not selected_items:
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

        selected_serials = [item.text() for item in selected_items]

        self.info_label.setText(
            f"{self.t('compare_selected')}: "
            + ", ".join(selected_serials)
        )

        hover_template = self.build_hover_template()
        first_insight = None

        for serial_number in selected_serials:
            df = get_records_by_serial(serial_number)

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

            priority = self.get_priority(
                remaining_days,
                recommendation_key
            )

            summary_rows.append({
                "serial": serial_number,
                "battery_health": battery_health_text,
                "slope": slope_text,
                "remaining": remaining_text,
                "confidence": confidence_text,
                "priority": priority,
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
                    customdata=self.get_customdata(plot_df, serial_number),
                    hovertemplate=hover_template,
                    line=dict(width=2),
                    marker=dict(size=4),
                    connectgaps=False
                )
            )

            plotted_nodes += 1

        if plotted_nodes == 0:
            self.web_view.setHtml(
                "<h3>No valid data found for selected nodes, metric and date range.</h3>"
            )
            self.last_figure_html = ""
            self.summary_label.setText("")
            return

        self.build_summary_html(summary_rows)

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
            xaxis_title="Time",
            yaxis_title=metric["axis"],
            template="plotly_white",
            legend_title=self.t("node"),
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