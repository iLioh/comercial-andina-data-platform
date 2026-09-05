import ast
from pathlib import Path


def test_prefect_flow_exposes_each_operational_stage():
    source = Path("src/comercial_andina/flows/daily_sales.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    task_names = []

    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Name) or decorator.func.id != "task":
                continue
            name_keyword = next(
                (keyword for keyword in decorator.keywords if keyword.arg == "name"), None
            )
            if name_keyword and isinstance(name_keyword.value, ast.Constant):
                task_names.append(name_keyword.value.value)

    assert task_names == [
        "01 - Preparar lote",
        "02 - Extraer PostgreSQL y persistir RAW",
        "03 - Cargar Staging",
        "04 - Validar y publicar Data Warehouse",
        "05 - Exportar cuarentena",
        "06 - Conciliar y auditar",
    ]
