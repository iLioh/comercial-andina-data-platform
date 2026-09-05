from comercial_andina.etl.azure_sql import AzureSqlExecutor


def test_query_one_maps_columns_to_values():
    class Cursor:
        description = [("count",), ("status",)]

        def fetchone(self):
            return (9_980, "SUCCESS")

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _sql, _parameters):
            return Cursor()

    executor = object.__new__(AzureSqlExecutor)
    executor._connect = lambda: Connection()

    assert executor.query_one("SELECT 1") == {"count": 9_980, "status": "SUCCESS"}
