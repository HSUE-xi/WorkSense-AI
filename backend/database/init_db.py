import sqlite3

DATABASE = "backend/database/worksense.db"


connection = sqlite3.connect(DATABASE)

connection.execute("""
CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_no TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    standard_time INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

connection.commit()
connection.close()

print("資料庫初始化完成！")