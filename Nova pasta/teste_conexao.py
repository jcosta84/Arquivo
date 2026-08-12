from db import get_connection


try:

    conn = get_connection()

    print("Ligação realizada com sucesso!")

    cursor = conn.cursor()

    cursor.execute("SELECT DATABASE();")

    database = cursor.fetchone()

    print("Base de dados:", database[0])

    cursor.execute("SELECT USER();")

    usuario = cursor.fetchone()

    print("Utilizador:", usuario[0])

    cursor.close()
    conn.close()

except Exception as erro:

    print("Erro na ligação:")
    print(erro)