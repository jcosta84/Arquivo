import bcrypt

from db import fetch_one
from db import execute


def hash_password(password: str) -> str:

    senha_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    )

    return senha_hash.decode(
        "utf-8"
    )


def verify_password(
    password: str,
    password_hash: str
) -> bool:

    return bcrypt.checkpw(

        password.encode(
            "utf-8"
        ),

        password_hash.encode(
            "utf-8"
        )
    )


def autenticar(
    username: str,
    password: str
):

    user = fetch_one(
        """
        SELECT
            id,
            username,
            password_hash,
            nome,
            email,
            nivel,
            ativo
        FROM usuarios
        WHERE username = %s
        """,
        (username,)
    )

    if not user:

        return None

    if not user["ativo"]:

        return None

    if not verify_password(
        password,
        user["password_hash"]
    ):

        return None

    execute(
        """
        UPDATE usuarios
        SET ultimo_acesso = NOW()
        WHERE id = %s
        """,
        (
            user["id"],
        )
    )

    user.pop(
        "password_hash",
        None
    )

    return user