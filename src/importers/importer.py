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

                # Elimina columnas basura tipo "Unnamed"
                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

                record_count = len(df)

                # Convertir campos numéricos
                df["Int. Voltage (mV)"] = pd.to_numeric(
                    df["Int. Voltage (mV)"], errors="coerce"
                )

                df["Int. Charge (%)"] = pd.to_numeric(
                    df["Int. Charge (%)"], errors="coerce"
                )

                # Quitar filas sin voltaje real
                valid_df = df.dropna(
                    subset=["Int. Voltage (mV)", "Int. Charge (%)"]
                )

                # Preferir último registro operativo
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
                    voltage = latest_row["Int. Voltage (mV)"]
                    charge = latest_row["Int. Charge (%)"]
                    acq_type = latest_row["Acq. Type"]
                else:
                    voltage = ""
                    charge = ""
                    acq_type = ""

                nodes.append({
                    "serial_number": csv_file.stem,
                    "records": record_count,
                    "voltage": voltage,
                    "charge": charge,
                    "acq_type": acq_type,
                    "file_path": str(csv_file)
                })

            except Exception as e:
                print(f"Error leyendo {csv_file.name}: {e}")

                nodes.append({
                    "serial_number": csv_file.stem,
                    "records": "",
                    "voltage": "",
                    "charge": "",
                    "acq_type": "",
                    "file_path": str(csv_file)
                })

        return nodes