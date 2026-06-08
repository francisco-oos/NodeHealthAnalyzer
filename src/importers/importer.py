from pathlib import Path

import pandas as pd

from src.analysis.health_score import calculate_health_score, classify_node
from src.analysis.battery_life import calculate_battery_insight
from src.database.database import save_node_records


class CSVImporter:

    def load_folder(self, folder_path):
        csv_files = list(Path(folder_path).glob("*.csv"))
        nodes = []

        for csv_file in csv_files:
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
                ]

                for column in numeric_columns:
                    if column in df.columns:
                        df[column] = pd.to_numeric(
                            df[column],
                            errors="coerce"
                        )

                records_to_save = []

                for _, row in df.iterrows():
                    records_to_save.append({
                        "timestamp": row.get("Start Local Time", ""),
                        "voltage_mv": row.get("Int. Voltage (mV)", None),
                        "charge_percent": row.get("Int. Charge (%)", None),
                        "gps_quality": row.get("GPS Quality (%)", None),
                        "temperature_c": row.get("Int. Temp. (°C)", None),
                        "acq_type": row.get("Acq. Type", ""),
                    })

                save_node_records(
                    csv_file.stem,
                    records_to_save
                )

                print(
                    f"Guardado: {csv_file.name} - "
                    f"{record_count} registros"
                )

                analysis_df = pd.DataFrame(records_to_save)
                battery_insight = calculate_battery_insight(analysis_df)

                valid_df = df.dropna(
                    subset=["Int. Voltage (mV)", "Int. Charge (%)"]
                )

                operational_df = valid_df[
                    valid_df["Acq. Type"].isin(["Seismic", "BIT"])
                ]

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
                    "recommendation": battery_insight.get("recommendation_key"),
                })

        return nodes