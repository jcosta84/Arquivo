import hashlib
import os
import sys
import subprocess
from datetime import date
from pathlib import Path
from io import BytesIO

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from auth import autenticar, hash_password, verify_password
from db import get_connection, fetch_all, fetch_one, execute


# =========================================================
# CONFIGURAÇÃO
# =========================================================

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def format_size(numero):
    numero = numero or 0
    if numero < 1024:
        return f"{numero} B"
    if numero < 1024 ** 2:
        return f"{numero / 1024:.1f} KB"
    if numero < 1024 ** 3:
        return f"{numero / 1024 ** 2:.1f} MB"
    return f"{numero / 1024 ** 3:.2f} GB"


def options_from_table(table):
    tabelas_permitidas = {"departamentos", "tipos_documento"}
    if table not in tabelas_permitidas:
        raise ValueError("Tabela inválida.")
    return fetch_all(
        f"""
        SELECT id, nome
        FROM {table}
        WHERE ativo = TRUE
        ORDER BY nome
        """
    )


def gerar_nova_referencia(ano):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT ultimo_numero
            FROM sequencia_documentos
            WHERE ano = %s
            FOR UPDATE
            """,
            (ano,)
        )
        resultado = cursor.fetchone()

        if resultado is None:
            numero = 1
            cursor.execute(
                """
                INSERT INTO sequencia_documentos (ano, ultimo_numero)
                VALUES (%s, %s)
                """,
                (ano, numero)
            )
        else:
            numero = resultado["ultimo_numero"] + 1
            cursor.execute(
                """
                UPDATE sequencia_documentos
                SET ultimo_numero = %s
                WHERE ano = %s
                """,
                (numero, ano)
            )

        conn.commit()
        return f"DOC-{ano}-{numero:06d}"
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


# =========================================================
# APLICAÇÃO PRINCIPAL
# =========================================================

class ArquivoDigitalApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("🗃️ Sistema de Arquivo Digital")
        self.geometry("1450x850")
        self.minsize(1100, 700)

        self.user = None
        self.pagina_atual = None
        self.conteudo = None
        self.processo_atual = None

        self.protocol("WM_DELETE_WINDOW", self.fechar)

        self.style_treeview()
        self.mostrar_login()

    # =====================================================
    # ESTILO
    # =====================================================

    def style_treeview(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Treeview",
            rowheight=30,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold")
        )

    # =====================================================
    # LOG
    # =====================================================

    def log(self, operacao, descricao=None, documento_id=None):
        usuario_id = self.user["id"] if self.user else None

        execute(
            """
            INSERT INTO logs
            (usuario_id, operacao, descricao, documento_id)
            VALUES (%s, %s, %s, %s)
            """,
            (usuario_id, operacao, descricao, documento_id)
        )

    # =====================================================
    # UTILITÁRIOS UI
    # =====================================================

    def limpar_janela(self):
        for widget in self.winfo_children():
            widget.destroy()

    def mensagem_erro(self, titulo, texto):
        messagebox.showerror(titulo, texto, parent=self)

    def mensagem_info(self, titulo, texto):
        messagebox.showinfo(titulo, texto, parent=self)

    def mensagem_aviso(self, titulo, texto):
        messagebox.showwarning(titulo, texto, parent=self)

    def fechar(self):
        self.destroy()

    # =====================================================
    # LOGIN
    # =====================================================

    def mostrar_login(self):
        self.user = None
        self.limpar_janela()

        self.configure(fg_color=("#f2f4f7", "#17191c"))

        fundo = ctk.CTkFrame(self, fg_color="transparent")
        fundo.pack(fill="both", expand=True)

        card = ctk.CTkFrame(
            fundo,
            width=480,
            height=440,
            corner_radius=18
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(
            card,
            text="🗃️",
            font=("Segoe UI Emoji", 44)
        ).pack(pady=(30, 5))

        ctk.CTkLabel(
            card,
            text="Sistema de Arquivo Digital",
            font=("Segoe UI", 25, "bold")
        ).pack()

        ctk.CTkLabel(
            card,
            text="Gestão e arquivo eletrónico de documentos",
            font=("Segoe UI", 12)
        ).pack(pady=(3, 25))

        self.login_username = ctk.CTkEntry(
            card,
            width=350,
            height=42,
            placeholder_text="Utilizador"
        )
        self.login_username.pack(pady=8)

        self.login_password = ctk.CTkEntry(
            card,
            width=350,
            height=42,
            placeholder_text="Palavra-passe",
            show="*"
        )
        self.login_password.pack(pady=8)
        self.login_password.bind("<Return>", lambda e: self.fazer_login())

        self.login_button = ctk.CTkButton(
            card,
            text="Entrar",
            width=350,
            height=44,
            command=self.fazer_login
        )
        self.login_button.pack(pady=(20, 10))

        self.login_status = ctk.CTkLabel(
            card,
            text="",
            text_color="red"
        )
        self.login_status.pack()

        self.login_username.focus()

    def fazer_login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get()

        if not username or not password:
            self.login_status.configure(
                text="Introduza o utilizador e a palavra-passe."
            )
            return

        try:
            user = autenticar(username, password)
        except Exception as erro:
            self.login_status.configure(text=f"Erro: {erro}")
            return

        if user:
            self.user = user
            try:
                self.log("LOGIN", f"Entrada no sistema: {user['username']}")
            except Exception:
                pass
            self.mostrar_sistema()
        else:
            self.login_status.configure(
                text="Utilizador ou palavra-passe inválidos."
            )

    # =====================================================
    # LAYOUT PRINCIPAL
    # =====================================================

    def mostrar_sistema(self):
        self.limpar_janela()

        self.configure(fg_color=("#f5f6f8", "#1a1a1a"))

        self.sidebar = ctk.CTkFrame(
            self,
            width=245,
            corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=("#f5f6f8", "#1a1a1a")
        )
        self.content.pack(side="right", fill="both", expand=True)

        self.criar_sidebar()
        self.mostrar_painel()

    def criar_sidebar(self):
        ctk.CTkLabel(
            self.sidebar,
            text="🗃️ Arquivo Digital",
            font=("Segoe UI", 21, "bold")
        ).pack(pady=(28, 6), padx=15)

        nome = self.user.get("nome") or self.user.get("username", "")
        ctk.CTkLabel(
            self.sidebar,
            text=nome,
            font=("Segoe UI", 13, "bold"),
            wraplength=210
        ).pack(pady=(4, 0))

        nivel_texto = (
            "Administrador"
            if self.user["nivel"] == "admin"
            else "Utilizador"
        )

        ctk.CTkLabel(
            self.sidebar,
            text=nivel_texto,
            font=("Segoe UI", 11)
        ).pack(pady=(0, 15))

        ctk.CTkFrame(
            self.sidebar,
            height=2,
            fg_color=("gray80", "gray25")
        ).pack(fill="x", padx=15, pady=5)

        self.menu_buttons = {}

        self.adicionar_menu("📊  Painel", self.mostrar_painel)
        self.adicionar_menu("➕  Novo documento", self.mostrar_novo_documento)
        self.adicionar_menu("🔎  Pesquisar documentos", self.mostrar_pesquisa)

        if self.user["nivel"] == "admin":
            self.adicionar_menu(
                "🏢  Departamentos e tipos",
                self.mostrar_departamentos_tipos
            )
            self.adicionar_menu(
                "👤  Utilizadores",
                self.mostrar_utilizadores
            )
            self.adicionar_menu(
                "📜  Histórico",
                self.mostrar_historico
            )
        else:
            self.adicionar_menu(
                "⚙️  Definições",
                self.mostrar_definicoes
            )

        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        ctk.CTkButton(
            self.sidebar,
            text="🚪  Terminar sessão",
            height=42,
            fg_color="transparent",
            border_width=1,
            command=self.logout
        ).pack(fill="x", padx=15, pady=15)

    def adicionar_menu(self, texto, comando):
        botao = ctk.CTkButton(
            self.sidebar,
            text=texto,
            height=43,
            anchor="w",
            fg_color="transparent",
            hover_color=("gray80", "gray25"),
            command=comando
        )
        botao.pack(fill="x", padx=12, pady=3)
        self.menu_buttons[texto] = botao

    def limpar_conteudo(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def titulo_pagina(self, titulo, subtitulo=None):
        frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )
        frame.pack(fill="x", padx=30, pady=(25, 15))

        ctk.CTkLabel(
            frame,
            text=titulo,
            font=("Segoe UI", 27, "bold")
        ).pack(anchor="w")

        if subtitulo:
            ctk.CTkLabel(
                frame,
                text=subtitulo,
                font=("Segoe UI", 12)
            ).pack(anchor="w", pady=(2, 0))

    def criar_scroll(self):
        scroll = ctk.CTkScrollableFrame(
            self.content,
            fg_color="transparent"
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=5)
        return scroll

    # =====================================================
    # LOGOUT
    # =====================================================

    def logout(self):
        try:
            self.log(
                "LOGOUT",
                f"Saída do sistema: {self.user['username']}"
            )
        except Exception:
            pass
        self.mostrar_login()

    # =====================================================
    # PAINEL
    # =====================================================

    def mostrar_painel(self):
        self.pagina_atual = "Painel"
        self.limpar_conteudo()
        self.titulo_pagina("📊 Painel", "Visão geral do arquivo digital")

        try:
            stats = fetch_one(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(tamanho_bytes), 0) AS tamanho,
                    COUNT(DISTINCT departamento_id) AS departamentos,
                    COUNT(DISTINCT tipo_documento_id) AS tipos
                FROM documentos
                """
            )
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            return

        cards = ctk.CTkFrame(self.content, fg_color="transparent")
        cards.pack(fill="x", padx=30, pady=5)

        valores = [
            ("📄", "Documentos", stats["total"]),
            ("💾", "Armazenamento", format_size(stats["tamanho"])),
            ("🏢", "Departamentos", stats["departamentos"]),
            ("📁", "Tipos", stats["tipos"]),
        ]

        for i, (icone, titulo, valor) in enumerate(valores):
            card = ctk.CTkFrame(cards, corner_radius=12)
            card.grid(row=0, column=i, sticky="nsew", padx=6)
            cards.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(
                card,
                text=f"{icone}  {titulo}",
                font=("Segoe UI", 13)
            ).pack(anchor="w", padx=18, pady=(15, 4))

            ctk.CTkLabel(
                card,
                text=str(valor),
                font=("Segoe UI", 24, "bold")
            ).pack(anchor="w", padx=18, pady=(0, 15))

        scroll = self.criar_scroll()

        ctk.CTkLabel(
            scroll,
            text="Documentos por departamento",
            font=("Segoe UI", 19, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 10))

        try:
            dados = fetch_all(
                """
                SELECT
                    d.nome AS Departamento,
                    COUNT(x.id) AS Quantidade
                FROM departamentos d
                LEFT JOIN documentos x
                    ON x.departamento_id = d.id
                GROUP BY d.id, d.nome
                ORDER BY Quantidade DESC, d.nome
                """
            )
        except Exception as erro:
            ctk.CTkLabel(scroll, text=str(erro)).pack()
            dados = []

        if dados:
            maximo = max(int(x["Quantidade"]) for x in dados) or 1
            for item in dados:
                linha = ctk.CTkFrame(scroll, fg_color="transparent")
                linha.pack(fill="x", padx=10, pady=4)

                ctk.CTkLabel(
                    linha,
                    text=str(item["Departamento"]),
                    width=220,
                    anchor="w"
                ).pack(side="left")

                barra = ctk.CTkProgressBar(linha)
                barra.pack(side="left", fill="x", expand=True, padx=10)
                barra.set(int(item["Quantidade"]) / maximo)

                ctk.CTkLabel(
                    linha,
                    text=str(item["Quantidade"]),
                    width=50
                ).pack(side="right")

        ctk.CTkLabel(
            scroll,
            text="Últimos documentos",
            font=("Segoe UI", 19, "bold")
        ).pack(anchor="w", padx=10, pady=(25, 10))

        try:
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
                INNER JOIN departamentos d ON d.id = x.departamento_id
                INNER JOIN tipos_documento t ON t.id = x.tipo_documento_id
                ORDER BY x.criado_em DESC
                LIMIT 10
                """
            )
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            ultimos = []

        if ultimos:
            self.criar_treeview(
                scroll,
                ultimos,
                [
                    ("ID", 60),
                    ("Referência", 150),
                    ("Título", 260),
                    ("Departamento", 180),
                    ("Tipo", 160),
                    ("Data", 110),
                    ("Inserido em", 160),
                ]
            )
        else:
            ctk.CTkLabel(
                scroll,
                text="Ainda não existem documentos arquivados."
            ).pack(anchor="w", padx=10)

    # =====================================================
    # TREEVIEW
    # =====================================================

    def criar_treeview(self, parent, dados, colunas, height=10):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        tree = ttk.Treeview(
            frame,
            columns=[c[0] for c in colunas],
            show="headings",
            height=height
        )

        scrollbar_y = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=tree.yview
        )
        tree.configure(yscrollcommand=scrollbar_y.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

        for nome, largura in colunas:
            tree.heading(nome, text=nome)
            tree.column(nome, width=largura, anchor="w")

        for item in dados:
            valores = []
            for nome, _ in colunas:
                valor = item.get(nome)
                valores.append("" if valor is None else str(valor))
            tree.insert("", "end", values=valores)

        return tree

    # =====================================================
    # NOVO DOCUMENTO
    # =====================================================

    def mostrar_novo_documento(self):
        self.pagina_atual = "Novo documento"
        self.limpar_conteudo()
        self.titulo_pagina(
            "➕ Arquivar documento",
            "Adicionar um novo documento ao arquivo"
        )

        try:
            departamentos = options_from_table("departamentos")
            tipos = options_from_table("tipos_documento")
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            return

        if not departamentos:
            self.mensagem_aviso(
                "Departamentos",
                "Não existem departamentos cadastrados."
            )
            return

        if not tipos:
            self.mensagem_aviso(
                "Tipos",
                "Não existem tipos de documento cadastrados."
            )
            return

        dep_map = {x["nome"]: x["id"] for x in departamentos}
        tipo_map = {x["nome"]: x["id"] for x in tipos}

        scroll = self.criar_scroll()

        card = ctk.CTkFrame(scroll, corner_radius=12)
        card.pack(fill="x", padx=10, pady=5)

        referencia = gerar_nova_referencia(date.today().year)

        self.novo_referencia = referencia

        ctk.CTkLabel(
            card,
            text="Referência / Nº do documento"
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))

        self.entry_referencia = ctk.CTkEntry(
            card,
            height=38
        )
        self.entry_referencia.grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 15)
        )
        self.entry_referencia.insert(0, referencia)
        self.entry_referencia.configure(state="disabled")

        ctk.CTkLabel(
            card,
            text="Título *"
        ).grid(row=0, column=1, sticky="w", padx=20, pady=(20, 5))

        self.entry_titulo = ctk.CTkEntry(card, height=38)
        self.entry_titulo.grid(
            row=1, column=1, sticky="ew", padx=20, pady=(0, 15)
        )

        ctk.CTkLabel(
            card,
            text="Departamento *"
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(5, 5))

        self.combo_departamento = ctk.CTkComboBox(
            card,
            values=list(dep_map.keys()),
            height=38
        )
        self.combo_departamento.grid(
            row=3, column=0, sticky="ew", padx=20, pady=(0, 15)
        )
        self.combo_departamento.set(list(dep_map.keys())[0])

        ctk.CTkLabel(
            card,
            text="Tipo de documento *"
        ).grid(row=2, column=1, sticky="w", padx=20, pady=(5, 5))

        self.combo_tipo = ctk.CTkComboBox(
            card,
            values=list(tipo_map.keys()),
            height=38
        )
        self.combo_tipo.grid(
            row=3, column=1, sticky="ew", padx=20, pady=(0, 15)
        )
        self.combo_tipo.set(list(tipo_map.keys())[0])

        ctk.CTkLabel(
            card,
            text="Data do documento *"
        ).grid(row=4, column=0, sticky="w", padx=20, pady=(5, 5))

        self.entry_data = ctk.CTkEntry(
            card,
            height=38,
            placeholder_text="AAAA-MM-DD"
        )
        self.entry_data.grid(
            row=5, column=0, sticky="ew", padx=20, pady=(0, 15)
        )
        self.entry_data.insert(0, date.today().isoformat())

        ctk.CTkLabel(
            card,
            text="Assunto"
        ).grid(row=4, column=1, sticky="w", padx=20, pady=(5, 5))

        self.entry_assunto = ctk.CTkEntry(card, height=38)
        self.entry_assunto.grid(
            row=5, column=1, sticky="ew", padx=20, pady=(0, 15)
        )

        ctk.CTkLabel(
            card,
            text="Descrição / Observações"
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=20, pady=(5, 5))

        self.text_descricao = ctk.CTkTextbox(card, height=120)
        self.text_descricao.grid(
            row=7, column=0, columnspan=2,
            sticky="ew", padx=20, pady=(0, 15)
        )

        ctk.CTkLabel(
            card,
            text="Ficheiro *"
        ).grid(row=8, column=0, sticky="w", padx=20, pady=(5, 5))

        ficheiro_frame = ctk.CTkFrame(card, fg_color="transparent")
        ficheiro_frame.grid(
            row=9, column=0, columnspan=2,
            sticky="ew", padx=20, pady=(0, 20)
        )

        self.label_ficheiro = ctk.CTkLabel(
            ficheiro_frame,
            text="Nenhum ficheiro selecionado.",
            anchor="w"
        )
        self.label_ficheiro.pack(
            side="left", fill="x", expand=True
        )

        ctk.CTkButton(
            ficheiro_frame,
            text="📁 Selecionar ficheiro",
            command=self.selecionar_ficheiro
        ).pack(side="right")

        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)

        self.dep_map_novo = dep_map
        self.tipo_map_novo = tipo_map
        self.ficheiro_selecionado = None

        ctk.CTkButton(
            scroll,
            text="💾 Guardar no arquivo",
            height=44,
            command=self.guardar_documento
        ).pack(anchor="e", padx=10, pady=15)

    def selecionar_ficheiro(self):
        tipos = [
            ("Documentos suportados",
             "*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.jpg *.jpeg *.png *.tif *.tiff"),
            ("PDF", "*.pdf"),
            ("Word", "*.doc *.docx"),
            ("Excel", "*.xls *.xlsx"),
            ("Imagens", "*.jpg *.jpeg *.png *.tif *.tiff"),
            ("Todos os ficheiros", "*.*"),
        ]

        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar ficheiro",
            filetypes=tipos
        )

        if caminho:
            self.ficheiro_selecionado = caminho
            self.label_ficheiro.configure(
                text=Path(caminho).name
            )

    def guardar_documento(self):
        titulo = self.entry_titulo.get().strip()
        assunto = self.entry_assunto.get().strip()
        descricao = self.text_descricao.get("1.0", "end").strip()
        referencia = self.novo_referencia
        data_texto = self.entry_data.get().strip()

        if not titulo:
            self.mensagem_erro("Validação", "O título é obrigatório.")
            return

        if not self.ficheiro_selecionado:
            self.mensagem_erro(
                "Validação",
                "Deve selecionar um ficheiro."
            )
            return

        try:
            from datetime import datetime
            data_documento = datetime.strptime(
                data_texto, "%Y-%m-%d"
            ).date()
        except ValueError:
            self.mensagem_erro(
                "Data inválida",
                "Utilize o formato AAAA-MM-DD."
            )
            return

        try:
            conteudo = Path(self.ficheiro_selecionado).read_bytes()
            caminho = Path(self.ficheiro_selecionado)

            hash_sha256 = hashlib.sha256(conteudo).hexdigest()
            extensao = caminho.suffix.lower().lstrip(".")
            mime_type = self.obter_mime(caminho)

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
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        referencia,
                        titulo,
                        assunto or None,
                        descricao or None,
                        self.dep_map_novo[
                            self.combo_departamento.get()
                        ],
                        self.tipo_map_novo[
                            self.combo_tipo.get()
                        ],
                        data_documento,
                        data_documento.year,
                        data_documento.month,
                        caminho.name,
                        extensao or None,
                        mime_type,
                        len(conteudo),
                        conteudo,
                        hash_sha256,
                        self.user["id"]
                    )
                )

                documento_id = cursor.lastrowid
                conn.commit()

                self.log(
                    "CRIAR_DOCUMENTO",
                    f"Documento '{titulo}' arquivado com referência {referencia}.",
                    documento_id
                )

                self.mensagem_info(
                    "Sucesso",
                    f"Documento {referencia} arquivado com sucesso!"
                )

                self.mostrar_pesquisa()

            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

        except Exception as erro:
            self.mensagem_erro(
                "Erro ao guardar documento",
                str(erro)
            )

    @staticmethod
    def obter_mime(caminho):
        import mimetypes
        mime, _ = mimetypes.guess_type(str(caminho))
        return mime or "application/octet-stream"

    # =====================================================
    # PESQUISA
    # =====================================================

    def mostrar_pesquisa(self):
        self.pagina_atual = "Pesquisar documentos"
        self.limpar_conteudo()
        self.titulo_pagina(
            "🔎 Pesquisar documentos",
            "Pesquisar e consultar documentos arquivados"
        )

        try:
            departamentos = options_from_table("departamentos")
            tipos = options_from_table("tipos_documento")
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            return

        dep_map = {"Todos": None}
        dep_map.update({x["nome"]: x["id"] for x in departamentos})

        tipo_map = {"Todos": None}
        tipo_map.update({x["nome"]: x["id"] for x in tipos})

        filtro = ctk.CTkFrame(self.content, corner_radius=12)
        filtro.pack(fill="x", padx=30, pady=5)

        ctk.CTkLabel(filtro, text="Pesquisar").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4)
        )
        self.pesquisa_texto = ctk.CTkEntry(
            filtro,
            placeholder_text="Referência, título ou assunto"
        )
        self.pesquisa_texto.grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 12)
        )

        ctk.CTkLabel(filtro, text="Departamento").grid(
            row=0, column=1, sticky="w", padx=12, pady=(12, 4)
        )
        self.pesquisa_dep = ctk.CTkComboBox(
            filtro,
            values=list(dep_map.keys())
        )
        self.pesquisa_dep.grid(
            row=1, column=1, sticky="ew", padx=12, pady=(0, 12)
        )
        self.pesquisa_dep.set("Todos")

        ctk.CTkLabel(filtro, text="Tipo").grid(
            row=0, column=2, sticky="w", padx=12, pady=(12, 4)
        )
        self.pesquisa_tipo = ctk.CTkComboBox(
            filtro,
            values=list(tipo_map.keys())
        )
        self.pesquisa_tipo.grid(
            row=1, column=2, sticky="ew", padx=12, pady=(0, 12)
        )
        self.pesquisa_tipo.set("Todos")

        anos = ["Todos"] + list(
            range(date.today().year, 1990, -1)
        )

        ctk.CTkLabel(filtro, text="Ano").grid(
            row=2, column=0, sticky="w", padx=12, pady=(4, 4)
        )
        self.pesquisa_ano = ctk.CTkComboBox(
            filtro,
            values=[str(x) for x in anos]
        )
        self.pesquisa_ano.grid(
            row=3, column=0, sticky="ew", padx=12, pady=(0, 12)
        )
        self.pesquisa_ano.set("Todos")

        ctk.CTkLabel(filtro, text="Mês").grid(
            row=2, column=1, sticky="w", padx=12, pady=(4, 4)
        )
        self.pesquisa_mes = ctk.CTkComboBox(
            filtro,
            values=["Todos"] + [str(x) for x in range(1, 13)]
        )
        self.pesquisa_mes.grid(
            row=3, column=1, sticky="ew", padx=12, pady=(0, 12)
        )
        self.pesquisa_mes.set("Todos")

        ctk.CTkLabel(filtro, text="Máximo de resultados").grid(
            row=2, column=2, sticky="w", padx=12, pady=(4, 4)
        )
        self.pesquisa_limite = ctk.CTkComboBox(
            filtro,
            values=["25", "50", "100", "250"]
        )
        self.pesquisa_limite.grid(
            row=3, column=2, sticky="ew", padx=12, pady=(0, 12)
        )
        self.pesquisa_limite.set("50")

        for i in range(3):
            filtro.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(
            filtro,
            text="🔎 Pesquisar",
            height=40,
            command=lambda: self.executar_pesquisa(
                dep_map, tipo_map
            )
        ).grid(
            row=1, column=3, rowspan=3,
            padx=15, pady=15
        )

        self.resultados_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )
        self.resultados_frame.pack(
            fill="both", expand=True, padx=20, pady=10
        )

        self.executar_pesquisa(dep_map, tipo_map)

    def executar_pesquisa(self, dep_map, tipo_map):
        for widget in self.resultados_frame.winfo_children():
            widget.destroy()

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

        texto = self.pesquisa_texto.get().strip()
        if texto:
            sql += """
                AND (
                    x.referencia LIKE %s
                    OR x.titulo LIKE %s
                    OR x.assunto LIKE %s
                )
            """
            pesquisa = f"%{texto}%"
            parametros.extend([pesquisa, pesquisa, pesquisa])

        dep_id = dep_map[self.pesquisa_dep.get()]
        if dep_id:
            sql += " AND x.departamento_id = %s"
            parametros.append(dep_id)

        tipo_id = tipo_map[self.pesquisa_tipo.get()]
        if tipo_id:
            sql += " AND x.tipo_documento_id = %s"
            parametros.append(tipo_id)

        ano = self.pesquisa_ano.get()
        if ano != "Todos":
            sql += " AND x.ano = %s"
            parametros.append(int(ano))

        mes = self.pesquisa_mes.get()
        if mes != "Todos":
            sql += " AND x.mes = %s"
            parametros.append(int(mes))

        limite = int(self.pesquisa_limite.get())

        sql += """
            ORDER BY x.data_documento DESC, x.id DESC
            LIMIT %s
        """
        parametros.append(limite)

        try:
            documentos = fetch_all(sql, tuple(parametros))
        except Exception as erro:
            self.mensagem_erro("Erro na pesquisa", str(erro))
            return

        ctk.CTkLabel(
            self.resultados_frame,
            text=f"{len(documentos)} documento(s) encontrado(s)",
            font=("Segoe UI", 15, "bold")
        ).pack(anchor="w", padx=10, pady=(0, 8))

        if not documentos:
            ctk.CTkLabel(
                self.resultados_frame,
                text="Nenhum processo encontrado."
            ).pack(anchor="w", padx=10)
            return

        colunas = [
            ("id", 60),
            ("referencia", 150),
            ("titulo", 260),
            ("assunto", 200),
            ("departamento", 170),
            ("tipo", 150),
            ("data_documento", 110),
            ("nome_ficheiro", 220),
            ("tamanho", 100),
        ]

        frame = ctk.CTkFrame(self.resultados_frame)
        frame.pack(fill="both", expand=True, padx=10)

        tree = ttk.Treeview(
            frame,
            columns=[x[0] for x in colunas],
            show="headings"
        )

        sy = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=tree.yview
        )
        sx = ttk.Scrollbar(
            frame,
            orient="horizontal",
            command=tree.xview
        )
        tree.configure(
            yscrollcommand=sy.set,
            xscrollcommand=sx.set
        )

        tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        for nome, largura in colunas:
            tree.heading(nome, text=nome.replace("_", " ").title())
            tree.column(nome, width=largura)

        for doc in documentos:
            valores = [
                doc["id"],
                doc["referencia"],
                doc["titulo"],
                doc["assunto"] or "",
                doc["departamento"],
                doc["tipo"],
                str(doc["data_documento"]),
                doc["nome_ficheiro"],
                format_size(doc["tamanho_bytes"])
            ]
            tree.insert("", "end", iid=str(doc["id"]), values=valores)

        tree.bind(
            "<Double-1>",
            lambda e: self.abrir_documento_selecionado(tree)
        )

        ctk.CTkButton(
            self.resultados_frame,
            text="👁️ Abrir documento selecionado",
            command=lambda: self.abrir_documento_selecionado(tree)
        ).pack(anchor="e", padx=10, pady=10)

    def abrir_documento_selecionado(self, tree):
        selecionado = tree.selection()
        if not selecionado:
            self.mensagem_aviso(
                "Seleção",
                "Selecione um documento."
            )
            return

        self.mostrar_detalhe_documento(
            int(selecionado[0])
        )

    # =====================================================
    # DETALHE / PRÉ-VISUALIZAÇÃO
    # =====================================================

    def mostrar_detalhe_documento(self, documento_id):
        try:
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
                (documento_id,)
            )
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            return

        if not processo:
            self.mensagem_aviso(
                "Documento",
                "Documento não encontrado."
            )
            return

        self.processo_atual = processo

        janela = ctk.CTkToplevel(self)
        janela.title("👁️ Pré-visualização - " + processo["referencia"])
        janela.geometry("1000x750")
        janela.transient(self)
        janela.grab_set()

        topo = ctk.CTkFrame(janela)
        topo.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            topo,
            text=processo["titulo"],
            font=("Segoe UI", 22, "bold")
        ).pack(anchor="w", padx=15, pady=(12, 3))

        ctk.CTkLabel(
            topo,
            text=(
                f"Referência: {processo['referencia']}    |    "
                f"Departamento: {processo['departamento']}    |    "
                f"Tipo: {processo['tipo']}"
            )
        ).pack(anchor="w", padx=15, pady=(0, 12))

        info = ctk.CTkFrame(janela)
        info.pack(fill="x", padx=15, pady=5)

        dados = [
            ("Data", processo["data_documento"]),
            ("Organização", f"{processo['ano']}/{processo['mes']:02d}"),
            ("Inserido por", processo["criado_por_nome"]),
            ("Ficheiro", processo["nome_ficheiro"]),
            ("Tamanho", format_size(processo["tamanho_bytes"])),
        ]

        for i, (campo, valor) in enumerate(dados):
            ctk.CTkLabel(
                info,
                text=f"{campo}: {valor}",
                anchor="w"
            ).grid(
                row=i // 3,
                column=i % 3,
                sticky="w",
                padx=15,
                pady=7
            )

        if processo["assunto"]:
            ctk.CTkLabel(
                janela,
                text=f"Assunto: {processo['assunto']}",
                anchor="w"
            ).pack(fill="x", padx=30, pady=5)

        if processo["descricao"]:
            ctk.CTkLabel(
                janela,
                text="Descrição / Observações:",
                font=("Segoe UI", 11, "bold")
            ).pack(anchor="w", padx=30, pady=(8, 2))

            txt = ctk.CTkTextbox(janela, height=80)
            txt.pack(fill="x", padx=30, pady=2)
            txt.insert("1.0", processo["descricao"])
            txt.configure(state="disabled")

        botoes = ctk.CTkFrame(janela, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            botoes,
            text="⬇️ Transferir ficheiro",
            command=lambda: self.transferir_documento(processo)
        ).pack(side="left", padx=5)

        if self.user["nivel"] == "admin":
            ctk.CTkButton(
                botoes,
                text="🗑️ Eliminar processo",
                fg_color="#b3261e",
                hover_color="#8f1d18",
                command=lambda: self.eliminar_documento(
                    processo, janela
                )
            ).pack(side="left", padx=5)

        preview = ctk.CTkFrame(janela)
        preview.pack(fill="both", expand=True, padx=15, pady=10)

        self.criar_preview(preview, processo)

    def criar_preview(self, parent, processo):
        mime = processo["mime_type"] or ""
        conteudo = processo["conteudo"]

        if mime == "application/pdf":
            # CTkinter não possui visualizador PDF nativo.
            # O botão abaixo abre o PDF com o programa padrão do sistema.
            ctk.CTkLabel(
                parent,
                text="📄 Documento PDF",
                font=("Segoe UI", 20, "bold")
            ).pack(pady=(60, 10))

            ctk.CTkLabel(
                parent,
                text=(
                    "A visualização interna de PDF depende de uma biblioteca "
                    "externa. Pode abrir o ficheiro no visualizador padrão."
                ),
                wraplength=650
            ).pack(pady=10)

            ctk.CTkButton(
                parent,
                text="📖 Abrir PDF",
                command=lambda: self.abrir_temporario(
                    processo
                )
            ).pack(pady=10)

        elif mime.startswith("image/"):
            try:
                from PIL import Image, ImageTk

                imagem = Image.open(BytesIO(conteudo))
                imagem.thumbnail((800, 450))

                photo = ImageTk.PhotoImage(imagem)
                label = tk.Label(parent, image=photo)
                label.image = photo
                label.pack(expand=True, pady=20)
            except Exception as erro:
                ctk.CTkLabel(
                    parent,
                    text=f"Erro ao apresentar imagem: {erro}"
                ).pack(pady=30)
        else:
            ctk.CTkLabel(
                parent,
                text=(
                    "A pré-visualização direta não está disponível "
                    "para este tipo de ficheiro."
                ),
                font=("Segoe UI", 14)
            ).pack(pady=(60, 10))

            ctk.CTkLabel(
                parent,
                text="Utilize o botão 'Transferir ficheiro'."
            ).pack()

    def transferir_documento(self, processo):
        caminho = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar ficheiro",
            initialfile=processo["nome_ficheiro"]
        )

        if not caminho:
            return

        try:
            Path(caminho).write_bytes(processo["conteudo"])
            self.mensagem_info(
                "Sucesso",
                "Ficheiro guardado com sucesso."
            )
        except Exception as erro:
            self.mensagem_erro(
                "Erro",
                f"Não foi possível guardar o ficheiro:\n{erro}"
            )

    def abrir_temporario(self, processo):
        try:
            pasta = Path(os.getenv("TEMP", ".")) / "arquivo_digital_preview"
            pasta.mkdir(exist_ok=True)

            caminho = pasta / processo["nome_ficheiro"]
            caminho.write_bytes(processo["conteudo"])

            if sys.platform.startswith("win"):
                os.startfile(str(caminho))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(caminho)])
            else:
                subprocess.Popen(["xdg-open", str(caminho)])
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))

    def eliminar_documento(self, processo, janela):
        confirmar = messagebox.askyesno(
            "Confirmar eliminação",
            "A eliminação do processo é definitiva.\n\n"
            f"Eliminar {processo['referencia']} - {processo['titulo']}?",
            parent=janela
        )

        if not confirmar:
            return

        try:
            execute(
                """
                DELETE FROM documentos
                WHERE id = %s
                """,
                (processo["id"],)
            )

            self.log(
                "ELIMINAR_DOCUMENTO",
                f"Processo {processo['referencia']} - "
                f"'{processo['titulo']}' eliminado."
            )

            janela.destroy()
            self.mensagem_info(
                "Sucesso",
                "Processo eliminado."
            )
            self.mostrar_pesquisa()

        except Exception as erro:
            self.mensagem_erro(
                "Erro ao eliminar",
                str(erro)
            )

    # =====================================================
    # DEPARTAMENTOS E TIPOS
    # =====================================================

    def mostrar_departamentos_tipos(self):
        if self.user["nivel"] != "admin":
            self.mensagem_erro(
                "Acesso",
                "Acesso não autorizado."
            )
            return

        self.limpar_conteudo()
        self.titulo_pagina(
            "⚙️ Departamentos e tipos de documento",
            "Gestão de classificações"
        )

        area = ctk.CTkFrame(self.content, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=25, pady=10)

        area.grid_columnconfigure(0, weight=1)
        area.grid_columnconfigure(1, weight=1)
        area.grid_rowconfigure(0, weight=1)

        self.criar_gestao_departamentos(area)
        self.criar_gestao_tipos(area)

    def criar_gestao_departamentos(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=0, column=0, sticky="nsew", padx=8)

        ctk.CTkLabel(
            card,
            text="🏢 Departamentos",
            font=("Segoe UI", 19, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))

        linha = ctk.CTkFrame(card, fg_color="transparent")
        linha.pack(fill="x", padx=20)

        entry = ctk.CTkEntry(
            linha,
            placeholder_text="Novo departamento"
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def adicionar():
            nome = entry.get().strip()
            if not nome:
                self.mensagem_erro(
                    "Validação",
                    "Introduza o nome do departamento."
                )
                return
            try:
                execute(
                    """
                    INSERT INTO departamentos (nome)
                    VALUES (%s)
                    """,
                    (nome,)
                )
                self.log("CRIAR_DEPARTAMENTO", nome)
                entry.delete(0, "end")
                self.mensagem_info(
                    "Sucesso",
                    "Departamento criado."
                )
                self.mostrar_departamentos_tipos()
            except Exception as erro:
                self.mensagem_erro("Erro", str(erro))

        ctk.CTkButton(
            linha,
            text="Adicionar",
            width=100,
            command=adicionar
        ).pack(side="right")

        try:
            departamentos = fetch_all(
                """
                SELECT id, nome, ativo, criado_em
                FROM departamentos
                ORDER BY nome
                """
            )
        except Exception as erro:
            departamentos = []
            ctk.CTkLabel(card, text=str(erro)).pack()

        if departamentos:
            self.criar_treeview(
                card,
                departamentos,
                [
                    ("id", 50),
                    ("nome", 220),
                    ("ativo", 80),
                    ("criado_em", 150)
                ],
                height=15
            )

    def criar_gestao_tipos(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=0, column=1, sticky="nsew", padx=8)

        ctk.CTkLabel(
            card,
            text="📁 Tipos de documento",
            font=("Segoe UI", 19, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))

        linha = ctk.CTkFrame(card, fg_color="transparent")
        linha.pack(fill="x", padx=20)

        entry = ctk.CTkEntry(
            linha,
            placeholder_text="Novo tipo de documento"
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def adicionar():
            nome = entry.get().strip()
            if not nome:
                self.mensagem_erro(
                    "Validação",
                    "Introduza o nome do tipo."
                )
                return
            try:
                execute(
                    """
                    INSERT INTO tipos_documento (nome)
                    VALUES (%s)
                    """,
                    (nome,)
                )
                self.log("CRIAR_TIPO_DOCUMENTO", nome)
                entry.delete(0, "end")
                self.mensagem_info(
                    "Sucesso",
                    "Tipo criado."
                )
                self.mostrar_departamentos_tipos()
            except Exception as erro:
                self.mensagem_erro("Erro", str(erro))

        ctk.CTkButton(
            linha,
            text="Adicionar",
            width=100,
            command=adicionar
        ).pack(side="right")

        try:
            tipos = fetch_all(
                """
                SELECT id, nome, ativo, criado_em
                FROM tipos_documento
                ORDER BY nome
                """
            )
        except Exception as erro:
            tipos = []
            ctk.CTkLabel(card, text=str(erro)).pack()

        if tipos:
            self.criar_treeview(
                card,
                tipos,
                [
                    ("id", 50),
                    ("nome", 220),
                    ("ativo", 80),
                    ("criado_em", 150)
                ],
                height=15
            )

    # =====================================================
    # UTILIZADORES
    # =====================================================

    def mostrar_utilizadores(self):
        if self.user["nivel"] != "admin":
            self.mensagem_erro(
                "Acesso",
                "Acesso não autorizado."
            )
            return

        self.limpar_conteudo()
        self.titulo_pagina(
            "👤 Gestão de Utilizadores",
            "Criar, editar e gerir utilizadores"
        )

        scroll = self.criar_scroll()

        criar_card = ctk.CTkFrame(scroll, corner_radius=12)
        criar_card.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            criar_card,
            text="➕ Criar novo utilizador",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=20, pady=(18, 12))

        form = ctk.CTkFrame(criar_card, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=5)

        campos = [
            ("Username *", "username"),
            ("Nome *", "nome"),
            ("Email", "email"),
            ("Palavra-passe *", "password"),
        ]

        entries = {}

        for i, (texto, chave) in enumerate(campos):
            col = i % 2
            row = i // 2

            ctk.CTkLabel(
                form,
                text=texto
            ).grid(
                row=row * 2,
                column=col,
                sticky="w",
                padx=8,
                pady=(5, 3)
            )

            entry = ctk.CTkEntry(
                form,
                height=38,
                show="*" if chave == "password" else None
            )
            entry.grid(
                row=row * 2 + 1,
                column=col,
                sticky="ew",
                padx=8,
                pady=(0, 10)
            )
            entries[chave] = entry

        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            form,
            text="Nível"
        ).grid(row=4, column=0, sticky="w", padx=8)

        nivel_combo = ctk.CTkComboBox(
            form,
            values=["utilizador", "admin"]
        )
        nivel_combo.grid(
            row=5, column=0, sticky="ew", padx=8, pady=(0, 12)
        )
        nivel_combo.set("utilizador")

        def criar():
            username = entries["username"].get().strip()
            nome = entries["nome"].get().strip()
            email = entries["email"].get().strip()
            password = entries["password"].get()
            nivel = nivel_combo.get()

            if not username:
                self.mensagem_erro("Validação", "Username obrigatório.")
                return
            if not nome:
                self.mensagem_erro("Validação", "Nome obrigatório.")
                return
            if not password:
                self.mensagem_erro(
                    "Validação",
                    "Palavra-passe obrigatória."
                )
                return
            if len(password) < 6:
                self.mensagem_erro(
                    "Validação",
                    "A palavra-passe deve ter pelo menos 6 caracteres."
                )
                return

            try:
                existente = fetch_one(
                    """
                    SELECT id FROM usuarios
                    WHERE username = %s
                    """,
                    (username,)
                )

                if existente:
                    self.mensagem_erro(
                        "Utilizador",
                        "Este username já existe."
                    )
                    return

                password_hash = hash_password(password)

                execute(
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
                    (%s, %s, %s, %s, %s, TRUE)
                    """,
                    (
                        username,
                        password_hash,
                        nome,
                        email or None,
                        nivel
                    )
                )

                self.log(
                    "CRIAR_UTILIZADOR",
                    f"Utilizador '{username}' criado."
                )

                self.mensagem_info(
                    "Sucesso",
                    "Utilizador criado com sucesso."
                )
                self.mostrar_utilizadores()

            except Exception as erro:
                self.mensagem_erro(
                    "Erro ao criar utilizador",
                    str(erro)
                )

        ctk.CTkButton(
            criar_card,
            text="💾 Criar utilizador",
            command=criar
        ).pack(anchor="e", padx=20, pady=(5, 20))

        # -------------------------------------------------
        # LISTA
        # -------------------------------------------------

        ctk.CTkLabel(
            scroll,
            text="👥 Utilizadores cadastrados",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=10, pady=(20, 8))

        try:
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
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            return

        if not users:
            ctk.CTkLabel(
                scroll,
                text="Não existem utilizadores cadastrados."
            ).pack(anchor="w", padx=10)
            return

        self.users_cache = users

        tree = self.criar_treeview(
            scroll,
            users,
            [
                ("id", 55),
                ("username", 130),
                ("nome", 200),
                ("email", 220),
                ("nivel", 110),
                ("ativo", 70),
                ("criado_em", 150),
                ("ultimo_acesso", 160)
            ],
            height=9
        )

        ctk.CTkButton(
            scroll,
            text="✏️ Editar utilizador selecionado",
            command=lambda: self.editar_utilizador_tree(tree)
        ).pack(anchor="e", padx=10, pady=10)

    def editar_utilizador_tree(self, tree):
        selecionado = tree.selection()

        if not selecionado:
            self.mensagem_aviso(
                "Seleção",
                "Selecione um utilizador."
            )
            return

        # Obter os valores da linha selecionada
        valores = tree.item(
            selecionado[0],
            "values"
        )

        if not valores:
            self.mensagem_aviso(
                "Seleção",
                "Não foi possível obter os dados do utilizador."
            )
            return

        try:
            # O ID está na primeira coluna da tabela
            usuario_id = int(valores[0])

        except (
            ValueError,
            TypeError,
            IndexError
        ):
            self.mensagem_erro(
                "Erro",
                "O ID do utilizador selecionado é inválido."
            )
            return

        # Abrir o utilizador correto
        self.editar_utilizador(usuario_id)

    def editar_utilizador(self, usuario_id):
        dados_user = fetch_one(
            """
            SELECT id, username, nome, email, nivel, ativo
            FROM usuarios
            WHERE id = %s
            """,
            (usuario_id,)
        )

        if not dados_user:
            self.mensagem_aviso(
                "Utilizador",
                "Utilizador não encontrado."
            )
            return

        janela = ctk.CTkToplevel(self)
        janela.title("✏️ Editar utilizador")
        janela.geometry("600x620")
        janela.transient(self)
        janela.grab_set()

        ctk.CTkLabel(
            janela,
            text="✏️ Editar utilizador",
            font=("Segoe UI", 22, "bold")
        ).pack(pady=(20, 15))

        form = ctk.CTkFrame(janela)
        form.pack(fill="both", expand=True, padx=25, pady=10)

        def campo(rotulo, valor="", password=False):
            ctk.CTkLabel(
                form,
                text=rotulo
            ).pack(anchor="w", padx=20, pady=(12, 3))

            e = ctk.CTkEntry(
                form,
                height=38,
                show="*" if password else None
            )
            e.pack(fill="x", padx=20)
            e.insert(0, "" if valor is None else str(valor))
            return e

        username = campo(
            "Nome de utilizador *",
            dados_user["username"]
        )
        nome = campo("Nome *", dados_user["nome"])
        email = campo("Email", dados_user["email"] or "")

        ctk.CTkLabel(form, text="Nível").pack(
            anchor="w", padx=20, pady=(12, 3)
        )

        nivel = ctk.CTkComboBox(
            form,
            values=["admin", "utilizador"],
            height=38
        )
        nivel.pack(fill="x", padx=20)
        nivel.set(
            dados_user["nivel"]
            if dados_user["nivel"] in ["admin", "utilizador"]
            else "utilizador"
        )

        nova_senha = campo(
            "Nova palavra-passe (deixe em branco para não alterar)",
            "",
            True
        )
        confirmar = campo(
            "Confirmar nova palavra-passe",
            "",
            True
        )

        ativo = tk.BooleanVar(
            value=bool(dados_user["ativo"])
        )

        ctk.CTkCheckBox(
            form,
            text="Utilizador ativo",
            variable=ativo
        ).pack(anchor="w", padx=20, pady=15)

        botoes = ctk.CTkFrame(
            janela,
            fg_color="transparent"
        )
        botoes.pack(fill="x", padx=25, pady=15)

        def atualizar():
            novo_username = username.get().strip()
            novo_nome = nome.get().strip()
            novo_email = email.get().strip()
            novo_nivel = nivel.get()
            senha = nova_senha.get()
            conf = confirmar.get()
            estado = ativo.get()

            if not novo_username:
                self.mensagem_erro(
                    "Validação",
                    "O username é obrigatório."
                )
                return

            if not novo_nome:
                self.mensagem_erro(
                    "Validação",
                    "O nome é obrigatório."
                )
                return

            if senha and len(senha) < 6:
                self.mensagem_erro(
                    "Validação",
                    "A nova palavra-passe deve ter pelo menos 6 caracteres."
                )
                return

            if senha and senha != conf:
                self.mensagem_erro(
                    "Validação",
                    "A nova palavra-passe e a confirmação não coincidem."
                )
                return

            try:
                existente = fetch_one(
                    """
                    SELECT id FROM usuarios
                    WHERE username = %s AND id <> %s
                    """,
                    (novo_username, usuario_id)
                )

                if existente:
                    self.mensagem_erro(
                        "Username",
                        "Este username já está a ser utilizado."
                    )
                    return

                if senha:
                    novo_hash = hash_password(senha)
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
                            novo_username,
                            novo_nome,
                            novo_email or None,
                            novo_nivel,
                            estado,
                            novo_hash,
                            usuario_id
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
                            novo_username,
                            novo_nome,
                            novo_email or None,
                            novo_nivel,
                            estado,
                            usuario_id
                        )
                    )

                self.log(
                    "EDITAR_UTILIZADOR",
                    f"Utilizador '{dados_user['username']}' alterado "
                    f"para '{novo_username}'."
                )

                janela.destroy()
                self.mensagem_info(
                    "Sucesso",
                    "Utilizador atualizado com sucesso."
                )
                self.mostrar_utilizadores()

            except Exception as erro:
                self.mensagem_erro(
                    "Erro ao atualizar",
                    str(erro)
                )

        def excluir():
            if usuario_id == self.user["id"]:
                self.mensagem_erro(
                    "Operação não permitida",
                    "Não é possível excluir o utilizador "
                    "que está atualmente autenticado."
                )
                return

            confirmar_delete = messagebox.askyesno(
                "Confirmar exclusão",
                f"Excluir o utilizador '{dados_user['username']}'?",
                parent=janela
            )

            if not confirmar_delete:
                return

            try:
                execute(
                    """
                    DELETE FROM usuarios
                    WHERE id = %s
                    """,
                    (usuario_id,)
                )

                self.log(
                    "ELIMINAR_UTILIZADOR",
                    f"Utilizador '{dados_user['username']}' "
                    f"({dados_user['nome']}) eliminado."
                )

                janela.destroy()
                self.mensagem_info(
                    "Sucesso",
                    "Utilizador excluído com sucesso."
                )
                self.mostrar_utilizadores()

            except Exception as erro:
                self.mensagem_erro(
                    "Erro ao excluir",
                    str(erro)
                )

        ctk.CTkButton(
            botoes,
            text="💾 Atualizar",
            command=atualizar
        ).pack(side="left", padx=5, expand=True, fill="x")

        ctk.CTkButton(
            botoes,
            text="🗑️ Excluir",
            fg_color="#b3261e",
            hover_color="#8f1d18",
            command=excluir
        ).pack(side="left", padx=5, expand=True, fill="x")

    # =====================================================
    # DEFINIÇÕES
    # =====================================================

    def mostrar_definicoes(self):
        if self.user["nivel"] != "utilizador":
            self.mensagem_erro(
                "Acesso",
                "Acesso não autorizado."
            )
            return

        self.limpar_conteudo()
        self.titulo_pagina(
            "⚙️ Definições",
            "Configurações da conta"
        )

        card = ctk.CTkFrame(self.content, corner_radius=12)
        card.pack(
            fill="x",
            padx=80,
            pady=20
        )

        ctk.CTkLabel(
            card,
            text="🔐 Alterar palavra-passe",
            font=("Segoe UI", 20, "bold")
        ).pack(anchor="w", padx=25, pady=(25, 5))

        ctk.CTkLabel(
            card,
            text=f"Utilizador: {self.user['username']}"
        ).pack(anchor="w", padx=25, pady=(0, 15))

        atual = ctk.CTkEntry(
            card,
            width=500,
            height=40,
            placeholder_text="Palavra-passe atual *",
            show="*"
        )
        atual.pack(anchor="w", padx=25, pady=7)

        nova = ctk.CTkEntry(
            card,
            width=500,
            height=40,
            placeholder_text="Nova palavra-passe *",
            show="*"
        )
        nova.pack(anchor="w", padx=25, pady=7)

        confirmar = ctk.CTkEntry(
            card,
            width=500,
            height=40,
            placeholder_text="Confirmar nova palavra-passe *",
            show="*"
        )
        confirmar.pack(anchor="w", padx=25, pady=7)

        def alterar():
            senha_atual = atual.get()
            nova_senha = nova.get()
            conf = confirmar.get()

            if not senha_atual:
                self.mensagem_erro(
                    "Validação",
                    "Introduza a palavra-passe atual."
                )
                return

            if not nova_senha:
                self.mensagem_erro(
                    "Validação",
                    "Introduza a nova palavra-passe."
                )
                return

            if not conf:
                self.mensagem_erro(
                    "Validação",
                    "Confirme a nova palavra-passe."
                )
                return

            if nova_senha != conf:
                self.mensagem_erro(
                    "Validação",
                    "A nova palavra-passe e a confirmação não coincidem."
                )
                return

            if len(nova_senha) < 6:
                self.mensagem_erro(
                    "Validação",
                    "A nova palavra-passe deve ter pelo menos 6 caracteres."
                )
                return

            if nova_senha == senha_atual:
                self.mensagem_erro(
                    "Validação",
                    "A nova palavra-passe deve ser diferente da atual."
                )
                return

            try:
                utilizador = fetch_one(
                    """
                    SELECT id, username, password_hash
                    FROM usuarios
                    WHERE id = %s
                    """,
                    (self.user["id"],)
                )

                if not utilizador:
                    self.mensagem_erro(
                        "Erro",
                        "Utilizador não encontrado."
                    )
                    return

                if not verify_password(
                    senha_atual,
                    utilizador["password_hash"]
                ):
                    self.mensagem_erro(
                        "Palavra-passe",
                        "A palavra-passe atual está incorreta."
                    )
                    return

                nova_hash = hash_password(nova_senha)

                execute(
                    """
                    UPDATE usuarios
                    SET password_hash = %s
                    WHERE id = %s
                    """,
                    (nova_hash, self.user["id"])
                )

                self.log(
                    "ALTERAR_SENHA",
                    f"Palavra-passe alterada pelo utilizador "
                    f"'{self.user['username']}'."
                )

                atual.delete(0, "end")
                nova.delete(0, "end")
                confirmar.delete(0, "end")

                self.mensagem_info(
                    "Sucesso",
                    "Palavra-passe alterada com sucesso!\n\n"
                    "Por segurança, termine a sessão e entre novamente "
                    "com a nova palavra-passe."
                )

            except Exception as erro:
                self.mensagem_erro(
                    "Erro ao alterar palavra-passe",
                    str(erro)
                )

        ctk.CTkButton(
            card,
            text="🔐 Alterar palavra-passe",
            height=42,
            command=alterar
        ).pack(anchor="w", padx=25, pady=(15, 25))

    # =====================================================
    # HISTÓRICO
    # =====================================================

    def mostrar_historico(self):
        if self.user["nivel"] != "admin":
            self.mensagem_erro(
                "Acesso",
                "Acesso não autorizado."
            )
            return

        self.limpar_conteudo()
        self.titulo_pagina(
            "📜 Histórico de operações",
            "Registo das operações realizadas no sistema"
        )

        try:
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
                ORDER BY l.data_hora DESC
                LIMIT 500
                """
            )
        except Exception as erro:
            self.mensagem_erro("Erro", str(erro))
            return

        if not logs:
            ctk.CTkLabel(
                self.content,
                text="Não existem operações registadas."
            ).pack(anchor="w", padx=40, pady=20)
            return

        scroll = self.criar_scroll()

        self.criar_treeview(
            scroll,
            logs,
            [
                ("id", 50),
                ("data_hora", 160),
                ("username", 120),
                ("nome", 180),
                ("operacao", 180),
                ("documento_id", 100),
                ("descricao", 500)
            ],
            height=20
        )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":
    app = ArquivoDigitalApp()
    app.mainloop()