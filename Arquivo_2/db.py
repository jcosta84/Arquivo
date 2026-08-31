import configparser
from pathlib import Path

import mysql.connector


# =========================================================
# LOCALIZAÇÃO DO PROJETO
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.ini"


# =========================================================
# CARREGAR CONFIG.INI
# =========================================================

config = configparser.ConfigParser()

if not CONFIG_FILE.exists():

    raise FileNotFoundError(
        f"Ficheiro config.ini não encontrado em: {CONFIG_FILE}"
    )


config.read(
    CONFIG_FILE,
    encoding="utf-8"
)


if "DATABASE" not in config:

    raise ValueError(
        "A secção [DATABASE] não existe no config.ini."
    )


# =========================================================
# CONFIGURAÇÕES MYSQL
# =========================================================

HOST = config["DATABASE"].get(
    "HOST",
    "localhost"
).strip()


PORT = config["DATABASE"].getint(
    "PORT",
    3306
)


DATABASE = config["DATABASE"].get(
    "DATABASE"
).strip()


USERNAME = config["DATABASE"].get(
    "USERNAME"
).strip()


PASSWORD = config["DATABASE"].get(
    "PASSWORD"
).strip()


# =========================================================
# VALIDAR CONFIGURAÇÕES
# =========================================================

if not HOST:

    raise ValueError(
        "HOST não definido no config.ini."
    )


if not DATABASE:

    raise ValueError(
        "DATABASE não definido no config.ini."
    )


if not USERNAME:

    raise ValueError(
        "USERNAME não definido no config.ini."
    )


if not PASSWORD:

    raise ValueError(
        "PASSWORD não definido no config.ini."
    )


# =========================================================
# CONEXÃO MYSQL
# =========================================================

def get_connection():

    return mysql.connector.connect(

        host=HOST,

        port=PORT,

        database=DATABASE,

        user=USERNAME,

        password=PASSWORD,

        charset="utf8mb4",

        autocommit=False
    )


# =========================================================
# SELECT VÁRIOS REGISTOS
# =========================================================

def fetch_all(
    sql,
    params=None
):

    conn = get_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            sql,
            params or ()
        )

        resultado = cursor.fetchall()

        return resultado

    finally:

        cursor.close()

        conn.close()


# =========================================================
# SELECT UM REGISTO
# =========================================================

def fetch_one(
    sql,
    params=None
):

    conn = get_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            sql,
            params or ()
        )

        resultado = cursor.fetchone()

        return resultado

    finally:

        cursor.close()

        conn.close()


# =========================================================
# INSERT / UPDATE / DELETE
# =========================================================

def execute(
    sql,
    params=None
):

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            sql,
            params or ()
        )

        conn.commit()

        return cursor.lastrowid

    except Exception:

        conn.rollback()

        raise

    finally:

        cursor.close()

        conn.close()