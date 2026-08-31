import base64
import hashlib

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from Arquivo_3.auth import autenticar
from Arquivo_3.auth import hash_password

from db import get_connection
from db import fetch_all
from db import fetch_one
from db import execute


# =========================================================
# CONFIGURAÇÃO STREAMLIT
# =========================================================

st.set_page_config(

    page_title="Arquivo Digital",

    page_icon="🗃️",

    layout="wide"
)


# =========================================================
# LOGS
# =========================================================

def log(
    operacao,
    descricao=None,
    documento_id=None
):

    user = st.session_state.get(
        "user"
    )

    usuario_id = None

    if user:

        usuario_id = user["id"]

    execute(
        """
        INSERT INTO logs
        (
            usuario_id,
            operacao,
            descricao,
            documento_id
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            usuario_id,
            operacao,
            descricao,
            documento_id
        )
    )


# =========================================================
# LOGIN
# =========================================================

def require_login():

    if "user" not in st.session_state:

        st.title(
            "🗃️ Sistema de Arquivo Digital"
        )

        st.caption(
            "Gestão e arquivo eletrónico de documentos"
        )

        st.divider()

        with st.form(
            "form_login"
        ):

            username = st.text_input(
                "Utilizador"
            )

            password = st.text_input(
                "Palavra-passe",
                type="password"
            )

            entrar = st.form_submit_button(
                "Entrar",
                use_container_width=True
            )

        if entrar:

            user = autenticar(
                username.strip(),
                password
            )

            if user:

                st.session_state.user = user

                log(
                    "LOGIN",
                    f"Entrada no sistema: {user['username']}"
                )

                st.rerun()

            else:

                st.error(
                    "Utilizador ou palavra-passe inválidos."
                )

        st.stop()


# =========================================================
# FORMATAR TAMANHO DO FICHEIRO
# =========================================================

def format_size(numero):

    if numero < 1024:

        return f"{numero} B"

    if numero < 1024 ** 2:

        return f"{numero / 1024:.1f} KB"

    if numero < 1024 ** 3:

        return (
            f"{numero / 1024 ** 2:.1f} MB"
        )

    return (
        f"{numero / 1024 ** 3:.2f} GB"
    )


# =========================================================
# CARREGAR OPÇÕES
# =========================================================

def options_from_table(
    table
):

    return fetch_all(
        f"""
        SELECT
            id,
            nome
        FROM {table}
        WHERE ativo = TRUE
        ORDER BY nome
        """
    )


# =========================================================
# AUTENTICAÇÃO
# =========================================================

require_login()


user = st.session_state.user


# =========================================================
# MENU
# =========================================================

with st.sidebar:

    st.title(
        "🗃️ Arquivo Digital"
    )

    st.write(
        f"**{user['nome']}**"
    )

    if user["nivel"] == "admin":

        st.caption(
            "Administrador"
        )

    else:

        st.caption(
            "Utilizador"
        )

    st.divider()

    menu = [

        "Painel",

        "Novo documento",

        "Pesquisar documentos"
    ]

    if user["nivel"] == "admin":

        menu += [

            "Departamentos e tipos",

            "Utilizadores",

            "Histórico"
        ]

    pagina = st.radio(
        "Menu",
        menu
    )

    st.divider()

    if st.button(
        "Terminar sessão",
        use_container_width=True
    ):

        log(
            "LOGOUT",
            f"Saída do sistema: {user['username']}"
        )

        del st.session_state["user"]

        st.rerun()


# =========================================================
# PAINEL
# =========================================================

if pagina == "Painel":

    st.header(
        "📊 Painel"
    )

    stats = fetch_one(
        """
        SELECT

            COUNT(*) AS total,

            COALESCE(
                SUM(tamanho_bytes),
                0
            ) AS tamanho,

            COUNT(
                DISTINCT departamento_id
            ) AS departamentos,

            COUNT(
                DISTINCT tipo_documento_id
            ) AS tipos

        FROM documentos
        """
    )

    coluna1, coluna2, coluna3, coluna4 = (
        st.columns(4)
    )

    coluna1.metric(
        "Documentos",
        stats["total"]
    )

    coluna2.metric(
        "Armazenamento",
        format_size(
            stats["tamanho"]
        )
    )

    coluna3.metric(
        "Departamentos",
        stats["departamentos"]
    )

    coluna4.metric(
        "Tipos",
        stats["tipos"]
    )

    st.divider()

    st.subheader(
        "Documentos por departamento"
    )

    dados_departamentos = fetch_all(
        """
        SELECT

            d.nome AS Departamento,

            COUNT(x.id) AS Quantidade

        FROM departamentos d

        LEFT JOIN documentos x
            ON x.departamento_id = d.id

        GROUP BY
            d.id,
            d.nome

        ORDER BY
            Quantidade DESC,
            d.nome
        """
    )

    if dados_departamentos:

        dataframe = pd.DataFrame(
            dados_departamentos
        )

        dataframe = dataframe.set_index(
            "Departamento"
        )

        st.bar_chart(
            dataframe
        )


    st.divider()

    st.subheader(
        "Últimos documentos"
    )

    ultimos = fetch_all(
        """
        SELECT

            x.id AS ID,

            x.referencia AS Referência,

            x.titulo AS Título,

            d.nome AS Departamento,

            t.nome AS Tipo,

            x.data_documento AS Data,

            x.criado_em AS 'Inserido em'

        FROM documentos x

        INNER JOIN departamentos d
            ON d.id = x.departamento_id

        INNER JOIN tipos_documento t
            ON t.id = x.tipo_documento_id

        ORDER BY
            x.criado_em DESC

        LIMIT 10
        """
    )

    if ultimos:

        st.dataframe(

            pd.DataFrame(
                ultimos
            ),

            use_container_width=True,

            hide_index=True
        )

    else:

        st.info(
            "Ainda não existem documentos arquivados."
        )


# =========================================================
# NOVO DOCUMENTO
# =========================================================

elif pagina == "Novo documento":

    st.header(
        "➕ Arquivar documento"
    )

    departamentos = options_from_table(
        "departamentos"
    )

    tipos = options_from_table(
        "tipos_documento"
    )

    if not departamentos:

        st.warning(
            "Não existem departamentos cadastrados."
        )

        st.stop()


    if not tipos:

        st.warning(
            "Não existem tipos de documento cadastrados."
        )

        st.stop()


    dep_map = {

        item["nome"]: item["id"]

        for item in departamentos
    }


    tipo_map = {

        item["nome"]: item["id"]

        for item in tipos
    }


    with st.form(
        "form_novo_documento",
        clear_on_submit=True
    ):

        coluna1, coluna2 = (
            st.columns(2)
        )


        referencia = coluna1.text_input(
            "Referência / Nº do documento"
        )


        titulo = coluna2.text_input(
            "Título *"
        )


        coluna3, coluna4 = (
            st.columns(2)
        )


        departamento_nome = coluna3.selectbox(
            "Departamento *",
            list(
                dep_map.keys()
            )
        )


        tipo_nome = coluna4.selectbox(
            "Tipo de documento *",
            list(
                tipo_map.keys()
            )
        )


        coluna5, coluna6 = (
            st.columns(2)
        )


        data_documento = coluna5.date_input(
            "Data do documento *",
            value=date.today()
        )


        assunto = coluna6.text_input(
            "Assunto"
        )


        descricao = st.text_area(
            "Descrição / Observações"
        )


        uploaded = st.file_uploader(

            "Selecionar ficheiro *",

            type=[

                "pdf",

                "doc",

                "docx",

                "xls",

                "xlsx",

                "csv",

                "txt",

                "jpg",

                "jpeg",

                "png",

                "tif",

                "tiff"
            ]
        )


        guardar = st.form_submit_button(
            "💾 Guardar no arquivo",
            type="primary"
        )


    if guardar:

        if not titulo.strip():

            st.error(
                "O título é obrigatório."
            )


        elif uploaded is None:

            st.error(
                "Deve selecionar um ficheiro."
            )


        else:

            conteudo = uploaded.getvalue()


            hash_sha256 = hashlib.sha256(
                conteudo
            ).hexdigest()


            extensao = Path(
                uploaded.name
            ).suffix.lower().lstrip(".")


            conn = get_connection()

            cursor = conn.cursor()


            try:

                cursor.execute(
                    """
                    INSERT INTO documentos
                    (
                        referencia,

                        titulo,

                        assunto,

                        descricao,

                        departamento_id,

                        tipo_documento_id,

                        data_documento,

                        ano,

                        mes,

                        nome_ficheiro,

                        extensao,

                        mime_type,

                        tamanho_bytes,

                        conteudo,

                        hash_sha256,

                        criado_por
                    )

                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,

                    (
                        referencia.strip()
                        or None,

                        titulo.strip(),

                        assunto.strip()
                        or None,

                        descricao.strip()
                        or None,

                        dep_map[
                            departamento_nome
                        ],

                        tipo_map[
                            tipo_nome
                        ],

                        data_documento,

                        data_documento.year,

                        data_documento.month,

                        uploaded.name,

                        extensao or None,

                        uploaded.type
                        or None,

                        len(
                            conteudo
                        ),

                        conteudo,

                        hash_sha256,

                        user["id"]
                    )
                )


                documento_id = (
                    cursor.lastrowid
                )


                conn.commit()


                log(

                    "CRIAR_DOCUMENTO",

                    (
                        f"Documento "
                        f"'{titulo}' arquivado."
                    ),

                    documento_id
                )


                st.success(
                    (
                        "Documento arquivado "
                        "com sucesso. "
                        f"ID: {documento_id}"
                    )
                )


            except Exception as erro:

                conn.rollback()

                st.error(
                    f"Erro ao guardar documento: {erro}"
                )


            finally:

                cursor.close()

                conn.close()


