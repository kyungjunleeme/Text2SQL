import pandas as pd
from pyhive import hive

class SparkBackend:
    def __init__(self, host: str, port: int = 10000, username: str | None = None,
                 database: str = "default", auth: str = "NONE"):
        self.kw = dict(host=host, port=port, username=username, database=database, auth=auth)

    def _conn(self):
        return hive.Connection(**self.kw)

    def exec(self, sql: str):
        with self._conn() as c:
            cur = c.cursor()
            cur.execute(sql)

    def fetch_df(self, sql: str) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql(sql, c)
