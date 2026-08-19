from db.postgres import get_connection

def check():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = cur.fetchall()
    print(tables)

if __name__ == "__main__":
    check()
