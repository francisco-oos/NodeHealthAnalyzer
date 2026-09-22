from pathlib import Path
import tempfile
import uuid

import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.analysis.battery_field_study import (
    BatteryFieldConfig,
    analyze_field_battery_batch,
    config_from_dict,
    format_optional_datetime,
    format_optional_number,
    load_profiles,
    save_profile,
)
from src.database.database import get_records_by_serial


class BatteryFieldStudyWindow(QMainWindow):
    """
    Independent v1.1 module.

    It does not modify existing health analysis, database schema, importer,
    node detail, or comparison logic.
    """

    def __init__(self, nodes):
        super().__init__()

        self.nodes = nodes
        self.analysis_rows = []
        self.current_profile_name = ""
        self.last_html = ""

        self.setWindowTitle("Estudio de Batería en Campo")
        self.resize(1500, 900)

        self.setup_ui()
        self.load_profiles_to_combo()
        self.run_analysis()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()

        self.title_label = QLabel(
            "<b>Estudio de Batería en Campo</b><br>"
            "Diagnóstico real + parámetros ajustables + simulación de warning."
        )
        self.title_label.setWordWrap(True)
        main_layout.addWidget(self.title_label)

        profile_layout = QHBoxLayout()

        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self.apply_selected_profile)
        profile_layout.addWidget(QLabel("Perfil:"))
        profile_layout.addWidget(self.profile_combo)

        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("Nombre de perfil nuevo")
        profile_layout.addWidget(self.profile_name_input)

        self.save_profile_button = QPushButton("Guardar perfil")
        self.save_profile_button.clicked.connect(self.save_current_profile)
        profile_layout.addWidget(self.save_profile_button)

        main_layout.addLayout(profile_layout)

        controls_layout = QHBoxLayout()

        form_left = QFormLayout()
        form_right = QFormLayout()

        self.rack_declared_charge = self.create_double_spin(0, 100, 90, 1, "%")
        self.optimal_min_charge = self.create_double_spin(0, 100, 90, 1, "%")
        self.warning_percent = self.create_double_spin(0, 100, 30, 1, "%")
        self.critical_percent = self.create_double_spin(0, 100, 20, 1, "%")
        self.expected_drop_percent_day = self.create_double_spin(0, 50, 3, 0.1, "%/día")
        self.accelerated_drop_factor = self.create_double_spin(1, 10, 2, 0.1, "x")

        form_left.addRow("Carga declarada rack:", self.rack_declared_charge)
        form_left.addRow("Carga óptima mínima:", self.optimal_min_charge)
        form_left.addRow("Warning operativo:", self.warning_percent)
        form_left.addRow("Critical operativo:", self.critical_percent)
        form_left.addRow("Descarga esperada:", self.expected_drop_percent_day)
        form_left.addRow("Factor caída acelerada:", self.accelerated_drop_factor)

        self.bit_hour = self.create_spin(0, 23, 7)
        self.bit_minute = self.create_spin(0, 59, 15)
        self.gps_min_quality = self.create_double_spin(0, 100, 70, 1, "%")
        self.gps_max_minutes = self.create_double_spin(0, 240, 20, 1, "min")
        self.max_temperature_c = self.create_double_spin(-20, 100, 45, 1, "°C")
        self.ignore_zero_charge = QCheckBox("Ignorar carga 0% como dato faltante")
        self.ignore_zero_charge.setChecked(True)
        self.ignore_zero_charge.stateChanged.connect(self.run_analysis)

        form_right.addRow("Hora BITS:", self.bit_hour)
        form_right.addRow("Minuto BITS:", self.bit_minute)
        form_right.addRow("GPS mínimo válido:", self.gps_min_quality)
        form_right.addRow("Máx. tiempo GPS:", self.gps_max_minutes)
        form_right.addRow("Máx. temperatura:", self.max_temperature_c)
        form_right.addRow("", self.ignore_zero_charge)

        controls_layout.addLayout(form_left)
        controls_layout.addLayout(form_right)

        main_layout.addLayout(controls_layout)

        button_layout = QHBoxLayout()

        self.recalculate_button = QPushButton("Recalcular")
        self.recalculate_button.clicked.connect(self.run_analysis)
        button_layout.addWidget(self.recalculate_button)

        self.export_excel_button = QPushButton("Exportar Excel")
        self.export_excel_button.clicked.connect(self.export_excel)
        button_layout.addWidget(self.export_excel_button)

        self.export_html_button = QPushButton("Exportar gráfica HTML")
        self.export_html_button.clicked.connect(self.export_html)
        button_layout.addWidget(self.export_html_button)

        main_layout.addLayout(button_layout)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        main_layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(22)
        self.table.setHorizontalHeaderLabels([
            "Nodo",
            "Estado",
            "Score",
            "Conf.",
            "Rack %",
            "Primer %",
            "BITS %",
            "GPS %",
            "Sísmica %",
            "Final %",
            "Dif. rack-campo",
            "Pérdida campo",
            "%/día",
            "%/hora",
            "mV/día",
            "Horas trabajo",
            "Horas warning",
            "Horas critical",
            "GPS min",
            "Temp máx",
            "Inicio caída",
            "Causa probable",
        ])
        self.table.cellClicked.connect(self.load_chart_for_row)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        main_layout.addWidget(self.table)

        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        main_layout.addWidget(self.detail_label)

        self.web_view = QWebEngineView()
        main_layout.addWidget(self.web_view)

        central.setLayout(main_layout)

        for widget in [
            self.rack_declared_charge,
            self.optimal_min_charge,
            self.warning_percent,
            self.critical_percent,
            self.expected_drop_percent_day,
            self.accelerated_drop_factor,
            self.bit_hour,
            self.bit_minute,
            self.gps_min_quality,
            self.gps_max_minutes,
            self.max_temperature_c,
        ]:
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self.run_analysis)

    def create_double_spin(self, minimum, maximum, value, step, suffix):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.setSuffix(f" {suffix}" if suffix else "")
        return spin

    def create_spin(self, minimum, maximum, value):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def get_config(self):
        return BatteryFieldConfig(
            rack_declared_charge=float(self.rack_declared_charge.value()),
            optimal_min_charge=float(self.optimal_min_charge.value()),
            warning_percent=float(self.warning_percent.value()),
            critical_percent=float(self.critical_percent.value()),
            bit_hour=int(self.bit_hour.value()),
            bit_minute=int(self.bit_minute.value()),
            gps_min_quality=float(self.gps_min_quality.value()),
            gps_max_minutes=float(self.gps_max_minutes.value()),
            max_temperature_c=float(self.max_temperature_c.value()),
            expected_drop_percent_day=float(self.expected_drop_percent_day.value()),
            accelerated_drop_factor=float(self.accelerated_drop_factor.value()),
            ignore_zero_charge=bool(self.ignore_zero_charge.isChecked()),
        )

    def set_config(self, config):
        self.rack_declared_charge.setValue(config.rack_declared_charge)
        self.optimal_min_charge.setValue(config.optimal_min_charge)
        self.warning_percent.setValue(config.warning_percent)
        self.critical_percent.setValue(config.critical_percent)
        self.bit_hour.setValue(config.bit_hour)
        self.bit_minute.setValue(config.bit_minute)
        self.gps_min_quality.setValue(config.gps_min_quality)
        self.gps_max_minutes.setValue(config.gps_max_minutes)
        self.max_temperature_c.setValue(config.max_temperature_c)
        self.expected_drop_percent_day.setValue(config.expected_drop_percent_day)
        self.accelerated_drop_factor.setValue(config.accelerated_drop_factor)
        self.ignore_zero_charge.setChecked(config.ignore_zero_charge)

    def load_profiles_to_combo(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()

        profiles = load_profiles()

        for name in profiles.keys():
            self.profile_combo.addItem(name, profiles[name])

        self.profile_combo.blockSignals(False)

    def apply_selected_profile(self):
        values = self.profile_combo.currentData()

        if not values:
            return

        config = config_from_dict(values)
        self.set_config(config)
        self.run_analysis()

    def save_current_profile(self):
        name = self.profile_name_input.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Guardar perfil",
                "Escribe un nombre para el perfil."
            )
            return

        save_profile(name, self.get_config())
        self.load_profiles_to_combo()

        for index in range(self.profile_combo.count()):
            if self.profile_combo.itemText(index) == name:
                self.profile_combo.setCurrentIndex(index)
                break

        QMessageBox.information(
            self,
            "Guardar perfil",
            f"Perfil guardado: {name}"
        )

    def run_analysis(self):
        if not hasattr(self, "table"):
            return

        config = self.get_config()

        self.analysis_rows = analyze_field_battery_batch(
            self.nodes,
            get_records_by_serial,
            config,
        )

        self.populate_table()
        self.update_summary()

        if self.analysis_rows:
            self.table.selectRow(0)
            self.load_chart_for_row(0, 0)
        else:
            self.web_view.setHtml("<h3>No hay nodos cargados.</h3>")

    def update_summary(self):
        total = len(self.analysis_rows)

        critical = sum(1 for row in self.analysis_rows if row.get("status") == "Crítico")
        high = sum(1 for row in self.analysis_rows if row.get("status") == "Alto")
        warning = sum(1 for row in self.analysis_rows if row.get("status") == "Atención")
        normal = sum(1 for row in self.analysis_rows if row.get("status") == "Normal")

        self.summary_label.setText(
            f"<b>Nodos analizados:</b> {total} | "
            f"🔴 Crítico: {critical} | "
            f"🟠 Alto: {high} | "
            f"🟡 Atención: {warning} | "
            f"🟢 Normal: {normal}<br>"
            f"<b>Parámetros actuales:</b> rack {self.rack_declared_charge.value():.0f}%, "
            f"warning {self.warning_percent.value():.0f}%, "
            f"critical {self.critical_percent.value():.0f}%, "
            f"descarga esperada {self.expected_drop_percent_day.value():.2f}%/día"
        )

    def populate_table(self):
        self.table.setRowCount(len(self.analysis_rows))

        for row_index, row in enumerate(self.analysis_rows):
            values = [
                row.get("serial_number", ""),
                row.get("status", ""),
                row.get("risk_score", ""),
                row.get("confidence", ""),
                row.get("rack_declared_charge", ""),
                row.get("first_charge", ""),
                row.get("bit_charge", ""),
                row.get("gps_charge", ""),
                row.get("seismic_charge", ""),
                row.get("final_charge", ""),
                row.get("rack_gap", ""),
                row.get("field_loss", ""),
                row.get("field_rate_percent_day", ""),
                row.get("field_rate_percent_hour", ""),
                row.get("voltage_rate_mv_day", ""),
                row.get("work_hours", ""),
                row.get("warning_hours", ""),
                row.get("critical_hours", ""),
                row.get("gps_minutes", ""),
                row.get("max_temp", ""),
                format_optional_datetime(row.get("accelerated_time")),
                row.get("probable_cause", ""),
            ]

            for column, value in enumerate(values):
                if isinstance(value, float):
                    text = f"{value:.2f}"
                else:
                    text = str(value)

                item = QTableWidgetItem(text)

                if column == 1:
                    status = row.get("status")
                    if status == "Crítico":
                        item.setText("🔴 Crítico")
                    elif status == "Alto":
                        item.setText("🟠 Alto")
                    elif status == "Atención":
                        item.setText("🟡 Atención")
                    elif status == "Normal":
                        item.setText("🟢 Normal")

                self.table.setItem(row_index, column, item)

    def get_selected_analysis_row(self, row_index):
        if row_index < 0 or row_index >= len(self.analysis_rows):
            return None

        return self.analysis_rows[row_index]

    def load_chart_for_row(self, row_index, column=0):
        analysis = self.get_selected_analysis_row(row_index)

        if analysis is None:
            return

        df = analysis.get("prepared_df")

        if df is None or df.empty:
            self.web_view.setHtml("<h3>Sin datos válidos.</h3>")
            return

        self.detail_label.setText(
            f"<b>Nodo {analysis.get('serial_number')}</b><br>"
            f"<b>Estado:</b> {analysis.get('status')} | "
            f"<b>Score:</b> {analysis.get('risk_score')} | "
            f"<b>Confianza:</b> {analysis.get('confidence')}<br>"
            f"<b>Causa probable:</b> {analysis.get('probable_cause')}<br>"
            f"<b>Evidencia:</b> {analysis.get('evidence')}<br>"
            f"<b>Recomendación:</b> {analysis.get('recommendation')}<br>"
            f"<b>Simulación:</b> {analysis.get('simulated_note')}"
        )

        fig = go.Figure()

        valid_charge = df.dropna(subset=["timestamp", "charge_for_analysis"])

        if not valid_charge.empty:
            fig.add_trace(
                go.Scatter(
                    x=valid_charge["timestamp"],
                    y=valid_charge["charge_for_analysis"],
                    mode="lines+markers",
                    name="Carga (%)",
                    customdata=valid_charge[
                        [
                            "voltage_mv",
                            "gps_quality",
                            "temperature_c",
                            "acq_type",
                        ]
                    ],
                    hovertemplate=(
                        "<b>Fecha:</b> %{x}<br>"
                        "<b>Carga:</b> %{y:.2f}%<br>"
                        "<b>Voltaje:</b> %{customdata[0]} mV<br>"
                        "<b>GPS:</b> %{customdata[1]}%<br>"
                        "<b>Temp:</b> %{customdata[2]} °C<br>"
                        "<b>Modo:</b> %{customdata[3]}<br>"
                        "<extra></extra>"
                    ),
                )
            )

        if "voltage_mv" in df.columns:
            voltage_df = df.dropna(subset=["timestamp", "voltage_mv"])
            if not voltage_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=voltage_df["timestamp"],
                        y=voltage_df["voltage_mv"],
                        mode="lines",
                        name="Voltaje (mV)",
                        yaxis="y2",
                        opacity=0.45,
                    )
                )

        fig.add_hline(
            y=self.warning_percent.value(),
            line_dash="dot",
            annotation_text=f"Warning {self.warning_percent.value():.0f}%"
        )

        fig.add_hline(
            y=self.critical_percent.value(),
            line_dash="dash",
            annotation_text=f"Critical {self.critical_percent.value():.0f}%"
        )

        marker_events = [
            ("BITS", analysis.get("bit_time"), analysis.get("bit_charge")),
            ("GPS válido", analysis.get("gps_time"), analysis.get("gps_charge")),
            ("Inicio sísmica", analysis.get("seismic_time"), analysis.get("seismic_charge")),
            ("Caída acelerada", analysis.get("accelerated_time"), None),
            ("Retiro simulado", analysis.get("recommended_retrieval_time"), None),
        ]

        for label, event_time, charge_value in marker_events:
            if event_time is None:
                continue

            y_value = charge_value

            if y_value is None:
                near = valid_charge[
                    valid_charge["timestamp"] <= event_time
                ]

                if not near.empty:
                    y_value = near.iloc[-1]["charge_for_analysis"]
                elif not valid_charge.empty:
                    y_value = valid_charge.iloc[0]["charge_for_analysis"]

            if y_value is None or pd.isna(y_value):
                continue

            fig.add_trace(
                go.Scatter(
                    x=[event_time],
                    y=[y_value],
                    mode="markers+text",
                    name=label,
                    text=[label],
                    textposition="top center",
                    marker=dict(size=11, symbol="x"),
                    hovertemplate=(
                        f"<b>{label}</b><br>"
                        "Fecha: %{x}<br>"
                        "Carga: %{y:.2f}%<br>"
                        "<extra></extra>"
                    ),
                )
            )

        fig.update_layout(
            title=f"Estudio de batería en campo - Nodo {analysis.get('serial_number')}",
            xaxis_title="Tiempo",
            yaxis_title="Carga (%)",
            yaxis2=dict(
                title="Voltaje (mV)",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            template="plotly_white",
            hovermode="closest",
            legend_title="Datos",
        )

        html = fig.to_html(include_plotlyjs=True)
        self.last_html = html
        self.render_html(html)

    def render_html(self, html):
        temp_dir = Path(tempfile.gettempdir()) / "node_health_analyzer"
        temp_dir.mkdir(parents=True, exist_ok=True)

        html_path = temp_dir / f"battery_field_study_{uuid.uuid4().hex}.html"
        html_path.write_text(html, encoding="utf-8")

        self.web_view.load(QUrl.fromLocalFile(str(html_path)))

    def export_excel(self):
        if not self.analysis_rows:
            QMessageBox.warning(self, "Exportar Excel", "No hay datos para exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Excel",
            "battery_field_study.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        export_rows = []

        for row in self.analysis_rows:
            export_rows.append({
                "Nodo": row.get("serial_number"),
                "Estado": row.get("status"),
                "Score": row.get("risk_score"),
                "Confianza": row.get("confidence"),
                "Rack declarado %": row.get("rack_declared_charge"),
                "Primer %": row.get("first_charge"),
                "BITS %": row.get("bit_charge"),
                "GPS %": row.get("gps_charge"),
                "Sísmica %": row.get("seismic_charge"),
                "Final %": row.get("final_charge"),
                "Dif. rack-campo": row.get("rack_gap"),
                "Pérdida campo": row.get("field_loss"),
                "%/día": row.get("field_rate_percent_day"),
                "%/hora": row.get("field_rate_percent_hour"),
                "mV/día": row.get("voltage_rate_mv_day"),
                "Horas trabajo": row.get("work_hours"),
                "Horas warning": row.get("warning_hours"),
                "Horas critical": row.get("critical_hours"),
                "GPS min": row.get("gps_minutes"),
                "Temp prom": row.get("avg_temp"),
                "Temp máx": row.get("max_temp"),
                "Inicio caída acelerada": format_optional_datetime(row.get("accelerated_time")),
                "Causa probable": row.get("probable_cause"),
                "Evidencia": row.get("evidence"),
                "Recomendación": row.get("recommendation"),
                "Simulación": row.get("simulated_note"),
            })

        try:
            pd.DataFrame(export_rows).to_excel(file_path, index=False)
            QMessageBox.information(self, "Exportar Excel", "Archivo exportado correctamente.")
        except Exception as error:
            QMessageBox.critical(self, "Exportar Excel", str(error))

    def export_html(self):
        if not self.last_html:
            QMessageBox.warning(self, "Exportar HTML", "No hay gráfica para exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar HTML",
            "battery_field_study_chart.html",
            "HTML Files (*.html)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(self.last_html)
            QMessageBox.information(self, "Exportar HTML", "Gráfica exportada correctamente.")
        except Exception as error:
            QMessageBox.critical(self, "Exportar HTML", str(error))
