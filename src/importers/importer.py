from pathlib import Path


class CSVImporter:

    def load_folder(self, folder_path):

        csv_files = list(
            Path(folder_path).glob("*.csv")
        )

        nodes = []

        for csv_file in csv_files:

            serial_number = csv_file.stem

            nodes.append(
                {
                    "serial_number": serial_number,
                    "file_path": str(csv_file)
                }
            )

        return nodes