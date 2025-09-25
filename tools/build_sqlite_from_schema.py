import sqlite3, argparse, os, glob, csv

def exec_sql(conn, sql_text: str):
    cur = conn.cursor()
    cur.executescript(sql_text)
    conn.commit()

def load_csvs(conn, csv_folder: str):
    for p in glob.glob(os.path.join(csv_folder, "*.csv")):
        table = os.path.splitext(os.path.basename(p))[0]
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            placeholders = ",".join(["?"] * len(header))
            sql = f"INSERT INTO {table} ({','.join(header)}) VALUES ({placeholders})"
            rows = list(reader)
        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
        print(f"  - Loaded {len(rows)} rows into {table}")

def main():
    ap = argparse.ArgumentParser(description="Build SQLite DB from DDL and optional CSV folder")
    ap.add_argument("--ddl", required=True, help="Path to .sql file containing DDL")
    ap.add_argument("--db", default="data/spider2.db", help="SQLite DB output path")
    ap.add_argument("--csv-folder", help="Optional folder with <table>.csv files to load")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    with open(args.ddl, "r", encoding="utf-8") as f: ddl = f.read()

    conn = sqlite3.connect(args.db)
    exec_sql(conn, ddl); print(f"✅ Built SQLite schema -> {args.db}")
    if args.csv_folder and os.path.isdir(args.csv_folder): load_csvs(conn, args.csv_folder)
    conn.close()

if __name__ == "__main__":
    main()
