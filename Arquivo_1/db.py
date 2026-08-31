import mysql.connector


HOST = "100.116.112.107"
PORT = 3306
DATABASE = "arquivo_digital"
USERNAME = "jcosta"
PASSWORD = "Loucoste@9309323"


def get_connection():

    return mysql.connector.connect(
        host=HOST,
        port=PORT,
        database=DATABASE,
        user=USERNAME,
        password=PASSWORD,
        autocommit=False
    )


def fetch_all(sql, params=None):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def fetch_one(sql, params=None):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()

    finally:
        cursor.close()
        conn.close()


def execute(sql, params=None):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params or ())
        conn.commit()
        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()