# =========================================================
# PESQUISAR
# =========================================================

elif pagina == "Pesquisar documentos":

    st.header(
        "🔎 Pesquisar documentos"
    )


    departamentos = options_from_table(
        "departamentos"
    )


    tipos = options_from_table(
        "tipos_documento"
    )


    dep_map = {
        "Todos": None
    }


    for item in departamentos:

        dep_map[
            item["nome"]
        ] = item["id"]


    tipo_map = {
        "Todos": None
    }


    for item in tipos:

        tipo_map[
            item["nome"]
        ] = item["id"]


    coluna1, coluna2, coluna3 = (
        st.columns(3)
    )


    texto = coluna1.text_input(
        "Pesquisar",
        placeholder=(
            "Referência, título ou assunto"
        )
    )


    departamento_nome = (
        coluna2.selectbox(
            "Departamento",
            list(
                dep_map.keys()
            )
        )
    )


    tipo_nome = (
        coluna3.selectbox(
            "Tipo",
            list(
                tipo_map.keys()
            )
        )
    )


    coluna4, coluna5, coluna6 = (
        st.columns(3)
    )


    anos = [
        "Todos"
    ] + list(
        range(
            date.today().year,
            1990,
            -1
        )
    )


    ano = coluna4.selectbox(
        "Ano",
        anos
    )


    mes = coluna5.selectbox(
        "Mês",
        [
            "Todos",
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12
        ]
    )


    limite = coluna6.selectbox(
        "Máximo de resultados",
        [
            25,
            50,
            100,
            250
        ],
        index=1
    )


    sql = """
        SELECT

            x.id,

            x.referencia,

            x.titulo,

            x.assunto,

            d.nome AS departamento,

            t.nome AS tipo,

            x.data_documento,

            x.ano,

            x.mes,

            x.nome_ficheiro,

            x.tamanho_bytes,

            x.criado_em

        FROM documentos x

        INNER JOIN departamentos d
            ON d.id = x.departamento_id

        INNER JOIN tipos_documento t
            ON t.id = x.tipo_documento_id

        WHERE 1 = 1
    """


    parametros = []


    if texto.strip():

        sql += """
            AND
            (
                x.referencia LIKE %s
                OR
                x.titulo LIKE %s
                OR
                x.assunto LIKE %s
            )
        """


        pesquisa = (
            f"%{texto.strip()}%"
        )


        parametros.extend(
            [
                pesquisa,
                pesquisa,
                pesquisa
            ]
        )


    departamento_id = (
        dep_map[
            departamento_nome
        ]
    )


    if departamento_id:

        sql += """
            AND x.departamento_id = %s
        """

        parametros.append(
            departamento_id
        )


    tipo_id = (
        tipo_map[
            tipo_nome
        ]
    )


    if tipo_id:

        sql += """
            AND x.tipo_documento_id = %s
        """

        parametros.append(
            tipo_id
        )


    if ano != "Todos":

        sql += """
            AND x.ano = %s
        """

        parametros.append(
            int(
                ano
            )
        )


    if mes != "Todos":

        sql += """
            AND x.mes = %s
        """

        parametros.append(
            int(
                mes
            )
        )


    sql += """

        ORDER BY
            x.data_documento DESC,
            x.id DESC

        LIMIT %s
    """


    parametros.append(
        int(
            limite
        )
    )


    documentos = fetch_all(

        sql,

        tuple(
            parametros
        )
    )


    if not documentos:

        st.info(
            "Nenhum documento encontrado."
        )


    else:

        dataframe = pd.DataFrame(
            documentos
        )


        dataframe["tamanho"] = (
            dataframe[
                "tamanho_bytes"
            ].apply(
                format_size
            )
        )


        st.write(
            f"**{len(documentos)} documento(s) encontrado(s)**"
        )


        st.dataframe(

            dataframe[
                [
                    "id",
                    "referencia",
                    "titulo",
                    "assunto",
                    "departamento",
                    "tipo",
                    "data_documento",
                    "nome_ficheiro",
                    "tamanho"
                ]
            ],

            use_container_width=True,

            hide_index=True
        )


        ids = [

            documento["id"]

            for documento in documentos
        ]


        documento_selecionado = (
            st.selectbox(

                "Selecionar documento",

                ids,

                format_func=lambda identificador:
                next(
                    (
                        f"{doc['id']} — "
                        f"{doc['titulo']} — "
                        f"{doc['nome_ficheiro']}"
                    )

                    for doc in documentos

                    if doc["id"]
                    == identificador
                )
            )
        )


        documento = fetch_one(
            """
            SELECT

                x.*,

                d.nome AS departamento,

                t.nome AS tipo,

                u.nome AS criado_por_nome

            FROM documentos x

            INNER JOIN departamentos d
                ON d.id = x.departamento_id

            INNER JOIN tipos_documento t
                ON t.id = x.tipo_documento_id

            INNER JOIN usuarios u
                ON u.id = x.criado_por

            WHERE x.id = %s
            """,

            (
                documento_selecionado,
            )
        )


        if documento:

            st.divider()

            st.subheader(
                documento["titulo"]
            )


            coluna1, coluna2, coluna3 = (
                st.columns(3)
            )


            coluna1.write(
                (
                    "**Referência:** "
                    f"{documento['referencia'] or '-'}"
                )
            )


            coluna2.write(
                (
                    "**Departamento:** "
                    f"{documento['departamento']}"
                )
            )


            coluna3.write(
                (
                    "**Tipo:** "
                    f"{documento['tipo']}"
                )
            )


            st.write(
                (
                    f"**Data:** "
                    f"{documento['data_documento']}"
                )
            )


            st.write(
                (
                    "**Organização:** "
                    f"{documento['ano']}/"
                    f"{documento['mes']:02d}"
                )
            )


            st.write(
                (
                    "**Inserido por:** "
                    f"{documento['criado_por_nome']}"
                )
            )


            if documento["assunto"]:

                st.write(
                    (
                        "**Assunto:** "
                        f"{documento['assunto']}"
                    )
                )


            if documento["descricao"]:

                st.write(
                    "**Descrição:**"
                )

                st.write(
                    documento["descricao"]
                )


            st.download_button(

                "⬇️ Transferir ficheiro",

                data=documento[
                    "conteudo"
                ],

                file_name=documento[
                    "nome_ficheiro"
                ],

                mime=(
                    documento["mime_type"]
                    or
                    "application/octet-stream"
                )
            )


            # =============================================
            # PDF
            # =============================================

            if (
                documento["mime_type"]
                == "application/pdf"
            ):

                pdf_base64 = (
                    base64.b64encode(
                        documento[
                            "conteudo"
                        ]
                    ).decode()
                )


                html_pdf = f"""
                <iframe
                    src="data:application/pdf;base64,{pdf_base64}"
                    width="100%"
                    height="700"
                    type="application/pdf">
                </iframe>
                """


                st.markdown(
                    html_pdf,
                    unsafe_allow_html=True
                )


            # =============================================
            # IMAGEM
            # =============================================

            elif (
                documento[
                    "mime_type"
                ]
                or ""
            ).startswith(
                "image/"
            ):

                st.image(

                    documento[
                        "conteudo"
                    ],

                    caption=documento[
                        "nome_ficheiro"
                    ],

                    use_container_width=True
                )


            # =============================================
            # ELIMINAR
            # =============================================

            if user["nivel"] == "admin":

                st.divider()

                st.warning(
                    (
                        "A eliminação do documento "
                        "é definitiva."
                    )
                )


                if st.button(
                    "🗑️ Eliminar documento"
                ):

                    titulo_eliminado = (
                        documento[
                            "titulo"
                        ]
                    )


                    execute(
                        """
                        DELETE FROM documentos
                        WHERE id = %s
                        """,
                        (
                            documento_selecionado,
                        )
                    )


                    log(
                        "ELIMINAR_DOCUMENTO",
                        (
                            f"Documento "
                            f"'{titulo_eliminado}' "
                            "eliminado."
                        )
                    )


                    st.success(
                        "Documento eliminado."
                    )


                    st.rerun()


