import sqlite3, os, json

os.makedirs("data", exist_ok=True)
os.makedirs("predictions", exist_ok=True)
os.makedirs("out", exist_ok=True)

def main():
    conn = sqlite3.connect("data/sample.db")
    cur = conn.cursor()

    cur.executescript("""    DROP TABLE IF EXISTS departments;
    DROP TABLE IF EXISTS employees;

    CREATE TABLE departments (
        id   INTEGER PRIMARY KEY,
        name TEXT
    );

    CREATE TABLE employees (
        id      INTEGER PRIMARY KEY,
        name    TEXT,
        dept_id INTEGER,
        salary  INTEGER,
        FOREIGN KEY(dept_id) REFERENCES departments(id)
    );
    """)

    cur.executemany("INSERT INTO departments(id,name) VALUES(?,?)",
                    [(1,"Engineering"),(2,"HR"),(3,"Sales")])
    cur.executemany("INSERT INTO employees(id,name,dept_id,salary) VALUES(?,?,?,?)",
                    [(1,"Alice",1,120),(2,"Bob",1,110),(3,"Charlie",2,90),(4,"David",3,100),(5,"Eva",3,95)])
    conn.commit(); conn.close()
    print("✅ data/sample.db created")

    testcases = [
        {
            "id":"q1",
            "question":"부서별 직원 수를 세어 부서명 오름차순으로 보여줘",
            "gold_sql":[
                "SELECT d.name AS dept, COUNT(*) AS cnt FROM employees e JOIN departments d ON e.dept_id = d.id GROUP BY d.name ORDER BY d.name",
                "SELECT name AS dept, COUNT(*) AS cnt FROM (SELECT e.dept_id, d.name FROM employees e JOIN departments d ON e.dept_id = d.id) t GROUP BY name ORDER BY name"
            ]
        },
        {
            "id":"q2",
            "question":"각 부서의 평균 급여를 계산해 높은 순서로 보여줘",
            "gold_sql":"SELECT d.name AS dept, AVG(e.salary) AS avg_salary FROM employees e JOIN departments d ON e.dept_id = d.id GROUP BY d.name ORDER BY avg_salary DESC"
        }
    ]
    with open("data/testcases_sample.json","w",encoding="utf-8") as f:
        json.dump(testcases,f,ensure_ascii=False,indent=2)
    print("✅ data/testcases_sample.json created")

    preds = [
        {"id":"q1","pred_sql":"SELECT d.name AS dept, COUNT(1) AS cnt FROM departments d JOIN employees e ON e.dept_id = d.id GROUP BY d.name ORDER BY d.name"},
        {"id":"q2","pred_sql":"SELECT d.name AS dept, AVG(e.salary) AS avg_salary FROM employees e JOIN departments d ON e.dept_id = d.id GROUP BY d.name ORDER BY avg_salary DESC"}
    ]
    with open("predictions/sample_preds.json","w",encoding="utf-8") as f:
        json.dump(preds,f,ensure_ascii=False,indent=2)
    print("✅ predictions/sample_preds.json created")

if __name__ == "__main__":
    main()
