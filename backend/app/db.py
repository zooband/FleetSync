import pymssql

from dotenv import load_dotenv
import os

load_dotenv()


def format_db_error(err: Exception) -> str:
    """将 pymssql/DB-Lib 异常信息里的 bytes 解码为可读字符串。

    常见形式：err.args = (50000, b'...')，其中 bytes 往往是 UTF-8（也可能是 GBK）。
    """

    def _decode(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            # 先尝试 UTF-8，再回退 GBK；都不行就替换非法字符
            for enc in ("utf-8", "gbk"):
                try:
                    return value.decode(enc)
                except Exception:
                    pass
            return value.decode("utf-8", errors="replace")
        return str(value)

    args = getattr(err, "args", None)
    if args:
        parts = [_decode(a).strip() for a in args if _decode(a).strip()]
        if parts:
            return " ".join(parts)
    return str(err)


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