# =========================================================
# DEPARTAMENTOS E TIPOS
# =========================================================

elif pagina == "Departamentos e tipos":

    st.header(
        "⚙️ Departamentos e tipos de documento"
    )


    coluna1, coluna2 = (
        st.columns(2)
    )


    # =====================================================
    # DEPARTAMENTOS
    # =====================================================

    with coluna1:

        st.subheader(
            "Departamentos"
        )


        novo_departamento = (
            st.text_input(
                "Novo departamento"
            )
        )


        if st.button(
            "Adicionar departamento"
        ):

            if novo_departamento.strip():

                try:

                    execute(
                        """
                        INSERT INTO departamentos
                        (
                            nome
                        )
                        VALUES
                        (
                            %s
                        )
                        """,

                        (
                            novo_departamento.strip(),
                        )
                    )


                    log(
                        "CRIAR_DEPARTAMENTO",
                        novo_departamento.strip()
                    )


                    st.success(
                        "Departamento criado."
                    )


                    st.rerun()


                except Exception as erro:

                    st.error(
                        str(
                            erro
                        )
                    )


        departamentos = fetch_all(
            """
            SELECT
                id,
                nome,
                ativo,
                criado_em
            FROM departamentos
            ORDER BY nome
            """
        )


        if departamentos:

            st.dataframe(

                pd.DataFrame(
                    departamentos
                ),

                use_container_width=True,

                hide_index=True
            )


    # =====================================================
    # TIPOS
    # =====================================================

    with coluna2:

        st.subheader(
            "Tipos de documento"
        )


        novo_tipo = st.text_input(
            "Novo tipo de documento"
        )


        if st.button(
            "Adicionar tipo"
        ):

            if novo_tipo.strip():

                try:

                    execute(
                        """
                        INSERT INTO tipos_documento
                        (
                            nome
                        )
                        VALUES
                        (
                            %s
                        )
                        """,

                        (
                            novo_tipo.strip(),
                        )
                    )


                    log(
                        "CRIAR_TIPO_DOCUMENTO",
                        novo_tipo.strip()
                    )


                    st.success(
                        "Tipo criado."
                    )


                    st.rerun()


                except Exception as erro:

                    st.error(
                        str(
                            erro
                        )
                    )


        tipos = fetch_all(
            """
            SELECT
                id,
                nome,
                ativo,
                criado_em
            FROM tipos_documento
            ORDER BY nome
            """
        )


        if tipos:

            st.dataframe(

                pd.DataFrame(
                    tipos
                ),

                use_container_width=True,

                hide_index=True
            )


