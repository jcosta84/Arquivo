import hashlib
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

from auth import autenticar, hash_password, verify_password
from db import get_connection, fetch_all, fetch_one, execute


# =========================================================
# CONFIGURAÇÃO DO STREAMLIT
# =========================================================

st.set_page_config(
    page_title="Arquivo Digital",
    page_icon="🗃️",
    layout="wide"
)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def log(
    operacao,
    descricao=None,
    documento_id=None
):

    user = st.session_state.get("user")

    usuario_id = (
        user["id"]
        if user
        else None
    )

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

    if "user" in st.session_state:
        return

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
# FORMATAR TAMANHO
# =========================================================

def format_size(numero):

    numero = numero or 0

    if numero < 1024:

        return f"{numero} B"

    if numero < 1024 ** 2:

        return (
            f"{numero / 1024:.1f} KB"
        )

    if numero < 1024 ** 3:

        return (
            f"{numero / 1024 ** 2:.1f} MB"
        )

    return (
        f"{numero / 1024 ** 3:.2f} GB"
    )


# =========================================================
# CARREGAR DEPARTAMENTOS / TIPOS
# =========================================================

def options_from_table(table):

    tabelas_permitidas = {
        "departamentos",
        "tipos_documento"
    }

    if table not in tabelas_permitidas:

        raise ValueError(
            "Tabela inválida."
        )

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
# GERAR REFERÊNCIA AUTOMÁTICA
# =========================================================

