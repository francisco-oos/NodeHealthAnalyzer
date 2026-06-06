from pathlib import Path
import pandas as pd


class CSVImporter:

    def load_folder(self, folder_path):
        csv_files = list(Path(folder_path).glob("*.csv"))
        nodes = []

        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, low_memory=False)
                df.columns = df.columns.str.strip()
                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

                record_count = len(df)

                numeric_columns = [
                    "Int. Voltage (mV)",
                    "Int. Charge (%)",
                    "GPS Quality (%)",
                    "Temperature (°C)",
                ]

                for column in numeric_columns:
                    if column in df.columns:
                        df[column] = pd.to_numeric(
                            df[column],
                            errors="coerce"
                        )

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
                    temperature = latest_row.get("Temperature (°C)", "")
                    last_time = latest_row.get("Start Local Time", "")
                else:
                    voltage = ""
                    charge = ""
                    acq_type = ""
                    gps_quality = ""
                    temperature = ""
                    last_time = ""

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
                })

        return nodes