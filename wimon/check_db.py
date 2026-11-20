import sqlite3

conn = sqlite3.connect("portal.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM victims")
rows = cursor.fetchall()

for row in rows:
  print(
      f"ID: {row['id']} | 企業名: {row['name']} | 業種: {row['industry']} |"
      f" データ量: {row['data_size']}"
  )

conn.close()