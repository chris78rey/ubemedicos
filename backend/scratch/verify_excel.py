import openpyxl

def verify():
    try:
        wb = openpyxl.load_workbook("g:/codex_projects/ubemedicos/web_frontend/public/plantilla_especialidades.xlsx")
        sheet = wb.active
        print(f"File ok. Header: {sheet.cell(row=1, column=1).value}")
    except Exception as e:
        print(f"File error: {e}")

if __name__ == "__main__":
    verify()
