from io import BytesIO
import pandas as pd


def safe_cells(frame):
    result = frame.copy()
    for column in result.select_dtypes(include=["object", "string"]):
        result[column] = result[column].map(lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value)
    return result


def csv_bytes(frame):
    return safe_cells(frame).to_csv(index=False).encode("utf-8-sig")


def excel_bytes(tables):
    from openpyxl import Workbook
    output = BytesIO()
    # Stream worksheet XML instead of retaining one Python object per Excel cell.
    workbook = Workbook(write_only=True)
    try:
        for name, frame in tables.items():
            sheet = workbook.create_sheet(name[:31])
            sheet.append(list(frame.columns))
            for row in frame.itertuples(index=False, name=None):
                values = []
                for value in row:
                    if isinstance(value, str):
                        values.append("'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value)
                    else:
                        values.append(None if pd.isna(value) else value)
                sheet.append(values)
        workbook.save(output)
    finally:
        workbook.close()
    return output.getvalue()
