from pathlib import Path
from datetime import datetime

import pandas as pd

from src.analysis.health_score import calculate_health_score, classify_node
from src.analysis.battery_life import calculate_battery_insight
from src.database.database import (
    create_import_session,
    finish_import_session,
    save_node_records,
    save_node_summary_history,
)


class CSVImporter:

    def normalize_timestamp(self, value):
        """
        Store timestamps in a stable format so duplicate detection works
        across repeated imports and overlapping CSV files.
        """

        if value is None or pd.isna(value):
            return ""

        parsed = pd.to_datetime(str(value).strip(), errors="coerce")

        if pd.isna(parsed):
            return str(value).strip()

        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def load_folder(self, folder_path):
        csv_files = list(Path(folder_path).glob("*.csv"))
        nodes = []

        import_session_id = create_import_session(folder_path)
        total_records_saved = 0
        total_duplicates_ignored = 0

        for csv_file in csv_files:
            battery_insight = {}

            try:
                print(f"Procesando: {csv_file.name}")

                df = pd.read_csv(csv_file, low_memory=False)
                df.columns = df.columns.str.strip()
                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

                record_count = len(df)

                numeric_columns = [
                    "Int. Voltage (mV)",
                    "Int. Charge (%)",
                    "GPS Quality (%)",
                    "Int. Temp. (°C)",
                    "Int. Current (mA)",
                    "Int. FCC (mAh)",
                    "Int. Design Capacity (mAh)",
                    "Int. Charge (mAh)",
                    "GPS Duty Cycle Period (s)",
                    "GPS Lock Time (ms)",
                    "Free Space (%)",
                    "Satellites",
                    "Latitude (°)",
                    "Longitude (°)",
                ]

                for column in numeric_columns:
                    if column in df.columns:
                        df[column] = pd.to_numeric(df[column], errors="coerce")

                records_to_save = []

                for row_index, row in df.iterrows():
                    records_to_save.append({
                        "row_index": int(row_index),
                        "timestamp": self.normalize_timestamp(row.get("Start Local Time", "")),
                        "voltage_mv": row.get("Int. Voltage (mV)", None),
                        "charge_percent": row.get("Int. Charge (%)", None),
                        "gps_quality": row.get("GPS Quality (%)", None),
                        "temperature_c": row.get("Int. Temp. (°C)", None),
                        "acq_type": row.get("Acq. Type", ""),
                        "current_ma": row.get("Int. Current (mA)", None),
                        "fcc_mah": row.get("Int. FCC (mAh)", None),
                        "design_capacity_mah": row.get("Int. Design Capacity (mAh)", None),
                        "charge_mah": row.get("Int. Charge (mAh)", None),
                        "duty_cycle_period_s": row.get("GPS Duty Cycle Period (s)", None),
                        "gps_locked": row.get("GPS Locked", ""),
                        "gps_lock_time_ms": row.get("GPS Lock Time (ms)", None),
                        "settings_key": row.get("Settings Key", ""),
                        "free_space_percent": row.get("Free Space (%)", None),
                        "satellites": row.get("Satellites", None),
                        "latitude": row.get("Latitude (°)", None),
                        "longitude": row.get("Longitude (°)", None),
                    })

                inserted_count = save_node_records(
                    csv_file.stem,
                    records_to_save,
                    source_file=csv_file.name,
                    import_session_id=import_session_id,
                )

                duplicates_ignored = max(record_count - inserted_count, 0)

                total_records_saved += inserted_count
                total_duplicates_ignored += duplicates_ignored

                print(
                    f"Guardado: {csv_file.name} - "
                    f"{record_count} leídos | "
                    f"{inserted_count} nuevos | "
                    f"{duplicates_ignored} duplicados ignorados"
                )

                analysis_df = pd.DataFrame(records_to_save)
                battery_insight = calculate_battery_insight(analysis_df)

                if inserted_count > 0:
                    self.save_history_snapshot(
                        import_session_id,
                        csv_file,
                        analysis_df,
                        battery_insight,
                        inserted_count,
                    )

                valid_df = df.dropna(
                    subset=["Int. Voltage (mV)", "Int. Charge (%)"]
                )

                operational_df = valid_df[
                    valid_df["Acq. Type"].isin(["Seismic", "BIT"])
                ] if "Acq. Type" in valid_df.columns else pd.DataFrame()

                if not operational_df.empty:
                    latest_row = operational_df.iloc[-1]
                elif not valid_df.empty:
                    latest_row = valid_df.iloc[-1]
                else:
                    latest_row = None

                if latest_row is not None:
                    voltage = latest_row.get("Int. Voltage (mV)", "")
                    charge = latest_row.get("Int. Charge (%)", "")
                    acq_type = latest_row.get("Acq. Type", "")
                    gps_quality = latest_row.get("GPS Quality (%)", "")
                    temperature = latest_row.get(
                        "Int. Temp. (°C)",
                        latest_row.get("Temperature (°C)", "")
                    )
                    last_time = latest_row.get("Start Local Time", "")

                    health_score = calculate_health_score(
                        voltage,
                        charge,
                        gps_quality
                    )

                    classification = classify_node(health_score)

                else:
                    voltage = ""
                    charge = ""
                    acq_type = ""
                    gps_quality = ""
                    temperature = ""
                    last_time = ""
                    health_score = 0
                    classification = "Unknown"

                nodes.append({
                    "serial_number": csv_file.stem,
                    "records": record_count,
                    "records_saved": inserted_count,
                    "duplicates_ignored": duplicates_ignored,
                    "voltage": voltage,
                    "charge": charge,
                    "acq_type": acq_type,
                    "gps_quality": gps_quality,
                    "temperature": temperature,
                    "last_time": last_time,
                    "file_path": str(csv_file),
                    "health_score": health_score,
                    "classification": classification,

                    # Battery Intelligence dashboard values.
                    "battery_health": battery_insight.get("battery_health"),
                    "degradation_level": battery_insight.get("degradation_level"),
                    "remaining_days": battery_insight.get("remaining_days"),
                    "prediction_confidence": battery_insight.get("confidence"),
                    "recommendation": battery_insight.get("recommendation"),
                })

            except Exception as e:
                print(f"Error leyendo {csv_file.name}: {e}")

                nodes.append({
                    "serial_number": csv_file.stem,
                    "records": "",
                    "records_saved": 0,
                    "duplicates_ignored": 0,
                    "voltage": "",
                    "charge": "",
                    "acq_type": "",
                    "gps_quality": "",
                    "temperature": "",
                    "last_time": "",
                    "file_path": str(csv_file),
                    "health_score": 0,
                    "classification": "Unknown",
                    "battery_health": None,
                    "remaining_days": None,
                    "prediction_confidence": "Low",
                    "recommendation": battery_insight.get(
                        "recommendation_key",
                        "recommendation_prediction_not_reliable",
                    ),
                })

        finish_import_session(
            import_session_id,
            node_count=len(nodes),
            record_count=total_records_saved,
            duplicate_count=total_duplicates_ignored,
        )

        print(
            f"Importación finalizada: "
            f"{total_records_saved} registros nuevos | "
            f"{total_duplicates_ignored} duplicados ignorados"
        )

        return nodes

    def save_history_snapshot(
        self,
        import_session_id,
        csv_file,
        analysis_df,
        battery_insight,
        record_count,
    ):
        df = analysis_df.copy()

        if df.empty:
            return

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

        if df.empty:
            return

        first_timestamp = df["timestamp"].min()
        last_timestamp = df["timestamp"].max()
        deployment_days = (
            last_timestamp - first_timestamp
        ).total_seconds() / 86400

        for column in [
            "voltage_mv",
            "charge_percent",
            "current_ma",
            "gps_quality",
            "temperature_c",
            "fcc_mah",
            "design_capacity_mah",
        ]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        valid_voltage = df.dropna(subset=["voltage_mv"])
        latest_voltage = None
        latest_charge = None

        if not valid_voltage.empty:
            latest_row = valid_voltage.iloc[-1]
            latest_voltage = latest_row.get("voltage_mv")
            latest_charge = latest_row.get("charge_percent")

        fcc_series = df.get("fcc_mah", pd.Series(dtype=float)).dropna()
        design_series = df.get("design_capacity_mah", pd.Series(dtype=float)).dropna()

        latest_fcc = float(fcc_series.iloc[-1]) if not fcc_series.empty else None
        avg_fcc = float(fcc_series.mean()) if not fcc_series.empty else None
        design_capacity = float(design_series.iloc[-1]) if not design_series.empty else None

        fcc_health = None
        if latest_fcc is not None and design_capacity not in (None, 0):
            fcc_health = max(0, min(100, (latest_fcc / design_capacity) * 100))

        settings_key = ""
        if "settings_key" in df.columns:
            settings_values = df["settings_key"].dropna().astype(str).str.strip()
            if not settings_values.empty:
                settings_key = settings_values.iloc[-1]

        summary = {
            "import_session_id": import_session_id,
            "serial_number": csv_file.stem,
            "source_file": csv_file.name,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "first_timestamp": first_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "last_timestamp": last_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "deployment_days": deployment_days,
            "records_count": record_count,
            "latest_voltage_mv": latest_voltage,
            "latest_charge_percent": latest_charge,
            "avg_voltage_mv": df["voltage_mv"].mean() if "voltage_mv" in df.columns else None,
            "avg_charge_percent": df["charge_percent"].mean() if "charge_percent" in df.columns else None,
            "avg_current_ma": df["current_ma"].mean() if "current_ma" in df.columns else None,
            "avg_gps_quality": df["gps_quality"].mean() if "gps_quality" in df.columns else None,
            "avg_temperature_c": df["temperature_c"].mean() if "temperature_c" in df.columns else None,
            "max_temperature_c": df["temperature_c"].max() if "temperature_c" in df.columns else None,
            "latest_fcc_mah": latest_fcc,
            "avg_fcc_mah": avg_fcc,
            "design_capacity_mah": design_capacity,
            "fcc_health_percent": fcc_health,
            "voltage_slope_mv_day": battery_insight.get("voltage_slope_mv_day"),
            "charge_slope_percent_day": battery_insight.get("charge_slope_percent_day"),
            "battery_health": battery_insight.get("battery_health"),
            "degradation_level": battery_insight.get("degradation_level"),
            "prediction_confidence": battery_insight.get("confidence"),
            "recommendation": battery_insight.get("recommendation"),
            "settings_key": settings_key,
        }

        save_node_summary_history(summary)
