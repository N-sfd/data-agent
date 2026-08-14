import pandas as pd


def parse_excel(file_path: str) -> dict:
    workbook = pd.ExcelFile(file_path)
    result = {}

    for sheet_name in workbook.sheet_names:
        dataframe = pd.read_excel(workbook, sheet_name=sheet_name)
        result[sheet_name] = dataframe.to_dict(orient="records")

    return result
