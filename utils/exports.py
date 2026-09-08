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
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, frame in tables.items():
            safe_cells(frame).to_excel(writer, sheet_name=name[:31], index=False)
    return output.getvalue()