# =========================================================
# UTILIZADORES
# =========================================================

elif pagina == "Utilizadores":

    st.header(
        "👤 Gestão de Utilizadores"
    )


    with st.expander(
        "Criar novo utilizador",
        expanded=True
    ):


        with st.form(
            "form_criar_utilizador",
            clear_on_submit=True
        ):


            coluna1, coluna2 = (
                st.columns(2)
            )


            username = coluna1.text_input(
                "Username *"
            )


            nome = coluna2.text_input(
                "Nome *"
            )


            coluna3, coluna4 = (
                st.columns(2)
            )


            email = coluna3.text_input(
                "Email"
            )


            nivel = coluna4.selectbox(
                "Nível",
                [
                    "utilizador",
                    "admin"
                ]
            )


            password = st.text_input(
                "Palavra-passe *",
                type="password"
            )


            criar = st.form_submit_button(
                "Criar utilizador",
                type="primary"
            )


        if criar:

            if not username.strip():

                st.error(
                    "Username obrigatório."
                )


            elif not nome.strip():

                st.error(
                    "Nome obrigatório."
                )


            elif not password:

                st.error(
                    "Palavra-passe obrigatória."
                )


            else:

                try:

                    usuario_id = execute(
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
                            %s,
                            TRUE
                        )
                        """,

                        (
                            username.strip(),

                            hash_password(
                                password
                            ),

                            nome.strip(),

                            email.strip()
                            or None,

                            nivel
                        )
                    )


                    log(
                        "CRIAR_UTILIZADOR",
                        (
                            f"Utilizador "
                            f"{username} criado."
                        )
                    )


                    st.success(
                        (
                            "Utilizador criado "
                            "com sucesso. "
                            f"ID: {usuario_id}"
                        )
                    )


                except Exception as erro:

                    st.error(
                        str(
                            erro
                        )
                    )


    st.divider()


    st.subheader(
        "Utilizadores cadastrados"
    )


    users = fetch_all(
        """
        SELECT

            id,

            username,

            nome,

            email,

            nivel,

            ativo,

            criado_em,

            ultimo_acesso

        FROM usuarios

        ORDER BY nome
        """
    )


    if users:

        st.dataframe(

            pd.DataFrame(
                users
            ),

            use_container_width=True,

            hide_index=True
        )


# =========================================================
# HISTÓRICO
# =========================================================

elif pagina == "Histórico":

    st.header(
        "📜 Histórico de operações"
    )


    logs = fetch_all(
        """
        SELECT

            l.id,

            l.data_hora,

            u.username,

            u.nome,

            l.operacao,

            l.documento_id,

            l.descricao

        FROM logs l

        LEFT JOIN usuarios u
            ON u.id = l.usuario_id

        ORDER BY
            l.data_hora DESC

        LIMIT 500
        """
    )


    if logs:

        st.dataframe(

            pd.DataFrame(
                logs
            ),

            use_container_width=True,

            hide_index=True
        )

    else:

        st.info(
            "Não existem operações registadas."
        )