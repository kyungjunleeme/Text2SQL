import pandas as pd
import sqlalchemy as sa

class SQLAlchemyBackend:
    def __init__(self, engine_url: str):
        self.engine_url = engine_url
        self.engine = sa.create_engine(engine_url, pool_pre_ping=True)

    def exec(self, sql: str):
        with self.engine.connect() as c:
            c.execute(sa.text(sql))

    def fetch_df(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as c:
            return pd.read_sql(sa.text(sql), c)
