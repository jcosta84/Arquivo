from db import get_connection


print(
    "=========================================="
)

print(
    " TESTE DE CONEXÃO MYSQL"
)

print(
    "=========================================="
)


try:

    conn = get_connection()

    print()
    print(
        "Ligação ao MySQL realizada com sucesso!"
    )

    cursor = conn.cursor()


    # =====================================================
    # SERVIDOR
    # =====================================================

    cursor.execute(
        "SELECT @@hostname;"
    )

    servidor = cursor.fetchone()[0]

    print(
        "Servidor:",
        servidor
    )


    # =====================================================
    # BASE DE DADOS
    # =====================================================

    cursor.execute(
        "SELECT DATABASE();"
    )

    database = cursor.fetchone()[0]

    print(
        "Base de dados:",
        database
    )


    # =====================================================
    # UTILIZADOR
    # =====================================================

    cursor.execute(
        "SELECT USER();"
    )

    usuario = cursor.fetchone()[0]

    print(
        "Utilizador:",
        usuario
    )


    # =====================================================
    # VERSÃO
    # =====================================================

    cursor.execute(
        "SELECT VERSION();"
    )

    versao = cursor.fetchone()[0]

    print(
        "MySQL:",
        versao
    )


    cursor.close()

    conn.close()


    print()
    print(
        "=========================================="
    )

    print(
        " TESTE CONCLUÍDO COM SUCESSO"
    )

    print(
        "=========================================="
    )


except Exception as erro:

    print()
    print(
        "ERRO NA LIGAÇÃO AO MYSQL:"
    )

    print(
        erro
    )