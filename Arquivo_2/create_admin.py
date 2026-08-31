import getpass

from Arquivo_3.auth import hash_password
from db import execute


print(
    "========================================"
)

print(
    " CRIAR ADMINISTRADOR"
)

print(
    "========================================"
)


username = input(
    "Username: "
).strip()


nome = input(
    "Nome: "
).strip()


email = input(
    "Email (opcional): "
).strip()


if not email:

    email = None


password = getpass.getpass(
    "Palavra-passe: "
)


confirmar = getpass.getpass(
    "Confirmar palavra-passe: "
)


# =========================================================
# VALIDAÇÕES
# =========================================================

if not username:

    raise SystemExit(
        "Username obrigatório."
    )


if not nome:

    raise SystemExit(
        "Nome obrigatório."
    )


if not password:

    raise SystemExit(
        "Palavra-passe obrigatória."
    )


if password != confirmar:

    raise SystemExit(
        "As palavras-passe não coincidem."
    )


# =========================================================
# CRIAR HASH
# =========================================================

password_hash = hash_password(
    password
)


# =========================================================
# INSERIR UTILIZADOR
# =========================================================

try:

    user_id = execute(
        """
        INSERT INTO usuarios
        (
            username,

            password_hash,

            nome,

            email,

            nivel,

            ativo
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            'admin',
            TRUE
        )
        """,

        (
            username,

            password_hash,

            nome,

            email
        )
    )


    print()
    print(
        "Administrador criado com sucesso!"
    )

    print(
        "ID:",
        user_id
    )


except Exception as erro:

    print()
    print(
        "Erro ao criar administrador:"
    )

    print(
        erro
    )