import pymssql

from dotenv import load_dotenv
import os

load_dotenv()


def connect_db():
    try:
        return pymssql.connect(
            server=os.getenv("SQL_SERVER", ""),
            user=os.getenv("SQL_USER", ""),
            password=os.getenv("SQL_PASSWORD", "") or "",
            database=os.getenv("SQL_DATABASE", ""),
            charset="UTF-8",
            as_dict=True,
        )
    except Exception as e:
        raise RuntimeError(
            f"数据库连接失败: {os.getenv('SQL_SERVER')} / {os.getenv('SQL_DATABASE')}"
        ) from e


def get_db():
    conn = connect_db()
    try:
        yield conn
    finally:
        conn.close()