def gerar_nova_referencia(ano):

    conn = get_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                ultimo_numero
            FROM sequencia_documentos
            WHERE ano = %s
            FOR UPDATE
            """,
            (
                ano,
            )
        )

        resultado = cursor.fetchone()

        if resultado is None:

            numero = 1

            cursor.execute(
                """
                INSERT INTO sequencia_documentos
                (
                    ano,
                    ultimo_numero
                )
                VALUES
                (
                    %s,
                    %s
                )
                """,
                (
                    ano,
                    numero
                )
            )

        else:

            numero = (
                resultado["ultimo_numero"]
                + 1
            )

            cursor.execute(
                """
                UPDATE sequencia_documentos
                SET ultimo_numero = %s
                WHERE ano = %s
                """,
                (
                    numero,
                    ano
                )
            )

        conn.commit()

        return (
            f"DOC-{ano}-{numero:06d}"
        )

    except Exception:

        conn.rollback()

        raise

    finally:

        cursor.close()

        conn.close()


# =========================================================
# AUTENTICAÇÃO
# =========================================================

require_login()

user = st.session_state.user


# =========================================================
# MENU LATERAL
# =========================================================

with st.sidebar:

    st.title("🗃️ Arquivo Digital")

    st.write(
        f"**{user['nome']}**"
    )

    if user["nivel"] == "admin":
        st.caption("Administrador")
    else:
        st.caption("Utilizador")

    st.divider()

    # =====================================================
    # MENU PARA ADMINISTRADOR
    # =====================================================

    if user["nivel"] == "admin":

        menu = [
            "Painel",
            "Novo documento",
            "Pesquisar documentos",
            "Departamentos e tipos",
            "Utilizadores",
            "Histórico"
        ]

        icons = [
            "speedometer2",
            "file-earmark-plus",
            "search",
            "people",
            "person-gear",
            "clock-history"
        ]

    # =====================================================
    # MENU PARA UTILIZADOR
    # =====================================================

    else:

        menu = [
            "Painel",
            "Novo documento",
            "Pesquisar documentos",
            "Definições"
        ]

        icons = [
            "speedometer2",
            "file-earmark-plus",
            "search",
            "gear"
        ]

    # =====================================================
    # OPTION MENU
    # =====================================================

    pagina = option_menu(
        menu_title="Menu",
        options=menu,
        icons=icons,
        menu_icon="list",
        default_index=0,
        orientation="vertical"
    )

    st.divider()

    # =====================================================
    # TERMINAR SESSÃO
    # =====================================================

    if st.button(
        "🚪 Terminar sessão",
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

            x.criado_em AS `Inserido em`

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

    # -----------------------------------------------------
    # REFERÊNCIA
    # -----------------------------------------------------

    if (
        "referencia_novo_documento"
        not in st.session_state
    ):

        st.session_state[
            "referencia_novo_documento"
        ] = gerar_nova_referencia(
            date.today().year
        )

    referencia = (
        st.session_state[
            "referencia_novo_documento"
        ]
    )

    # -----------------------------------------------------
    # FORMULÁRIO
    # -----------------------------------------------------

    with st.form(
        "form_novo_documento",
        clear_on_submit=True
    ):

        coluna1, coluna2 = st.columns(2)

        coluna1.text_input(
            "Referência / Nº do documento",
            value=referencia,
            disabled=True
        )

        titulo = coluna2.text_input(
            "Título *"
        )

        coluna3, coluna4 = st.columns(2)

        departamento_nome = (
            coluna3.selectbox(
                "Departamento *",
                list(
                    dep_map.keys()
                )
            )
        )

        tipo_nome = (
            coluna4.selectbox(
                "Tipo de documento *",
                list(
                    tipo_map.keys()
                )
            )
        )

        coluna5, coluna6 = st.columns(2)

        data_documento = (
            coluna5.date_input(
                "Data do documento *",
                value=date.today()
            )
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

    # -----------------------------------------------------
    # GUARDAR
    # -----------------------------------------------------

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

            extensao = (
                Path(
                    uploaded.name
                )
                .suffix
                .lower()
                .lstrip(".")
            )

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
                        referencia,
                        titulo.strip(),
                        assunto.strip() or None,
                        descricao.strip() or None,
                        dep_map[departamento_nome],
                        tipo_map[tipo_nome],
                        data_documento,
                        data_documento.year,
                        data_documento.month,
                        uploaded.name,
                        extensao or None,
                        uploaded.type or None,
                        len(conteudo),
                        conteudo,
                        hash_sha256,
                        user["id"]
                    )
                )

                documento_id = cursor.lastrowid

                conn.commit()

                log(
                    "CRIAR_DOCUMENTO",
                    (
                        f"Documento "
                        f"'{titulo.strip()}' "
                        f"arquivado com referência "
                        f"{referencia}."
                    ),
                    documento_id
                )

                st.success(
                    (
                        f"Documento {referencia} "
                        "arquivado com sucesso!"
                    )
                )

                del st.session_state[
                    "referencia_novo_documento"
                ]

                st.rerun()

            except Exception as erro:

                conn.rollback()

                st.error(
                    f"Erro ao guardar documento: {erro}"
                )

            finally:

                cursor.close()

                conn.close()


# =========================================================
# PESQUISAR DOCUMENTOS
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

        dep_map[item["nome"]] = item["id"]

    tipo_map = {
        "Todos": None
    }

    for item in tipos:

        tipo_map[item["nome"]] = item["id"]

    # -----------------------------------------------------
    # FILTROS
    # -----------------------------------------------------

    coluna1, coluna2, coluna3 = st.columns(3)

    texto = coluna1.text_input(
        "Pesquisar",
        placeholder="Referência, título ou assunto"
    )

    departamento_nome = coluna2.selectbox(
        "Departamento",
        list(dep_map.keys())
    )

    tipo_nome = coluna3.selectbox(
        "Tipo",
        list(tipo_map.keys())
    )

    coluna4, coluna5, coluna6 = st.columns(3)

    anos = (
        ["Todos"]
        +
        list(
            range(
                date.today().year,
                1990,
                -1
            )
        )
    )

    ano = coluna4.selectbox(
        "Ano",
        anos
    )

    mes = coluna5.selectbox(
        "Mês",
        ["Todos"] + list(range(1, 13))
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

    # -----------------------------------------------------
    # QUERY
    # -----------------------------------------------------

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
                OR x.titulo LIKE %s
                OR x.assunto LIKE %s
            )
        """

        pesquisa = f"%{texto.strip()}%"

        parametros.extend(
            [
                pesquisa,
                pesquisa,
                pesquisa
            ]
        )

    departamento_id = dep_map[
        departamento_nome
    ]

    if departamento_id:

        sql += """
            AND x.departamento_id = %s
        """

        parametros.append(
            departamento_id
        )

    tipo_id = tipo_map[
        tipo_nome
    ]

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
            int(ano)
        )

    if mes != "Todos":

        sql += """
            AND x.mes = %s
        """

        parametros.append(
            int(mes)
        )

    sql += """
        ORDER BY
            x.data_documento DESC,
            x.id DESC

        LIMIT %s
    """

    parametros.append(
        int(limite)
    )

    documentos = fetch_all(
        sql,
        tuple(parametros)
    )

    # -----------------------------------------------------
    # RESULTADOS
    # -----------------------------------------------------

    if not documentos:

        st.info(
            "Nenhum processo encontrado."
        )

    else:

        st.write(
            f"**{len(documentos)} processo(s) encontrado(s)**"
        )

        dataframe = pd.DataFrame(
            documentos
        )

        dataframe["tamanho"] = (
            dataframe["tamanho_bytes"]
            .apply(format_size)
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

        st.write("")

        # -------------------------------------------------
        # SELECIONAR PROCESSO
        # -------------------------------------------------

        ids = [
            documento["id"]
            for documento in documentos
        ]

        processo_selecionado = st.selectbox(
            "Selecionar processo",
            ids,
            format_func=lambda identificador: next(
                (
                    f"{doc['referencia']} — "
                    f"{doc['titulo']}"
                )
                for doc in documentos
                if doc["id"] == identificador
            )
        )

        # -------------------------------------------------
        # CARREGAR PROCESSO
        # -------------------------------------------------

        processo = fetch_one(
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
                processo_selecionado,
            )
        )

        # -------------------------------------------------
        # PRÉ-VISUALIZAÇÃO
        # -------------------------------------------------

        if processo:

            st.divider()

            st.header(
                "👁️ Pré-visualização"
            )

            st.subheader(
                processo["titulo"]
            )

            coluna1, coluna2, coluna3 = st.columns(3)

            coluna1.write(
                f"**Referência:** {processo['referencia']}"
            )

            coluna2.write(
                f"**Departamento:** {processo['departamento']}"
            )

            coluna3.write(
                f"**Tipo:** {processo['tipo']}"
            )

            coluna4, coluna5, coluna6 = st.columns(3)

            coluna4.write(
                f"**Data:** {processo['data_documento']}"
            )

            coluna5.write(
                (
                    f"**Organização:** "
                    f"{processo['ano']}/"
                    f"{processo['mes']:02d}"
                )
            )

            coluna6.write(
                f"**Inserido por:** {processo['criado_por_nome']}"
            )

            if processo["assunto"]:

                st.write(
                    f"**Assunto:** {processo['assunto']}"
                )

            if processo["descricao"]:

                st.write(
                    "**Descrição / Observações:**"
                )

                st.write(
                    processo["descricao"]
                )

            st.write(
                f"**Documento:** {processo['nome_ficheiro']}"
            )

            st.write(
                (
                    f"**Tamanho:** "
                    f"{format_size(processo['tamanho_bytes'])}"
                )
            )

            # -------------------------------------------------
            # DOWNLOAD
            # -------------------------------------------------

            st.download_button(
                "⬇️ Transferir ficheiro",

                data=processo["conteudo"],

                file_name=processo["nome_ficheiro"],

                mime=(
                    processo["mime_type"]
                    or
                    "application/octet-stream"
                ),

                key=f"download_{processo['id']}"
            )

            st.write("")

            # -------------------------------------------------
            # PRÉ-VISUALIZAÇÃO
            # -------------------------------------------------

            mime_type = (
                processo["mime_type"]
                or ""
            )

            if mime_type == "application/pdf":

                try:

                    st.pdf(
                        processo["conteudo"],
                        height=900
                    )

                except Exception as erro:

                    st.error(
                        f"Erro ao apresentar o PDF: {erro}"
                    )

            elif mime_type.startswith("image/"):

                st.image(
                    processo["conteudo"],
                    caption=processo["nome_ficheiro"],
                    use_container_width=True
                )

            else:

                st.info(
                    (
                        "A pré-visualização direta "
                        "não está disponível para "
                        "este tipo de ficheiro. "
                        "Utilize o botão "
                        "'Transferir ficheiro'."
                    )
                )

            # -------------------------------------------------
            # ADMINISTRADOR
            # -------------------------------------------------

            if user["nivel"] == "admin":

                st.divider()

                st.subheader(
                    "⚙️ Administração do processo"
                )

                st.warning(
                    "A eliminação do processo é definitiva."
                )

                if st.button(
                    "🗑️ Eliminar processo",
                    key=f"eliminar_{processo['id']}"
                ):

                    titulo_eliminado = processo["titulo"]

                    referencia_eliminada = (
                        processo["referencia"]
                    )

                    execute(
                        """
                        DELETE FROM documentos
                        WHERE id = %s
                        """,
                        (
                            processo["id"],
                        )
                    )

                    log(
                        "ELIMINAR_DOCUMENTO",
                        (
                            f"Processo "
                            f"{referencia_eliminada} - "
                            f"'{titulo_eliminado}' "
                            "eliminado."
                        )
                    )

                    st.success(
                        "Processo eliminado."
                    )

                    st.rerun()


