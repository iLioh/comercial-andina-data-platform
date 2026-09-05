from comercial_andina.etl.redshift import RedshiftDataExecutor


def test_query_one_decodes_data_api_record():
    class Client:
        def get_statement_result(self, Id):
            assert Id == "statement-1"
            return {
                "ColumnMetadata": [{"name": "count"}, {"name": "status"}],
                "Records": [[{"longValue": 9_980}, {"stringValue": "SUCCESS"}]],
            }

    executor = object.__new__(RedshiftDataExecutor)
    executor.client = Client()
    executor.execute = lambda _sql: {"Id": "statement-1", "HasResultSet": True}

    assert executor.query_one("SELECT 1") == {"count": 9_980, "status": "SUCCESS"}