# =========================================================
# DEPARTAMENTOS E TIPOS
# SOMENTE ADMINISTRADOR
# =========================================================

elif pagina == "Departamentos e tipos":

    if user["nivel"] != "admin":

        st.error(
            "Acesso não autorizado."
        )

        st.stop()

    st.header(
        "⚙️ Departamentos e tipos de documento"
    )

    coluna1, coluna2 = st.columns(2)

    # -----------------------------------------------------
    # DEPARTAMENTOS
    # -----------------------------------------------------

    with coluna1:

        st.subheader(
            "Departamentos"
        )

        novo_departamento = st.text_input(
            "Novo departamento"
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
                        str(erro)
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

    # -----------------------------------------------------
    # TIPOS
    # -----------------------------------------------------

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
                        str(erro)
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
# SOMENTE ADMINISTRADOR
# =========================================================

elif pagina == "Utilizadores" and user["nivel"] == "admin":

    st.header(
        "👤 Gestão de Utilizadores"
    )

    # =====================================================
    # CRIAR NOVO UTILIZADOR
    # =====================================================

    with st.expander(
        "➕ Criar novo utilizador",
        expanded=False
    ):

        with st.form(
            "form_criar_utilizador",
            clear_on_submit=True
        ):

            coluna1, coluna2 = st.columns(2)

            username = coluna1.text_input(
                "Username *"
            )

            nome = coluna2.text_input(
                "Nome *"
            )

            coluna3, coluna4 = st.columns(2)

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
                "💾 Criar utilizador",
                type="primary",
                use_container_width=True
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

            elif len(password) < 6:

                st.error(
                    "A palavra-passe deve ter pelo menos 6 caracteres."
                )

            else:

                try:

                    # -------------------------------------
                    # VERIFICAR SE USERNAME JÁ EXISTE
                    # -------------------------------------

                    existente = fetch_one(
                        """
                        SELECT id
                        FROM usuarios
                        WHERE username = %s
                        """,
                        (
                            username.strip(),
                        )
                    )

                    if existente:

                        st.error(
                            "Este username já existe."
                        )

                    else:

                        # ---------------------------------
                        # CRIAR HASH BCRYPT
                        # ---------------------------------

                        password_hash = hash_password(
                            password
                        )

                        # ---------------------------------
                        # INSERIR UTILIZADOR
                        # ---------------------------------

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
                                password_hash,
                                nome.strip(),
                                email.strip() or None,
                                nivel
                            )
                        )

                        log(
                            "CRIAR_UTILIZADOR",
                            (
                                f"Utilizador "
                                f"'{username.strip()}' "
                                f"criado."
                            )
                        )

                        st.success(
                            "Utilizador criado com sucesso."
                        )

                        st.rerun()

                except Exception as erro:

                    st.error(
                        f"Erro ao criar utilizador: {erro}"
                    )

    # =====================================================
    # LISTAR UTILIZADORES
    # =====================================================

    st.divider()

    st.subheader(
        "👥 Utilizadores cadastrados"
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

    if not users:

        st.info(
            "Não existem utilizadores cadastrados."
        )

    else:

        # -----------------------------------------------
        # TABELA
        # -----------------------------------------------

        dataframe = pd.DataFrame(
            users
        )

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # =================================================
        # SELECIONAR UTILIZADOR
        # =================================================

        utilizadores_map = {
            (
                f"{item['username']} — "
                f"{item['nome']} "
                f"({item['nivel']})"
            ):
            item["id"]

            for item in users
        }

        utilizador_selecionado = st.selectbox(
            "Selecionar utilizador para editar",
            list(
                utilizadores_map.keys()
            )
        )

        id_selecionado = utilizadores_map[
            utilizador_selecionado
        ]

        # =================================================
        # CARREGAR DADOS DO UTILIZADOR
        # =================================================

        dados_user = fetch_one(
            """
            SELECT
                id,
                username,
                nome,
                email,
                nivel,
                ativo
            FROM usuarios
            WHERE id = %s
            """,
            (
                id_selecionado,
            )
        )

        if dados_user:

            st.subheader(
                "✏️ Editar utilizador"
            )

            # =================================================
            # FORMULÁRIO DE EDIÇÃO
            # =================================================

            with st.form(
                "form_editar_usuario"
            ):

                coluna1, coluna2 = st.columns(2)

                novo_username = coluna1.text_input(
                    "Nome de utilizador *",
                    value=dados_user["username"]
                )

                novo_nome = coluna2.text_input(
                    "Nome *",
                    value=dados_user["nome"]
                )

                coluna3, coluna4 = st.columns(2)

                novo_email = coluna3.text_input(
                    "Email",
                    value=dados_user["email"] or ""
                )

                niveis = [
                    "admin",
                    "utilizador"
                ]

                nivel_atual = dados_user["nivel"]

                if nivel_atual not in niveis:

                    nivel_atual = "utilizador"

                novo_nivel_edit = coluna4.selectbox(
                    "Nível",
                    niveis,
                    index=niveis.index(
                        nivel_atual
                    )
                )

                nova_senha_edit = st.text_input(
                    "Nova palavra-passe "
                    "(deixe em branco para não alterar)",
                    type="password"
                )

                confirmar_senha_edit = st.text_input(
                    "Confirmar nova palavra-passe",
                    type="password"
                )

                ativo_atual = bool(
                    dados_user["ativo"]
                )

                novo_estado = st.checkbox(
                    "Utilizador ativo",
                    value=ativo_atual
                )

                st.divider()

                coluna1, coluna2 = st.columns(2)

                atualizar = coluna1.form_submit_button(
                    "💾 Atualizar",
                    type="primary",
                    use_container_width=True
                )

                deletar = coluna2.form_submit_button(
                    "🗑️ Excluir",
                    use_container_width=True
                )

            # =================================================
            # ATUALIZAR UTILIZADOR
            # =================================================

            if atualizar:

                if not novo_username.strip():

                    st.error(
                        "O username é obrigatório."
                    )

                elif not novo_nome.strip():

                    st.error(
                        "O nome é obrigatório."
                    )

                elif (
                    nova_senha_edit
                    and len(nova_senha_edit) < 6
                ):

                    st.error(
                        "A nova palavra-passe deve ter "
                        "pelo menos 6 caracteres."
                    )

                elif (
                    nova_senha_edit
                    and nova_senha_edit
                    != confirmar_senha_edit
                ):

                    st.error(
                        "A nova palavra-passe e a confirmação "
                        "não coincidem."
                    )

                else:

                    try:

                        # ---------------------------------
                        # VERIFICAR USERNAME
                        # ---------------------------------

                        username_existente = fetch_one(
                            """
                            SELECT id
                            FROM usuarios
                            WHERE username = %s
                            AND id <> %s
                            """,
                            (
                                novo_username.strip(),
                                id_selecionado
                            )
                        )

                        if username_existente:

                            st.error(
                                "Este username já está a ser "
                                "utilizado por outro utilizador."
                            )

                        else:

                            # ---------------------------------
                            # ATUALIZAR COM OU SEM SENHA
                            # ---------------------------------

                            if nova_senha_edit:

                                novo_hash = hash_password(
                                    nova_senha_edit
                                )

                                execute(
                                    """
                                    UPDATE usuarios
                                    SET
                                        username = %s,
                                        nome = %s,
                                        email = %s,
                                        nivel = %s,
                                        ativo = %s,
                                        password_hash = %s
                                    WHERE id = %s
                                    """,
                                    (
                                        novo_username.strip(),
                                        novo_nome.strip(),
                                        novo_email.strip() or None,
                                        novo_nivel_edit,
                                        novo_estado,
                                        novo_hash,
                                        id_selecionado
                                    )
                                )

                            else:

                                execute(
                                    """
                                    UPDATE usuarios
                                    SET
                                        username = %s,
                                        nome = %s,
                                        email = %s,
                                        nivel = %s,
                                        ativo = %s
                                    WHERE id = %s
                                    """,
                                    (
                                        novo_username.strip(),
                                        novo_nome.strip(),
                                        novo_email.strip() or None,
                                        novo_nivel_edit,
                                        novo_estado,
                                        id_selecionado
                                    )
                                )

                            # ---------------------------------
                            # REGISTAR HISTÓRICO
                            # ---------------------------------

                            log(
                                "EDITAR_UTILIZADOR",
                                (
                                    f"Utilizador "
                                    f"'{dados_user['username']}' "
                                    f"alterado para "
                                    f"'{novo_username.strip()}'."
                                )
                            )

                            st.success(
                                "Utilizador atualizado com sucesso."
                            )

                            st.rerun()

                    except Exception as erro:

                        st.error(
                            f"Erro ao atualizar utilizador: {erro}"
                        )

            # =================================================
            # EXCLUIR UTILIZADOR
            # =================================================

            if deletar:

                # ---------------------------------------------
                # NÃO PERMITIR EXCLUIR O PRÓPRIO UTILIZADOR
                # ---------------------------------------------

                if id_selecionado == user["id"]:

                    st.error(
                        "Não é possível excluir o utilizador "
                        "que está atualmente autenticado."
                    )

                else:

                    try:

                        # -----------------------------------------
                        # GUARDAR DADOS ANTES DA ELIMINAÇÃO
                        # -----------------------------------------

                        username_eliminado = (
                            dados_user["username"]
                        )

                        nome_eliminado = (
                            dados_user["nome"]
                        )

                        # -----------------------------------------
                        # ELIMINAR
                        # -----------------------------------------

                        execute(
                            """
                            DELETE FROM usuarios
                            WHERE id = %s
                            """,
                            (
                                id_selecionado,
                            )
                        )

                        # -----------------------------------------
                        # HISTÓRICO
                        # -----------------------------------------

                        log(
                            "ELIMINAR_UTILIZADOR",
                            (
                                f"Utilizador "
                                f"'{username_eliminado}' "
                                f"({nome_eliminado}) "
                                f"eliminado."
                            )
                        )

                        st.success(
                            "Utilizador excluído com sucesso."
                        )

                        st.rerun()

                    except Exception as erro:

                        st.error(
                            f"Erro ao excluir utilizador: {erro}"
                        )


# =========================================================
# DEFINIÇÕES
# =========================================================

elif (
    pagina == "Definições"
    and user["nivel"] == "utilizador"
):

    st.header(
        "⚙️ Definições"
    )

    st.subheader(
        "🔐 Alterar palavra-passe"
    )

    st.caption(
        f"Utilizador: {user['username']}"
    )

    st.divider()

    with st.form(
        "form_alterar_senha"
    ):

        senha_atual = st.text_input(
            "Palavra-passe atual *",
            type="password"
        )

        nova_senha = st.text_input(
            "Nova palavra-passe *",
            type="password"
        )

        confirmar_senha = st.text_input(
            "Confirmar nova palavra-passe *",
            type="password"
        )

        alterar = st.form_submit_button(
            "🔐 Alterar palavra-passe",
            type="primary",
            use_container_width=True
        )

    if alterar:

        if not senha_atual:

            st.error(
                "Introduza a palavra-passe atual."
            )

        elif not nova_senha:

            st.error(
                "Introduza a nova palavra-passe."
            )

        elif not confirmar_senha:

            st.error(
                "Confirme a nova palavra-passe."
            )

        elif nova_senha != confirmar_senha:

            st.error(
                "A nova palavra-passe e a confirmação não coincidem."
            )

        elif len(nova_senha) < 6:

            st.error(
                "A nova palavra-passe deve ter pelo menos 6 caracteres."
            )

        elif nova_senha == senha_atual:

            st.error(
                "A nova palavra-passe deve ser diferente da atual."
            )

        else:

            try:

                utilizador = fetch_one(
                    """
                    SELECT
                        id,
                        username,
                        password_hash
                    FROM usuarios
                    WHERE id = %s
                    """,
                    (
                        user["id"],
                    )
                )

                if not utilizador:

                    st.error(
                        "Utilizador não encontrado."
                    )

                else:

                    from auth import verify_password

                    senha_valida = verify_password(
                        senha_atual,
                        utilizador["password_hash"]
                    )

                    if not senha_valida:

                        st.error(
                            "A palavra-passe atual está incorreta."
                        )

                    else:

                        nova_senha_hash = hash_password(
                            nova_senha
                        )

                        execute(
                            """
                            UPDATE usuarios
                            SET password_hash = %s
                            WHERE id = %s
                            """,
                            (
                                nova_senha_hash,
                                user["id"]
                            )
                        )

                        log(
                            "ALTERAR_SENHA",
                            (
                                "Palavra-passe alterada "
                                f"pelo utilizador "
                                f"'{user['username']}'."
                            )
                        )

                        st.success(
                            "Palavra-passe alterada com sucesso!"
                        )

                        st.info(
                            "Por segurança, termine a sessão "
                            "e entre novamente com a nova palavra-passe."
                        )

            except Exception as erro:

                st.error(
                    f"Erro ao alterar a palavra-passe: {erro}"
                )


# =========================================================
# HISTÓRICO
# SOMENTE ADMINISTRADOR
# =========================================================

elif pagina == "Histórico":

    if user["nivel"] != "admin":

        st.error(
            "Acesso não autorizado."
        )

        st.stop()

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