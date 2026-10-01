
import json
import os
import sys
import sqlite3
import shutil
import zipfile
import subprocess
import urllib.request
import urllib.error
import threading
import tempfile
from tkinter import simpledialog
from banco import configure_connection, checkpoint
from armazenamento import safe_unlink
from pdf import safe_pdf_filename
from telas import active_nav_config
from atualizador import (
    check_for_update, download_update, load_repository, save_repository,
    repository_configured, CONFIG_PATH as UPDATE_CONFIG_PATH
)
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

APP_NAME = "RH Fácil"
VERSION = "v0.3.8"
TRASH_RETENTION_DAYS = 30
DEVELOPER = "Desenvolvido por João Trindade"

ROOT = Path(__file__).resolve().parent
INSTALL_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))
BUNDLED_DB_PATH = RESOURCE_ROOT / "rh_facil.db"

def _app_config_dir():
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "RHFacil"
    return Path.home() / ".rhfacil"

APP_CONFIG_DIR = _app_config_dir()
APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_SETTINGS_FILE = APP_CONFIG_DIR / "storage.json"

def _default_data_dir():
    return Path.home() / "Documents" / "RH Fácil"

def _load_data_dir():
    try:
        if STORAGE_SETTINGS_FILE.exists():
            raw=json.loads(STORAGE_SETTINGS_FILE.read_text(encoding="utf-8"))
            value=(raw.get("data_dir") or "").strip()
            if value:
                return Path(value)
    except Exception:
        pass
    return _default_data_dir()

DATA_DIR = _load_data_dir()
DB_PATH = DATA_DIR / "Banco de Dados" / "rh_facil.db"
PDF_DIR = DATA_DIR / "Fichas PDF"
CURRICULOS_DIR = DATA_DIR / "Currículos"
BACKUP_DIR = DATA_DIR / "Backups"
DRAFT_PATH = DATA_DIR / "rascunho_admissao.json"

def _set_data_paths(path):
    global DATA_DIR, DB_PATH, PDF_DIR, CURRICULOS_DIR, BACKUP_DIR, DRAFT_PATH
    DATA_DIR=Path(path)
    DB_PATH=DATA_DIR / "Banco de Dados" / "rh_facil.db"
    PDF_DIR=DATA_DIR / "Fichas PDF"
    CURRICULOS_DIR=DATA_DIR / "Currículos"
    BACKUP_DIR=DATA_DIR / "Backups"
    DRAFT_PATH=DATA_DIR / "rascunho_admissao.json"

def _legacy_data_dir():
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "RHFacil"
    return None

def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CURRICULOS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Migra automaticamente o banco do executável de teste anterior,
    # caso seja a primeira abertura da nova estrutura em Documentos.
    if not DB_PATH.exists():
        legacy=_legacy_data_dir()
        legacy_db=(legacy / "rh_facil.db") if legacy else None
        if legacy_db and legacy_db.exists() and legacy_db.resolve() != DB_PATH.resolve():
            shutil.copy2(legacy_db, DB_PATH)
            for old_name in ("fichas_geradas","Fichas PDF"):
                old_folder=legacy / old_name
                if old_folder.exists():
                    shutil.copytree(old_folder, PDF_DIR, dirs_exist_ok=True)
        elif BUNDLED_DB_PATH.exists() and BUNDLED_DB_PATH.resolve() != DB_PATH.resolve():
            shutil.copy2(BUNDLED_DB_PATH, DB_PATH)

ensure_storage()

# ---------------------- VISUAL ----------------------
BG = "#eceff1"
CARD = "#f8f9fa"
SOFT = "#e3e7ea"
BORDER = "#b8c0c7"
TEXT = "#202326"
LABEL = "#25292d"
MUTED = "#5d646a"
SIDEBAR = "#101827"
SIDEBAR_HOVER = "#1a2535"
SIDEBAR_ACTIVE = "#2563eb"
SIDEBAR_BORDER = "#26344a"
SIDEBAR_TEXT = "#f4f7fb"
SIDEBAR_MUTED = "#9fb0c7"
ACCENT = "#4e5358"
ACCENT_HOVER = "#3f4448"
GREEN = "#268653"
RED = "#b23b3b"
AMBER = "#9b6b00"

FONT_TITLE = ("Segoe UI", 28, "bold")
FONT_H2 = ("Segoe UI", 19, "bold")
FONT_GROUP = ("Segoe UI", 16, "bold")
FONT_LABEL = ("Segoe UI", 14, "bold")
FONT_INPUT = ("Segoe UI", 15)
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)

# Tipografia global da navegação: mesma família, peso e proporção em todos os itens.
FONT_NAV = ("Segoe UI", 15)
FONT_NAV_SECTION = ("Segoe UI", 13, "bold")
FONT_BRAND = ("Segoe UI", 28, "bold")
FONT_FOOTER = ("Segoe UI", 11)
NAV_ICON_SIZE = (24, 24)
BRAND_ICON_SIZE = (42, 42)

UF_NAMES = {
    "AC":"Acre","AL":"Alagoas","AP":"Amapá","AM":"Amazonas","BA":"Bahia","CE":"Ceará",
    "DF":"Distrito Federal","ES":"Espírito Santo","GO":"Goiás","MA":"Maranhão","MT":"Mato Grosso",
    "MS":"Mato Grosso do Sul","MG":"Minas Gerais","PA":"Pará","PB":"Paraíba","PR":"Paraná",
    "PE":"Pernambuco","PI":"Piauí","RJ":"Rio de Janeiro","RN":"Rio Grande do Norte",
    "RS":"Rio Grande do Sul","RO":"Rondônia","RR":"Roraima","SC":"Santa Catarina",
    "SP":"São Paulo","SE":"Sergipe","TO":"Tocantins"
}

# Pequena base inicial para o sistema funcionar offline imediatamente.
# Ao selecionar um estado, o sistema tenta consultar o IBGE e salva todos os municípios daquele estado no SQLite.
SEED_CITIES = {
    "RO":["Ji-Paraná","Porto Velho","Ariquemes","Vilhena","Cacoal","Rolim de Moura","Jaru","Ouro Preto do Oeste",
          "Pimenta Bueno","Guajará-Mirim","Machadinho d'Oeste","Buritis","Espigão d'Oeste","Alta Floresta d'Oeste",
          "Presidente Médici","Nova Brasilândia d'Oeste","São Miguel do Guaporé","Colorado do Oeste","Cerejeiras"],
    "AC":["Rio Branco","Cruzeiro do Sul","Sena Madureira","Tarauacá"],
    "AM":["Manaus","Parintins","Itacoatiara","Manacapuru"],
    "MT":["Cuiabá","Várzea Grande","Rondonópolis","Sinop"],
    "MS":["Campo Grande","Dourados","Três Lagoas","Corumbá"],
    "GO":["Goiânia","Anápolis","Aparecida de Goiânia","Rio Verde"],
    "DF":["Brasília"],
    "SP":["São Paulo","Campinas","Santos","Ribeirão Preto","São José dos Campos","Sorocaba"],
    "RJ":["Rio de Janeiro","Niterói","Duque de Caxias","Nova Iguaçu","Petrópolis"],
    "MG":["Belo Horizonte","Uberlândia","Contagem","Juiz de Fora","Betim"],
    "PR":["Curitiba","Londrina","Maringá","Cascavel","Ponta Grossa"],
    "SC":["Florianópolis","Joinville","Blumenau","Chapecó","Itajaí"],
    "RS":["Porto Alegre","Caxias do Sul","Pelotas","Canoas","Santa Maria"],
    "BA":["Salvador","Feira de Santana","Vitória da Conquista","Camaçari"],
    "PE":["Recife","Jaboatão dos Guararapes","Olinda","Caruaru"],
    "CE":["Fortaleza","Caucaia","Juazeiro do Norte","Sobral"],
    "PA":["Belém","Ananindeua","Santarém","Marabá"],
    "MA":["São Luís","Imperatriz","Caxias","Timon"],
    "PB":["João Pessoa","Campina Grande","Santa Rita"],
    "RN":["Natal","Mossoró","Parnamirim"],
    "AL":["Maceió","Arapiraca"],
    "SE":["Aracaju","Nossa Senhora do Socorro"],
    "PI":["Teresina","Parnaíba"],
    "ES":["Vitória","Vila Velha","Serra","Cariacica"],
    "TO":["Palmas","Araguaína","Gurupi"],
    "RR":["Boa Vista"],
    "AP":["Macapá","Santana"]
}

DEFAULT_NO = {
    "estrangeiro","orgao_classe","possui_cnh","residencia_propria","fgts_imovel",
    "deficiencia_motora","deficiencia_visual","deficiencia_auditiva","reabilitado",
    "outros_vinculos","outra_remuneracao","sindicato","pensao","consignado","vale_transporte"
}


REQUIRED_KEYS = {
    # Dados pessoais
    "nome","cep","endereco","bairro","uf","cidade","telefone","primeiro_emprego",
    "data_nascimento","uf_nascimento","cidade_nascimento","sexo","raca_cor",
    "estado_civil","municipio_nascimento","nome_mae",

    # Documentos
    "cpf","pis","carteira_digital","rg_numero","rg_orgao","rg_expedicao","possui_cnh",
    "ctps_numero","ctps_serie_uf","ctps_emissao",
    "rne_orgao_data","chegada_brasil",
    "orgao_classe_numero","orgao_classe_emissor_data",
    "cnh_numero","cnh_categoria","cnh_expedicao","cnh_validade","cnh_primeira_habilitacao",

    # Dependentes / condições
    "residencia_propria","deficiencia_motora","deficiencia_visual","deficiencia_auditiva","reabilitado",

    # Trabalho
    "outros_vinculos","outra_remuneracao","sindicato","pensao","consignado",
    "data_admissao","salario","funcao","horario_trabalho","contrato_experiencia",
    "grau_instrucao","vale_transporte","outros_vinculos_cnpj","sindicato_cnpj",
    "pensao_nome","pensao_cpf","pensao_banco","pensao_agencia","pensao_conta",
}

# ---------------------- DATABASE ----------------------
def db():
    return configure_connection(sqlite3.connect(DB_PATH, timeout=8))

def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS empresas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        razao_social TEXT NOT NULL,
        nome_fantasia TEXT,
        cnpj TEXT,
        endereco TEXT,
        cidade TEXT,
        uf TEXT,
        telefone TEXT,
        ativa INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS horarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        horario TEXT NOT NULL,
        ativo INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS cargos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        ativo INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS municipios(
        uf TEXT NOT NULL,
        cidade TEXT NOT NULL,
        fonte TEXT DEFAULT 'local',
        PRIMARY KEY(uf,cidade)
    );

    CREATE TABLE IF NOT EXISTS admissoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        nome TEXT,
        cpf TEXT,
        funcao TEXT,
        data_admissao TEXT,
        dados_json TEXT NOT NULL,
        FOREIGN KEY(empresa_id) REFERENCES empresas(id)
    );
    """)
    # Migrações incrementais para manter compatibilidade com bancos anteriores.
    def ensure_column(table, column, definition):
        existing={r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    for col, definition in [
        ("bairro","TEXT"),("cep","TEXT"),("complemento","TEXT")
    ]:
        ensure_column("empresas",col,definition)

    for col, definition in [
        ("dias_json","TEXT"),
        ("entrada","TEXT"),("saida_intervalo","TEXT"),("retorno","TEXT"),("saida","TEXT"),
        ("segunda_saida","TEXT"),
        ("sabado_entrada","TEXT"),("sabado_saida","TEXT"),
        ("padrao","INTEGER NOT NULL DEFAULT 0")
    ]:
        ensure_column("horarios",col,definition)

    for col, definition in [
        ("excluido_em","TEXT"),
        ("pdf_path","TEXT"),
        ("pdf_excluido","INTEGER NOT NULL DEFAULT 0")
    ]:
        ensure_column("admissoes",col,definition)

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS historico_admissoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admissao_id INTEGER,
        data_hora TEXT NOT NULL,
        acao TEXT NOT NULL,
        detalhes TEXT,
        nome TEXT,
        cpf TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_admissoes_cpf ON admissoes(cpf);
    CREATE INDEX IF NOT EXISTS idx_admissoes_nome ON admissoes(nome);
    CREATE INDEX IF NOT EXISTS idx_admissoes_funcao ON admissoes(funcao);
    CREATE INDEX IF NOT EXISTS idx_admissoes_data_admissao ON admissoes(data_admissao);
    CREATE INDEX IF NOT EXISTS idx_admissoes_excluido ON admissoes(excluido_em);
    CREATE INDEX IF NOT EXISTS idx_historico_admissao ON historico_admissoes(admissao_id);
    CREATE INDEX IF NOT EXISTS idx_historico_data ON historico_admissoes(data_hora);
    """)

    # Seeds de municípios.
    for uf, cidades in SEED_CITIES.items():
        for cidade in cidades:
            cur.execute(
                "INSERT OR IGNORE INTO municipios(uf,cidade,fonte) VALUES(?,?,?)",
                (uf,cidade,"local")
            )

    # Horário padrão solicitado:
    # Segunda: 06:45-11:00 / 13:00-17:45
    # Terça a sexta: 06:45-11:00 / 13:00-17:30
    default_days=json.dumps(["SEG","TER","QUA","QUI","SEX"])
    default_text="Seg: 06:45-11:00 / 13:00-17:45 | Ter-Sex: 06:45-11:00 / 13:00-17:30"

    cur.execute(
        """INSERT OR IGNORE INTO horarios(
               id,nome,horario,ativo,dias_json,entrada,saida_intervalo,retorno,saida,
               segunda_saida,sabado_entrada,sabado_saida,padrao
           ) VALUES(
               1,'PADRÃO',?,1,?,
               '06:45','11:00','13:00','17:30','17:45','','',1
           )""",
        (default_text,default_days)
    )
    cur.execute("UPDATE horarios SET padrao=0 WHERE id<>1")
    cur.execute(
        """UPDATE horarios SET
               nome='PADRÃO',
               horario=?,
               ativo=1,
               dias_json=?,
               entrada='06:45',
               saida_intervalo='11:00',
               retorno='13:00',
               saida='17:30',
               segunda_saida='17:45',
               sabado_entrada='',
               sabado_saida='',
               padrao=1
           WHERE id=1""",
        (default_text,default_days)
    )

    # Nenhuma empresa real é incluída no código-fonte público.
    # O administrador cadastra as empresas pela tela CONFIGURAÇÕES > EMPRESAS.
    con.commit()
    con.close()

def rows(sql, params=()):
    con = db()
    data = con.execute(sql, params).fetchall()
    con.close()
    return data

def execute(sql, params=()):
    con = db()
    cur = con.execute(sql, params)
    con.commit()
    last = cur.lastrowid
    con.close()
    return last

def checkpoint_db():
    try:
        con=db()
        checkpoint(con)
        con.close()
    except Exception:
        pass

# ---------------------- VALIDATION ----------------------
from validacoes import only_digits, cpf_valid, cnpj_valid

# ---------------------- WIDGET HELPERS ----------------------
from widgets import SegmentedField, PhoneField, YesNoField, MoneyField, MeasureField

# ---------------------- APP ----------------------
class RHFacil:
    STEPS = ["Dados pessoais","Documentos","Dependentes","Trabalho","Revisão"]

    def __init__(self):
        # CustomTkinter já gerencia HighDPI automaticamente no Windows.
        # Não sobrescrevemos a política de DPI para evitar que notebooks com
        # escala de 125%/150% exibam o menu menor que o esperado.
        init_db()
        self.purge_expired_trash()
        ctk.set_appearance_mode("light")
        self.root=ctk.CTk()
        self.root.title(f"{APP_NAME} · {VERSION}")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        window_w = min(1280, max(1100, int(screen_w * 0.92)))
        window_h = min(780, max(650, int(screen_h * 0.88)))
        self.root.geometry(f"{window_w}x{window_h}")
        self.root.minsize(1000,650)

        self.vars={}
        self.field_labels={}
        self.dependentes=[]
        self.consignados=[]
        self.current_step=0
        self.company_map={}
        self.step_buttons=[]
        self.step_canvas=None
        self.step_frame=None
        self.restoring=False
        self.current_edit_id=None
        self.field_labels={}
        self.nav_buttons={}
        self._autosave_job=None
        self._status_job=None
        self._city_request_tokens={"cidade":0,"cidade_nascimento":0}
        self._cep_request_token=0
        self._update_check_in_progress=False
        self._update_prompted=False

        self.build_shell()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.show_dashboard()
        self.root.after(1400, self.check_updates_on_startup)

    # -------- base layout --------
    def build_shell(self):
        self.root.grid_columnconfigure(1,weight=1)
        self.root.grid_rowconfigure(0,weight=1)

        side=ctk.CTkFrame(
            self.root,width=245,corner_radius=0,fg_color=SIDEBAR,
            border_width=0
        )
        side.grid(row=0,column=0,sticky="nsew")
        side.grid_propagate(False)
        side.grid_rowconfigure(7,weight=1)

        brand=ctk.CTkFrame(side,fg_color="transparent")
        brand.grid(row=0,column=0,padx=18,pady=(22,18),sticky="ew")
        brand.grid_columnconfigure(1,weight=1)

        ctk.CTkLabel(
            brand,text="●",text_color="#60a5fa",font=("Segoe UI",28,"bold")
        ).grid(row=0,column=0,padx=(0,10),sticky="w")
        ctk.CTkLabel(
            brand,text="RH Fácil",text_color=SIDEBAR_TEXT,font=FONT_BRAND
        ).grid(row=0,column=1,sticky="w")

        ctk.CTkFrame(
            side,height=1,fg_color=SIDEBAR_BORDER,corner_radius=0
        ).grid(row=1,column=0,padx=18,pady=(0,14),sticky="ew")

        nav=[
            ("⌂   Visão Geral",self.show_dashboard,"dashboard"),
            ("＋   Nova Admissão",self.show_new_admission,"new"),
            ("☷   Admissões Salvas",self.show_employees,"employees"),
            ("▱   Lixeira",self.show_trash,"trash"),
            ("▤   Fichas PDF",self.show_generated,"pdf"),
            ("⚙   Configurações",self.show_settings,"settings"),
        ]

        for i,(label,cmd,key) in enumerate(nav,2):
            b=ctk.CTkButton(
                side,
                text=label,
                command=cmd,
                height=46,
                corner_radius=8,
                border_spacing=12,
                fg_color="transparent",
                hover_color=SIDEBAR_HOVER,
                text_color=SIDEBAR_TEXT,
                anchor="w",
                font=FONT_NAV
            )
            b.grid(row=i,column=0,padx=12,pady=3,sticky="ew")
            self.nav_buttons[key]=b

        ctk.CTkFrame(
            side,height=1,fg_color=SIDEBAR_BORDER,corner_radius=0
        ).grid(row=8,column=0,padx=18,pady=(0,10),sticky="ew")

        footer=ctk.CTkFrame(side,fg_color="transparent")
        footer.grid(row=9,column=0,padx=18,pady=(0,18),sticky="sw")

        ctk.CTkLabel(
            footer,text=DEVELOPER,text_color=SIDEBAR_MUTED,
            justify="left",font=FONT_FOOTER
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,text=VERSION,text_color="#60a5fa",
            justify="left",font=("Segoe UI",11,"bold")
        ).pack(anchor="w",pady=(2,0))

        self.content=ctk.CTkFrame(self.root,fg_color=BG,corner_radius=0)
        self.content.grid(row=0,column=1,sticky="nsew")
        self.content.grid_columnconfigure(0,weight=1)
        self.content.grid_rowconfigure(1,weight=1)

        self.status_bar=ctk.CTkFrame(self.content,fg_color="#e2e6e9",corner_radius=0,height=30)
        self.status_bar.grid(row=2,column=0,sticky="ew")
        self.status_label=ctk.CTkLabel(
            self.status_bar,text="Pronto.",text_color=MUTED,font=("Segoe UI",10,"bold"),anchor="w"
        )
        self.status_label.pack(fill="x",padx=12,pady=5)

    def clear_content(self):
        for w in self.content.winfo_children():
            if w is not getattr(self,"status_bar",None):
                w.destroy()

    def set_status(self,text,kind="info",timeout=4500):
        if not hasattr(self,"status_label"):
            return
        colors={"ok":GREEN,"error":RED,"warn":AMBER,"info":MUTED}
        self.status_label.configure(text=text,text_color=colors.get(kind,MUTED))
        if self._status_job:
            try: self.root.after_cancel(self._status_job)
            except Exception: pass
        if timeout:
            self._status_job=self.root.after(timeout,lambda:self.status_label.configure(text="Pronto.",text_color=MUTED))

    def set_active_nav(self,key):
        for name,b in getattr(self,"nav_buttons",{}).items():
            active_nav_config(b,name==key)

    def page_header(self,title,subtitle=""):
        h=ctk.CTkFrame(self.content,fg_color="transparent")
        h.grid(row=0,column=0,sticky="ew",padx=32,pady=(24,14))
        ctk.CTkLabel(h,text=title,text_color=TEXT,font=FONT_TITLE).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(h,text=subtitle,text_color=MUTED,font=FONT_BODY).pack(anchor="w",pady=(4,0))

    # -------- variables / draft --------
    def V(self,key,default=""):
        if key not in self.vars:
            initial = "Não" if key in DEFAULT_NO else default
            self.vars[key]=tk.StringVar(value=initial)
            self.vars[key].trace_add("write",lambda *_a,k=key:self.on_var_change(k))
        return self.vars[key]

    def is_required(self,key):
        if key in {"uf_nascimento","cidade_nascimento","municipio_nascimento"} and self.V("estrangeiro").get()=="Sim":
            return False
        return key in REQUIRED_KEYS

    def refresh_required_labels(self):
        for key,label_widget in getattr(self,"field_labels",{}).items():
            base=getattr(label_widget,"_rh_base_text",None)
            if base is None:
                continue
            label_widget.configure(text=f"{base} *" if self.is_required(key) else base)

    def on_var_change(self,key):
        if self.restoring: return
        if key=="estrangeiro":
            self.refresh_required_labels()
        self.update_progress()
        self.autosave_draft()

    def _write_draft_now(self):
        if not hasattr(self,"company_var"): return
        data={
            "empresa":self.company_var.get(),
            "vars":{k:v.get() for k,v in self.vars.items()},
            "dependentes":self.dependentes,
            "consignados":self.consignados,
            "step":self.current_step,
            "saved_at":datetime.now().isoformat(timespec="seconds")
        }
        try:
            DRAFT_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception:
            pass

    def autosave_draft(self,immediate=False):
        if not hasattr(self,"company_var"): return
        if self._autosave_job:
            try: self.root.after_cancel(self._autosave_job)
            except Exception: pass
            self._autosave_job=None
        if immediate:
            self._write_draft_now()
        else:
            self._autosave_job=self.root.after(650,self._write_draft_now)

    def close_app(self):
        self.autosave_draft(immediate=True)
        try:
            self.root.destroy()
        except Exception:
            pass

    def load_draft(self):
        if not DRAFT_PATH.exists(): return False
        try:
            d=json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
            if not d.get("vars"): return False
            if messagebox.askyesno("Rascunho encontrado","Existe uma admissão não concluída. Deseja continuar de onde parou?"):
                self.restoring=True
                for k,val in d.get("vars",{}).items():
                    self.V(k).set(val)
                self.dependentes=d.get("dependentes",[])
                self.consignados=d.get("consignados",[]) or []
                # Compatibilidade com versões anteriores que tinham apenas um contrato.
                legacy_contract=(d.get("vars",{}).get("consignado_contrato") or "").strip()
                if not self.consignados and legacy_contract:
                    self.consignados=[{"contrato":legacy_contract}]
                self.current_step=min(4,max(0,int(d.get("step",0))))
                if d.get("empresa"): self.company_var.set(d["empresa"])
                self.restoring=False
                return True
        except Exception:
            pass
        return False

    def clear_draft(self):
        if self._autosave_job:
            try: self.root.after_cancel(self._autosave_job)
            except Exception: pass
            self._autosave_job=None
        try:
            if DRAFT_PATH.exists(): DRAFT_PATH.unlink()
        except Exception: pass

    def record_history(self,admissao_id,acao,detalhes="",nome="",cpf=""):
        try:
            if admissao_id and (not nome or not cpf):
                result=rows("SELECT nome,cpf FROM admissoes WHERE id=?",(admissao_id,))
                if result:
                    nome=nome or result[0]["nome"] or ""
                    cpf=cpf or result[0]["cpf"] or ""
            execute(
                """INSERT INTO historico_admissoes(admissao_id,data_hora,acao,detalhes,nome,cpf)
                   VALUES(?,?,?,?,?,?)""",
                (admissao_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),acao,detalhes,nome,cpf)
            )
        except Exception:
            pass

    def purge_expired_trash(self):
        try:
            cutoff=(datetime.now()-timedelta(days=TRASH_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
            expired=rows("SELECT id,nome,cpf,pdf_path,pdf_excluido FROM admissoes WHERE excluido_em IS NOT NULL AND excluido_em<?",(cutoff,))
            for x in expired:
                self.record_history(x["id"],"Exclusão definitiva automática",f"Registro expirado após {TRASH_RETENTION_DAYS} dias.",x["nome"] or "",x["cpf"] or "")
                if not x["pdf_excluido"] and x["pdf_path"]:
                    try:
                        Path(x["pdf_path"]).unlink(missing_ok=True)
                    except Exception:
                        pass
                execute("DELETE FROM admissoes WHERE id=?",(x["id"],))
        except Exception:
            pass

    def show_history_dialog(self,aid):
        result=rows("SELECT nome,cpf FROM admissoes WHERE id=?",(aid,))
        if result:
            title_name=result[0]["nome"] or "Funcionário"
        else:
            hist=rows("SELECT nome FROM historico_admissoes WHERE admissao_id=? ORDER BY id DESC LIMIT 1",(aid,))
            title_name=(hist[0]["nome"] if hist else "Funcionário") or "Funcionário"

        entries=rows(
            """SELECT data_hora,acao,detalhes FROM historico_admissoes
               WHERE admissao_id=? ORDER BY id DESC""",(aid,)
        )
        win=ctk.CTkToplevel(self.root)
        win.title(f"Histórico · {title_name}")
        win.geometry("720x520")
        win.minsize(620,420)
        win.transient(self.root)
        body=ctk.CTkScrollableFrame(win,fg_color="#f7f8f9")
        body.pack(fill="both",expand=True,padx=12,pady=12)
        if not entries:
            ctk.CTkLabel(body,text="Nenhum evento registrado.",text_color=MUTED,font=FONT_BODY).pack(anchor="w",padx=12,pady=12)
        else:
            for x in entries:
                card=ctk.CTkFrame(body,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=8)
                card.pack(fill="x",padx=5,pady=4)
                ctk.CTkLabel(card,text=f"{x['data_hora']} — {x['acao']}",text_color=TEXT,font=("Segoe UI",12,"bold")).pack(anchor="w",padx=12,pady=(9,2))
                if x["detalhes"]:
                    ctk.CTkLabel(card,text=x["detalhes"],text_color=MUTED,font=FONT_SMALL,wraplength=620,justify="left").pack(anchor="w",padx=12,pady=(0,9))
        ctk.CTkButton(win,text="FECHAR",command=win.destroy,width=110,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,font=("Segoe UI",11,"bold")).pack(anchor="e",padx=18,pady=(0,14))

    # -------- dashboard --------
    def show_dashboard(self):
        self.set_active_nav("dashboard")
        self.clear_content()
        self.page_header("Visão Geral","Resumo do RH Fácil e últimos registros salvos.")

        body=ctk.CTkFrame(self.content,fg_color="transparent")
        body.grid(row=1,column=0,sticky="nsew",padx=32,pady=(0,18))
        body.grid_columnconfigure((0,1,2,3),weight=1)
        body.grid_rowconfigure(1,weight=1)

        month=datetime.now().strftime("%Y-%m")
        month_count=rows("SELECT COUNT(*) AS n FROM admissoes WHERE excluido_em IS NULL AND substr(criado_em,1,7)=?",(month,))[0]["n"]
        draft=1 if DRAFT_PATH.exists() else 0
        pdf_count=len(list(PDF_DIR.glob("*.pdf")))
        last_backup=self.latest_backup_text().replace("Último backup: ","") if list(BACKUP_DIR.glob("RH_Facil_backup_*.zip")) else "Nenhum"

        cards=[
            ("Admissões este mês",month_count),
            ("Rascunho em andamento", "Sim" if draft else "Não"),
            ("Total de fichas",pdf_count),
            ("Último backup",last_backup),
        ]
        for i,(label,value) in enumerate(cards):
            c=ctk.CTkFrame(body,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
            c.grid(row=0,column=i,sticky="ew",padx=(0 if i==0 else 6,0 if i==3 else 6))
            ctk.CTkLabel(c,text=str(value),text_color=TEXT,font=("Segoe UI",25,"bold"),wraplength=230,justify="left").pack(anchor="w",padx=16,pady=(14,0))
            ctk.CTkLabel(c,text=label,text_color=MUTED,font=FONT_BODY).pack(anchor="w",padx=16,pady=(0,14))

        recent=ctk.CTkFrame(body,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
        recent.grid(row=1,column=0,columnspan=4,sticky="nsew",pady=(14,0))
        recent.grid_columnconfigure(0,weight=1)

        top=ctk.CTkFrame(recent,fg_color="transparent")
        top.grid(row=0,column=0,sticky="ew",padx=16,pady=(12,7))
        top.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(top,text="ÚLTIMAS ADMISSÕES",text_color=TEXT,font=("Segoe UI",17,"bold")).grid(row=0,column=0,sticky="w")
        ctk.CTkButton(top,text="VER TODAS",command=self.show_employees,width=110,height=32,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,font=("Segoe UI",11,"bold")).grid(row=0,column=1,sticky="e")

        latest=rows(
            """SELECT id,nome,cpf,funcao,criado_em,atualizado_em
               FROM admissoes WHERE excluido_em IS NULL ORDER BY id DESC LIMIT 5"""
        )
        if not latest:
            ctk.CTkLabel(recent,text="Nenhuma admissão salva ainda.",text_color=MUTED,font=FONT_BODY).grid(row=1,column=0,sticky="w",padx=16,pady=(6,18))
            return

        for idx,x in enumerate(latest,1):
            line=ctk.CTkFrame(recent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=8)
            line.grid(row=idx,column=0,sticky="ew",padx=16,pady=4)
            line.grid_columnconfigure(0,weight=1)
            funcao=(x["funcao"] or "Função não informada").strip()
            cpf=self.format_cpf(x["cpf"] or "")
            ctk.CTkLabel(line,text=(x["nome"] or "Sem nome"),text_color=TEXT,font=("Segoe UI",13,"bold")).grid(row=0,column=0,sticky="w",padx=12,pady=(7,1))
            ctk.CTkLabel(line,text=f"{cpf} · {funcao}",text_color=MUTED,font=FONT_SMALL).grid(row=1,column=0,sticky="w",padx=12,pady=(0,2))
            ctk.CTkLabel(line,text=f"Criado: {x['criado_em']}   |   Atualizado: {x['atualizado_em']}",text_color=MUTED,font=("Segoe UI",10)).grid(row=2,column=0,sticky="w",padx=12,pady=(0,7))
            ctk.CTkButton(line,text="ABRIR",width=75,height=31,fg_color=ACCENT,hover_color=ACCENT_HOVER,command=lambda aid=x["id"]:self.load_employee_for_edit(aid),font=("Segoe UI",10,"bold")).grid(row=0,column=1,rowspan=3,padx=10,pady=7)

    def show_new_admission(self, load_draft=True):
        self.set_active_nav("new")
        self.clear_content()
        self.vars={}
        self.dependentes=[]
        self.consignados=[]
        self.current_step=0
        self.current_edit_id=None
        self.page_header("Nova Admissão","Fluxo guiado, com campos condicionais e salvamento automático de rascunho.")

        wrapper=ctk.CTkFrame(self.content,fg_color="transparent")
        wrapper.grid(row=1,column=0,sticky="nsew",padx=32,pady=(0,28))
        wrapper.grid_columnconfigure(0,weight=1)
        wrapper.grid_rowconfigure(1,weight=1)

        # company var before draft restore
        companies=rows("SELECT id,razao_social,nome_fantasia FROM empresas WHERE ativa=1 ORDER BY razao_social")
        self.company_map={((r["nome_fantasia"] or "").strip() or r["razao_social"]):r["id"] for r in companies}
        vals=list(self.company_map) or ["Cadastre uma empresa em Configurações"]
        self.company_var=tk.StringVar(value=vals[0])
        self.company_var.trace_add("write",lambda *_: (self.update_progress(),self.autosave_draft()))

        # progress / clickable tabs
        self.progress=ctk.CTkFrame(wrapper,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
        self.progress.grid(row=0,column=0,sticky="ew",pady=(0,14))
        self.progress.grid_columnconfigure(tuple(range(5)),weight=1)
        self.step_buttons=[]
        for i,name in enumerate(self.STEPS):
            b=ctk.CTkButton(
                self.progress,text=f"{i+1}  {name}",command=lambda idx=i:self.goto_step(idx),
                height=46,fg_color="transparent",hover_color="#eef0f2",corner_radius=7,
                text_color=RED,font=("Segoe UI",13,"bold")
            )
            b.grid(row=0,column=i,padx=5,pady=7,sticky="ew")
            self.step_buttons.append(b)

        self.stage=ctk.CTkFrame(wrapper,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
        self.stage.grid(row=1,column=0,sticky="nsew")
        self.stage.grid_columnconfigure(0,weight=1)
        self.stage.grid_rowconfigure(0,weight=1)

        self.form=ctk.CTkScrollableFrame(self.stage,fg_color="transparent")
        self.form.grid(row=0,column=0,sticky="nsew",padx=7,pady=7)
        self.form.grid_columnconfigure((0,1),weight=1)

        bottom=ctk.CTkFrame(self.stage,fg_color="#fafafa",corner_radius=0)
        bottom.grid(row=1,column=0,sticky="ew")
        bottom.grid_columnconfigure(1,weight=1)
        self.back_btn=ctk.CTkButton(bottom,text="← Voltar",command=self.prev_step,width=120,
                                    fg_color="#e5e7e9",hover_color="#d8dbde",text_color=TEXT,font=FONT_BODY)
        self.back_btn.grid(row=0,column=0,padx=18,pady=14)
        self.next_btn=ctk.CTkButton(bottom,text="Continuar →",command=self.next_step,width=145,
                                    fg_color=ACCENT,hover_color=ACCENT_HOVER,text_color="white",font=("Segoe UI",13,"bold"))
        self.next_btn.grid(row=0,column=2,padx=18,pady=14)

        restored=self.load_draft() if load_draft else False
        self.render_step()
        if restored:
            self.root.after(100,lambda:self.goto_step(self.current_step))

    def scroll_top(self):
        try:
            self.form._parent_canvas.yview_moveto(0)
        except Exception: pass

    def goto_step(self,idx):
        self.current_step=idx
        self.render_step()
        self.scroll_top()
        self.autosave_draft(immediate=True)

    def next_step(self):
        if self.current_step<4:
            self.goto_step(self.current_step+1)

    def prev_step(self):
        if self.current_step>0:
            self.goto_step(self.current_step-1)

    def update_progress(self):
        if not getattr(self,"step_buttons",None): return
        for i,b in enumerate(self.step_buttons):
            complete=self.step_complete(i)
            color=GREEN if complete else RED
            prefix="✓ " if complete else "• "
            b.configure(
                text=f"{prefix}{i+1}  {self.STEPS[i]}",
                text_color=color,
                fg_color="#eef6f1" if i==self.current_step and complete else "#f8eeee" if i==self.current_step else "transparent"
            )
        if hasattr(self,"back_btn"):
            self.back_btn.configure(state="disabled" if self.current_step==0 else "normal")
        if hasattr(self,"next_btn"):
            if self.current_step==4:
                final_text="Atualizar e gerar PDF" if self.current_edit_id else "Salvar e gerar PDF"
                self.next_btn.configure(text=final_text,command=self.save_and_pdf)
            else:
                self.next_btn.configure(text="Continuar →",command=self.next_step)

    def filled(self,key):
        v=self.V(key).get().strip()
        return bool(v and v!="Selecione")

    def step_complete(self,s):
        try:
            if s==0:
                req=["nome","cep","endereco","bairro","uf","cidade","telefone","primeiro_emprego",
                     "data_nascimento","sexo","raca_cor","estado_civil","nome_mae"]
                if self.V("estrangeiro").get()!="Sim":
                    req += ["uf_nascimento","cidade_nascimento"]
                if self.V("estado_civil").get() in ("Casado","União Estável"): req.append("nome_conjuge")
                return bool(self.company_map.get(self.company_var.get())) and all(self.filled(k) for k in req)
            if s==1:
                req=["cpf","pis","carteira_digital","rg_numero","rg_orgao","rg_expedicao","possui_cnh"]
                if self.V("carteira_digital").get()=="Não": req += ["ctps_numero","ctps_serie_uf","ctps_emissao"]
                if self.V("estrangeiro").get()=="Sim": req += ["rne_orgao_data","chegada_brasil"]
                if self.V("orgao_classe").get()=="Sim": req += ["orgao_classe_numero","orgao_classe_emissor_data"]
                if self.V("possui_cnh").get()=="Sim": req += ["cnh_numero","cnh_categoria","cnh_expedicao","cnh_validade","cnh_primeira_habilitacao"]
                return all(self.filled(k) for k in req) and cpf_valid(self.V("cpf").get())
            if s==2:
                return all(self.filled(k) for k in ["residencia_propria","deficiencia_motora","deficiencia_visual","deficiencia_auditiva","reabilitado"])
            if s==3:
                req=["outros_vinculos","outra_remuneracao","sindicato","pensao","consignado",
                     "data_admissao","salario","funcao","horario_trabalho","contrato_experiencia","grau_instrucao","vale_transporte"]
                if self.V("outros_vinculos").get()=="Sim":
                    req.append("outros_vinculos_cnpj")
                    if not cnpj_valid(self.V("outros_vinculos_cnpj").get()): return False
                if self.V("sindicato").get()=="Sim":
                    req.append("sindicato_cnpj")
                    if not cnpj_valid(self.V("sindicato_cnpj").get()): return False
                if self.V("pensao").get()=="Sim": req += ["pensao_nome","pensao_cpf","pensao_banco","pensao_agencia","pensao_conta"]
                if self.V("consignado").get()=="Sim":
                    if not getattr(self,"consignados",[]):
                        return False
                    if any(not (x.get("contrato","") or "").strip() for x in self.consignados):
                        return False
                return all(self.filled(k) for k in req)
            return all(self.step_complete(i) for i in range(4))
        except Exception:
            return False

    def clear_form(self):
        for w in self.form.winfo_children(): w.destroy()

    def render_step(self):
        self.clear_form()
        [self.build_personal,self.build_documents,self.build_dependents,self.build_work,self.build_review][self.current_step]()
        self.update_progress()
        self.root.after(80,self.bind_arrows)

    def section_title(self,title,subtitle=""):
        row=0
        ctk.CTkLabel(self.form,text=title,text_color=TEXT,font=FONT_H2).grid(
            row=row,column=0,columnspan=2,sticky="w",padx=16,pady=(15,2)
        )
        if subtitle:
            row+=1
            ctk.CTkLabel(self.form,text=subtitle,text_color=MUTED,font=FONT_BODY).grid(
                row=row,column=0,columnspan=2,sticky="w",padx=16,pady=(0,6)
            )
        if self.current_step < 4:
            row+=1
            ctk.CTkLabel(
                self.form,text="* Campo obrigatório",text_color=RED,
                font=("Segoe UI",11,"bold")
            ).grid(row=row,column=0,columnspan=2,sticky="w",padx=16,pady=(0,10))
        return row+1

    def group(self,row,title,subtitle=""):
        g=ctk.CTkFrame(self.form,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10)
        g.grid(row=row,column=0,columnspan=2,sticky="ew",padx=14,pady=9)
        g.grid_columnconfigure((0,1),weight=1)
        ctk.CTkLabel(g,text=title,text_color=TEXT,font=FONT_GROUP).grid(row=0,column=0,columnspan=2,sticky="w",padx=16,pady=(13,2))
        rr=1
        if subtitle:
            ctk.CTkLabel(g,text=subtitle,text_color=MUTED,font=FONT_SMALL).grid(row=1,column=0,columnspan=2,sticky="w",padx=16,pady=(0,7))
            rr=2
        return g,rr

    def field(self,parent,row,col,key,label,kind="entry",values=None,on_change=None):
        box=ctk.CTkFrame(parent,fg_color="transparent")
        box.grid(row=row,column=col,sticky="ew",padx=14,pady=8)
        display_label = f"{label} *" if self.is_required(key) else label
        label_widget=ctk.CTkLabel(box,text=display_label,text_color=LABEL,font=FONT_LABEL)
        label_widget._rh_base_text=label
        label_widget.pack(anchor="w",pady=(0,6))
        self.field_labels[key]=label_widget
        v=self.V(key)

        if kind=="yesno":
            w=YesNoField(box,v,command=lambda:(on_change() if on_change else None,self.update_progress(),self.autosave_draft()))
            w.pack(anchor="w",pady=(4,4))
        elif kind=="date":
            w=SegmentedField(box,v,[2,2,4],["/","/"],command=self.autosave_draft); w.pack(anchor="w")
        elif kind=="phone":
            w=PhoneField(box,v,command=self.autosave_draft)
            w.pack(anchor="w")
        elif kind=="cpf":
            status = ctk.CTkLabel(box,text="",text_color=MUTED,font=("Segoe UI",11,"bold"))
            def validate_cpf_live():
                digits = only_digits(v.get())
                if len(digits) < 11:
                    status.configure(text="", text_color=MUTED)
                elif cpf_valid(digits):
                    status.configure(text="✓ CPF válido", text_color=GREEN)
                else:
                    status.configure(text="CPF inválido", text_color=RED)
                self.update_progress()
                self.autosave_draft()
            w=SegmentedField(box,v,[3,3,3,2],[".",".","-"],command=validate_cpf_live)
            w.pack(anchor="w")
            status.pack(anchor="w",pady=(4,0))
            validate_cpf_live()
        elif kind=="cnpj":
            status = ctk.CTkLabel(box,text="",text_color=MUTED,font=("Segoe UI",11,"bold"))
            def validate_cnpj_live():
                digits = only_digits(v.get())
                if len(digits) < 14:
                    status.configure(text="", text_color=MUTED)
                elif cnpj_valid(digits):
                    status.configure(text="✓ CNPJ válido", text_color=GREEN)
                else:
                    status.configure(text="CNPJ inválido", text_color=RED)
                self.update_progress()
                self.autosave_draft()
            w=SegmentedField(box,v,[2,3,3,4,2],[".",".","/","-"],command=validate_cnpj_live)
            w.pack(anchor="w")
            status.pack(anchor="w",pady=(4,0))
            validate_cnpj_live()
        elif kind=="cep":
            w=SegmentedField(box,v,[5,3],["-"],command=self.autosave_draft); w.pack(side="left")
            self.cep_button=ctk.CTkButton(box,text="Consultar",width=102,height=42,fg_color=ACCENT,hover_color=ACCENT_HOVER,
                          command=self.lookup_cep,font=FONT_BODY)
            self.cep_button.pack(side="left",padx=(10,0))
            self.cep_status_label=ctk.CTkLabel(box,text="",text_color=MUTED,font=("Segoe UI",10,"bold"))
            self.cep_status_label.pack(anchor="w",pady=(3,0))
        elif kind=="money":
            w=MoneyField(box,v); w.pack(anchor="w")
        elif kind=="height":
            w=MeasureField(box,v,"m",2,1); w.pack(anchor="w")
        elif kind=="weight":
            w=MeasureField(box,v,"kg",1,3); w.pack(anchor="w")
        elif kind=="combo":
            vals=values or ["Selecione"]
            if not v.get(): v.set(vals[0])
            w=ctk.CTkOptionMenu(box,variable=v,values=vals,height=44,font=FONT_INPUT,
                                dropdown_font=FONT_INPUT,fg_color="#eef1f3",button_color="#c8ced3",
                                button_hover_color="#c8cdd1",text_color=TEXT,command=lambda _x:(on_change() if on_change else None,self.update_progress(),self.autosave_draft()))
            w.pack(fill="x")
        else:
            w=ctk.CTkEntry(box,textvariable=v,height=44,font=FONT_INPUT,fg_color="#eef1f3",border_color="#aeb6bd")
            w.pack(fill="x")
        return w

    # -------- Personal --------
    def build_personal(self):
        r=self.section_title("1. Dados pessoais","Dados básicos, endereço e identificação pessoal.")

        g,rr=self.group(r,"Empresa e identificação","Selecione a empresa e informe os dados principais.")
        vals=list(self.company_map) or ["Cadastre uma empresa em Configurações"]
        b=ctk.CTkFrame(g,fg_color="transparent"); b.grid(row=rr,column=0,columnspan=2,sticky="ew",padx=14,pady=8)
        ctk.CTkLabel(b,text="Empresa *",text_color=LABEL,font=FONT_LABEL).pack(anchor="w",pady=(0,6))
        ctk.CTkOptionMenu(
            b,variable=self.company_var,values=vals,height=44,font=FONT_INPUT,
            dropdown_font=FONT_INPUT,fg_color="#eef1f3",button_color="#c8ced3",
            button_hover_color="#b9c0c6",text_color=TEXT
        ).pack(fill="x")
        rr+=1
        self.field(g,rr,0,"nome","Nome completo")
        self.field(g,rr,1,"cep","CEP",kind="cep")
        r+=1

        g,rr=self.group(r,"Endereço","O CEP pode preencher os campos automaticamente.")
        self.field(g,rr,0,"endereco","Endereço")
        self.field(g,rr,1,"bairro","Bairro"); rr+=1
        uf_vals=["Selecione"]+sorted(UF_NAMES.keys())
        self.field(g,rr,0,"uf","Estado (UF)",kind="combo",values=uf_vals,on_change=self.on_uf_change)
        self.city_widget=self.field(g,rr,1,"cidade","Cidade",kind="combo",values=self.city_values(),
                                      on_change=lambda:self.on_city_selected("cidade")); rr+=1
        r+=1

        g,rr=self.group(r,"Contato e nascimento","O telefone de contato é informado somente aqui.")
        self.field(g,rr,0,"telefone","Telefone de contato",kind="phone")
        self.field(g,rr,1,"data_nascimento","Data de nascimento",kind="date"); rr+=1
        self.field(g,rr,0,"primeiro_emprego","Primeiro emprego?",kind="yesno")
        self.field(g,rr,1,"uf_nascimento","Estado de nascimento (UF)",kind="combo",
                   values=["Selecione"]+sorted(UF_NAMES.keys()),on_change=self.on_birth_uf_change); rr+=1
        self.birth_city_widget=self.field(g,rr,0,"cidade_nascimento","Cidade de nascimento",kind="combo",
                                          values=self.birth_city_values(),
                                          on_change=lambda:self.on_city_selected("cidade_nascimento"))
        r+=1

        g,rr=self.group(r,"Características pessoais")
        self.field(g,rr,0,"sexo","Sexo",kind="combo",values=["Selecione","Masculino","Feminino","Outro"])
        self.field(g,rr,1,"raca_cor","Raça / cor",kind="combo",
                   values=["Selecione","Indígena","Branca","Preta","Amarela","Parda","Não informado"]); rr+=1
        self.field(g,rr,0,"altura","Altura",kind="height")
        self.field(g,rr,1,"peso","Peso",kind="weight"); rr+=1
        self.field(g,rr,0,"cor_cabelos","Cor dos cabelos")
        self.field(g,rr,1,"cor_olhos","Cor dos olhos"); rr+=1
        self.field(g,rr,0,"tipagem_sanguinea","Tipagem sanguínea",kind="combo",
                   values=["Selecione","A+","A-","B+","B-","AB+","AB-","O+","O-"])
        self.field(g,rr,1,"estado_civil","Estado civil",kind="combo",
                   values=["Selecione","Solteiro","Casado","Divorciado","Viúvo","União Estável","Outros"],
                   on_change=self.toggle_spouse); rr+=1

        self.spouse_box=ctk.CTkFrame(g,fg_color="transparent")
        self.spouse_box.grid(row=rr,column=0,sticky="ew",padx=14,pady=8)
        ctk.CTkLabel(self.spouse_box,text="Nome do cônjuge",text_color=LABEL,font=FONT_LABEL).pack(anchor="w",pady=(0,6))
        ctk.CTkEntry(
            self.spouse_box,textvariable=self.V("nome_conjuge"),height=44,font=FONT_INPUT,
            fg_color="#eef1f3",border_color="#aeb6bd"
        ).pack(fill="x")
        if self.V("estado_civil").get() not in ("Casado","União Estável"):
            self.spouse_box.grid_remove()
        r+=1

        g,rr=self.group(r,"Filiação")
        self.field(g,rr,0,"nome_mae","Nome da mãe")
        self.field(g,rr,1,"nome_pai","Nome do pai")

    def city_values_for(self, uf_key):
        uf=self.V(uf_key).get()
        if uf=="Selecione" or not uf:
            return ["Selecione"]
        vals=[r["cidade"] for r in rows("SELECT cidade FROM municipios WHERE uf=? ORDER BY cidade",(uf,))]
        return ["Selecione"]+vals+["Outra cidade..."]

    def city_values(self):
        return self.city_values_for("uf")

    def birth_city_values(self):
        return self.city_values_for("uf_nascimento")

    def on_uf_change(self):
        uf=self.V("uf").get()
        self.V("cidade").set("Selecione")
        self.fetch_ibge_cities(uf,"cidade")
        if hasattr(self,"city_widget"):
            self.city_widget.configure(values=self.city_values())
        self.update_progress()
        self.autosave_draft()

    def on_birth_uf_change(self):
        uf=self.V("uf_nascimento").get()
        self.V("cidade_nascimento").set("Selecione")
        self.fetch_ibge_cities(uf,"cidade_nascimento")
        if hasattr(self,"birth_city_widget"):
            self.birth_city_widget.configure(values=self.birth_city_values())
        self.update_progress()
        self.autosave_draft()

    def toggle_spouse(self):
        married=self.V("estado_civil").get() in ("Casado","União Estável")
        if hasattr(self,"spouse_box"):
            if married:
                self.spouse_box.grid()
            else:
                self.V("nome_conjuge").set("")
                self.spouse_box.grid_remove()
        self.update_progress()
        self.autosave_draft()

    def rerender_keep_position(self):
        # Mantido por compatibilidade com rascunhos/versões anteriores.
        self.update_progress()
        self.autosave_draft()

    def _restore_scroll(self,pos):
        try:
            self.form._parent_canvas.yview_moveto(pos)
        except Exception:
            pass

    def _apply_ibge_result(self,uf,target,token,data,error=None):
        if token!=self._city_request_tokens.get(target,0):
            return
        if error:
            self.set_status("Não foi possível atualizar a lista de municípios; você pode usar Outra cidade...", "warn")
            return
        try:
            con=db()
            for item in data:
                cidade=(item.get("nome") or "").strip()
                if cidade:
                    con.execute("INSERT OR IGNORE INTO municipios(uf,cidade,fonte) VALUES(?,?,?)",(uf,cidade,"IBGE"))
            con.commit(); con.close()
        except Exception:
            self.set_status("Lista local de municípios não pôde ser atualizada.","warn")
            return
        if target=="cidade" and hasattr(self,"city_widget") and self.V("uf").get()==uf:
            self.city_widget.configure(values=self.city_values())
        if target=="cidade_nascimento" and hasattr(self,"birth_city_widget") and self.V("uf_nascimento").get()==uf:
            self.birth_city_widget.configure(values=self.birth_city_values())
        self.set_status(f"Municípios de {uf} atualizados pelo IBGE.","ok")

    def fetch_ibge_cities(self,uf,target="cidade"):
        if uf not in UF_NAMES:
            return
        if len(rows("SELECT cidade FROM municipios WHERE uf=?",(uf,))) > 30:
            return
        self._city_request_tokens[target]=self._city_request_tokens.get(target,0)+1
        token=self._city_request_tokens[target]
        self.set_status("Consultando municípios no IBGE...", "info", timeout=0)
        def worker():
            try:
                url=f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
                req=urllib.request.Request(url,headers={"User-Agent":"RH-Facil/0.3.7"})
                with urllib.request.urlopen(req,timeout=8) as resp:
                    data=json.loads(resp.read().decode("utf-8"))
                self.root.after(0,lambda:self._apply_ibge_result(uf,target,token,data,None))
            except Exception as exc:
                self.root.after(0,lambda:self._apply_ibge_result(uf,target,token,[],exc))
        threading.Thread(target=worker,daemon=True).start()

    def _apply_cep_result(self,token,data,error=None):
        if token!=self._cep_request_token:
            return
        if hasattr(self,"cep_button"):
            self.cep_button.configure(state="normal",text="Consultar")
        if hasattr(self,"cep_status_label"):
            self.cep_status_label.configure(text="")
        if error:
            messagebox.showerror("Consulta de CEP","Não foi possível consultar o CEP. Você ainda pode preencher o endereço manualmente.")
            return
        if data.get("erro"):
            messagebox.showwarning("CEP","CEP não encontrado.")
            return
        self.restoring=True
        self.V("endereco").set(data.get("logradouro", ""))
        self.V("bairro").set(data.get("bairro", ""))
        uf=data.get("uf", "")
        cidade=data.get("localidade", "")
        self.V("uf").set(uf)
        if cidade:
            execute("INSERT OR IGNORE INTO municipios(uf,cidade,fonte) VALUES(?,?,?)",(uf,cidade,"CEP"))
            self.V("cidade").set(cidade)
        self.restoring=False
        if hasattr(self,"city_widget"):
            self.city_widget.configure(values=self.city_values())
        self.update_progress()
        self.autosave_draft()
        self.set_status("Endereço preenchido pelo CEP.","ok")

    def lookup_cep(self):
        cep=only_digits(self.V("cep").get())
        if len(cep)!=8:
            messagebox.showwarning("CEP","Informe os 8 dígitos do CEP.")
            return
        self._cep_request_token+=1
        token=self._cep_request_token
        if hasattr(self,"cep_button"):
            self.cep_button.configure(state="disabled",text="Consultando...")
        if hasattr(self,"cep_status_label"):
            self.cep_status_label.configure(text="Consultando ViaCEP...")
        def worker():
            try:
                req=urllib.request.Request(f"https://viacep.com.br/ws/{cep}/json/",headers={"User-Agent":"RH-Facil/0.3.7"})
                with urllib.request.urlopen(req,timeout=8) as resp:
                    data=json.loads(resp.read().decode("utf-8"))
                self.root.after(0,lambda:self._apply_cep_result(token,data,None))
            except Exception as exc:
                self.root.after(0,lambda:self._apply_cep_result(token,{},exc))
        threading.Thread(target=worker,daemon=True).start()

    # -------- Documents --------
    def build_documents(self):
        r=self.section_title("2. Documentos","Cada documento fica em seu próprio bloco para evitar confusão.")

        g,rr=self.group(r,"CPF e PIS/PASEP/NIT")
        self.field(g,rr,0,"cpf","CPF",kind="cpf")
        self.field(g,rr,1,"pis","PIS / PASEP / NIT"); r+=1

        g,rr=self.group(r,"Carteira de Trabalho")
        self.field(g,rr,0,"carteira_digital","Carteira de trabalho digital?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.ctps_block,self.V("carteira_digital").get()=="Não")); rr+=1
        self.ctps_block=self.conditional_block(g,rr,self.V("carteira_digital").get()=="Não")
        self.field(self.ctps_block,0,0,"ctps_numero","Número da CTPS")
        self.field(self.ctps_block,0,1,"ctps_serie_uf","Série e UF")
        self.field(self.ctps_block,1,0,"ctps_emissao","Data de emissão",kind="date")
        rr+=1; r+=1

        g,rr=self.group(r,"RG")
        self.field(g,rr,0,"rg_numero","Número do RG")
        orgaos=["Selecione","SSP - Secretaria de Segurança Pública","PC - Polícia Civil","IGP - Instituto-Geral de Perícias",
                "IFP - Instituto Félix Pacheco","SESP - Secretaria de Estado da Segurança Pública",
                "SDS - Secretaria de Defesa Social","SEJUSP - Secretaria de Justiça e Segurança Pública",
                "DETRAN - Departamento Estadual de Trânsito","Outro"]
        self.field(g,rr,1,"rg_orgao","Órgão emissor",kind="combo",values=orgaos,
                   on_change=lambda:self.toggle_block(self.rg_other_block,self.V("rg_orgao").get()=="Outro")); rr+=1
        self.rg_other_block=self.conditional_block(g,rr,self.V("rg_orgao").get()=="Outro")
        self.field(self.rg_other_block,0,0,"rg_orgao_outro","Digite o órgão emissor"); rr+=1
        self.field(g,rr,0,"rg_expedicao","Data de expedição",kind="date"); r+=1

        g,rr=self.group(r,"Título de Eleitor")
        self.field(g,rr,0,"titulo_eleitor","Número do título")
        self.field(g,rr,1,"zona","Zona"); rr+=1
        self.field(g,rr,0,"secao","Seção"); r+=1

        g,rr=self.group(r,"Estrangeiro","Padrão: Não. Mude para Sim apenas quando necessário.")
        self.field(g,rr,0,"estrangeiro","Estrangeiro?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.foreigner_block,self.V("estrangeiro").get()=="Sim")); rr+=1
        self.foreigner_block=self.conditional_block(g,rr,self.V("estrangeiro").get()=="Sim")
        self.field(self.foreigner_block,0,0,"rne_orgao_data","RNE / órgão emissor / expedição")
        self.field(self.foreigner_block,0,1,"chegada_brasil","Chegada ao Brasil",kind="date")
        self.field(self.foreigner_block,1,0,"naturalizacao","Naturalização",kind="date")
        self.field(self.foreigner_block,1,1,"casado_brasileiro","Casado(a) com brasileiro(a)?",kind="yesno")
        self.field(self.foreigner_block,2,0,"filhos_brasileiro","Tem filhos com brasileiro(a)?",kind="yesno")
        rr+=1; r+=1

        g,rr=self.group(r,"Registro em órgão de classe","CRC, CRM, CRO, OAB ou equivalente.")
        self.field(g,rr,0,"orgao_classe","Possui registro?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.orgao_classe_block,self.V("orgao_classe").get()=="Sim")); rr+=1
        self.orgao_classe_block=self.conditional_block(g,rr,self.V("orgao_classe").get()=="Sim")
        self.field(self.orgao_classe_block,0,0,"orgao_classe_numero","Número do registro")
        self.field(self.orgao_classe_block,0,1,"orgao_classe_emissor_data","Órgão emissor / expedição")
        self.field(self.orgao_classe_block,1,0,"orgao_classe_validade","Validade",kind="date")
        rr+=1; r+=1

        g,rr=self.group(r,"CNH","Padrão: Não. Ao marcar Sim, os detalhes aparecem logo abaixo.")
        self.field(g,rr,0,"possui_cnh","Possui CNH?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.cnh_block,self.V("possui_cnh").get()=="Sim")); rr+=1
        self.cnh_block=self.conditional_block(g,rr,self.V("possui_cnh").get()=="Sim")
        self.field(self.cnh_block,0,0,"cnh_numero","Número da CNH")
        self.field(self.cnh_block,0,1,"cnh_categoria","Categoria",kind="combo",
                   values=["Selecione","ACC","A","B","AB","C","D","E","AC","AD","AE","Outro"])
        self.field(self.cnh_block,1,0,"cnh_expedicao","Data de expedição",kind="date")
        self.field(self.cnh_block,1,1,"cnh_validade","Data de validade",kind="date")
        self.field(self.cnh_block,2,0,"cnh_primeira_habilitacao","Primeira habilitação",kind="date")

    # -------- Dependents --------
    def build_dependents(self):
        r=self.section_title("3. Dependentes","Condições pessoais e cadastro dos dependentes.")

        g,rr=self.group(r,"Residência")
        self.field(g,rr,0,"residencia_propria","Residência própria?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.fgts_block,self.V("residencia_propria").get()=="Sim")); rr+=1
        self.fgts_block=self.conditional_block(g,rr,self.V("residencia_propria").get()=="Sim")
        self.field(self.fgts_block,0,0,"fgts_imovel","Adquirida com recurso do FGTS?",kind="yesno")
        rr+=1; r+=1

        g,rr=self.group(r,"Condições e reabilitação","As opções ficam em Não por padrão.")
        self.field(g,rr,0,"deficiencia_motora","Deficiência motora?",kind="yesno")
        self.field(g,rr,1,"deficiencia_visual","Deficiência visual?",kind="yesno"); rr+=1
        self.field(g,rr,0,"deficiencia_auditiva","Deficiência auditiva?",kind="yesno")
        self.field(g,rr,1,"reabilitado","Trabalhador reabilitado?",kind="yesno"); rr+=1
        self.field(g,rr,0,"outra_deficiencia","Outra deficiência — indique")
        r+=1

        g,rr=self.group(r,"Dependentes")
        if not self.dependentes:
            ctk.CTkLabel(g,text="Nenhum dependente adicionado.",text_color=MUTED,font=FONT_BODY).grid(row=rr,column=0,columnspan=2,sticky="w",padx=14,pady=8); rr+=1
        else:
            for i,d in enumerate(self.dependentes):
                line=ctk.CTkFrame(g,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8)
                line.grid(row=rr,column=0,columnspan=2,sticky="ew",padx=14,pady=4)
                ctk.CTkLabel(line,text=f"{i+1}. {d.get('nome','')} · CPF {d.get('cpf','')} · {d.get('tipo','')}",text_color=TEXT,font=FONT_BODY).pack(side="left",padx=12,pady=10)
                ctk.CTkButton(line,text="Remover",width=75,height=29,fg_color="#e4e6e8",hover_color="#d7dadd",text_color=TEXT,command=lambda idx=i:self.remove_dep(idx)).pack(side="right",padx=8,pady=6)
                rr+=1
        ctk.CTkButton(g,text="+ Adicionar dependente",command=self.add_dep_dialog,width=180,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,font=FONT_BODY).grid(row=rr,column=0,sticky="w",padx=14,pady=(8,14))


    def add_dep_dialog(self):
        win=ctk.CTkToplevel(self.root)
        win.title("Adicionar dependente")
        win.geometry("660x640")
        win.minsize(620,560)
        win.transient(self.root)
        win.grab_set()
        win.grid_columnconfigure(0,weight=1)
        win.grid_rowconfigure(0,weight=1)

        body=ctk.CTkScrollableFrame(
            win,fg_color="#f7f8f9",
            scrollbar_button_color="#9da5ab",
            scrollbar_button_hover_color="#7f888f"
        )
        body.grid(row=0,column=0,sticky="nsew",padx=12,pady=(12,0))
        body.grid_columnconfigure(0,weight=1)

        footer=ctk.CTkFrame(win,fg_color="#eef1f3",corner_radius=0)
        footer.grid(row=1,column=0,sticky="ew")
        footer.grid_columnconfigure(0,weight=1)

        vals={}

        def label(text):
            ctk.CTkLabel(
                body,text=text,text_color=LABEL,font=FONT_LABEL
            ).pack(anchor="w",padx=18,pady=(12,5))

        def entry(label_text,key,options=None):
            label(label_text)
            v=tk.StringVar()
            vals[key]=v
            if options:
                w=ctk.CTkOptionMenu(
                    body,variable=v,values=options,height=42,
                    font=FONT_INPUT,dropdown_font=FONT_INPUT,
                    fg_color="#eef1f3",button_color="#c8ced3",
                    text_color=TEXT
                )
                v.set(options[0])
            else:
                w=ctk.CTkEntry(
                    body,textvariable=v,height=42,font=FONT_INPUT,
                    fg_color="#eef1f3",border_color="#aeb6bd"
                )
            w.pack(fill="x",padx=18)
            return w

        entry(
            "Tipo","tipo",
            [
                "01 - Cônjuge/companheiro(a)",
                "02 - Filho(a)/enteado(a) até 21",
                "03 - Filho(a)/enteado(a) estudante até 24",
                "04 - Filho(a)/enteado(a) incapacitado",
                "05 - Irmão/neto/bisneto até 21",
                "06 - Irmão/neto/bisneto estudante até 24",
                "07 - Irmão/neto/bisneto incapacitado",
                "08 - Pais/avós/bisavós",
                "09 - Menor sob guarda",
                "10 - Tutelado/curatelado"
            ]
        )
        entry("Nome","nome")

        # Data com barras permanentemente visíveis.
        label("Data de nascimento")
        birth_var=tk.StringVar()
        vals["nascimento"]=birth_var
        birth=SegmentedField(body,birth_var,[2,2,4],["/","/"])
        birth.pack(anchor="w",padx=18)

        entry("CPF","cpf")
        entry("Dependente para IRRF?","irrf",["Não","Sim"])
        entry("Dependente para salário-família?","salario_familia",["Não","Sim"])

        def save():
            if not vals["nome"].get().strip():
                messagebox.showwarning("Dependente","Informe o nome.",parent=win)
                return
            nascimento=vals["nascimento"].get().strip()
            if nascimento and len(only_digits(nascimento)) != 8:
                messagebox.showwarning(
                    "Dependente","Informe a data de nascimento completa.",parent=win
                )
                return
            data={k:v.get().strip() for k,v in vals.items()}
            if data.get("nascimento"):
                data["nascimento"]=self.format_date(data["nascimento"])
            self.dependentes.append(data)
            win.destroy()
            self.render_step()
            self.autosave_draft()

        ctk.CTkButton(
            footer,text="CANCELAR",command=win.destroy,
            width=110,height=42,fg_color="#d9dde0",
            hover_color="#cbd1d5",text_color=TEXT,
            font=("Segoe UI",12,"bold")
        ).grid(row=0,column=1,padx=(8,6),pady=12)

        ctk.CTkButton(
            footer,text="SALVAR DEPENDENTE",command=save,
            width=175,height=42,fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Segoe UI",12,"bold")
        ).grid(row=0,column=2,padx=(6,14),pady=12)

        self.root.after(100,lambda: win.lift())

    def remove_dep(self,idx):
        if 0<=idx<len(self.dependentes): self.dependentes.pop(idx); self.render_step(); self.autosave_draft()

    # -------- Work --------
    def build_work(self):
        r=self.section_title("4. Trabalho","Vínculos, benefícios e dados da contratação.")

        g,rr=self.group(r,"Contato complementar","O telefone de contato já foi informado em Dados pessoais.")
        self.field(g,rr,0,"email_principal","E-mail principal")
        self.field(g,rr,1,"email_alternativo","E-mail alternativo"); rr+=1
        self.field(g,rr,0,"qtd_filhos_ir","Quantidade de filhos para IR")
        self.field(g,rr,1,"qtd_filhos_salario_familia","Quantidade de filhos para salário-família"); r+=1

        g,rr=self.group(r,"Outros vínculos","Padrão: Não.")
        self.field(g,rr,0,"outros_vinculos","Trabalha em outra empresa com carteira assinada?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.outros_vinculos_block,self.V("outros_vinculos").get()=="Sim")); rr+=1
        self.field(g,rr,1,"outra_remuneracao","Recebe outra remuneração?",kind="yesno"); rr+=1
        self.outros_vinculos_block=self.conditional_block(g,rr,self.V("outros_vinculos").get()=="Sim")
        self.field(self.outros_vinculos_block,0,0,"outros_vinculos_cnpj","CNPJ da outra empresa",kind="cnpj")
        rr+=1; r+=1

        g,rr=self.group(r,"Sindicato","Padrão: Não.")
        self.field(g,rr,0,"sindicato","É filiado a sindicato?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.sindicato_block,self.V("sindicato").get()=="Sim")); rr+=1
        self.sindicato_block=self.conditional_block(g,rr,self.V("sindicato").get()=="Sim")
        self.field(self.sindicato_block,0,0,"sindicato_cnpj","CNPJ do sindicato",kind="cnpj")
        rr+=1; r+=1

        g,rr=self.group(r,"Pensão alimentícia","Padrão: Não. Os dados aparecem logo abaixo ao marcar Sim.")
        self.field(g,rr,0,"pensao","Possui pensão alimentícia?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.pensao_block,self.V("pensao").get()=="Sim")); rr+=1
        self.pensao_block=self.conditional_block(g,rr,self.V("pensao").get()=="Sim")
        self.field(self.pensao_block,0,0,"pensao_nome","Nome do beneficiário")
        self.field(self.pensao_block,0,1,"pensao_nascimento","Nascimento",kind="date")
        self.field(self.pensao_block,1,0,"pensao_cpf","CPF do beneficiário",kind="cpf")
        self.field(self.pensao_block,1,1,"pensao_banco","Banco")
        self.field(self.pensao_block,2,0,"pensao_agencia","Agência")
        self.field(self.pensao_block,2,1,"pensao_conta","Conta bancária")
        rr+=1; r+=1

        g,rr=self.group(r,"Empréstimos consignados / CLT","Padrão: Não. Ao marcar Sim, é possível cadastrar um ou mais contratos.")
        self.field(g,rr,0,"consignado","Possui empréstimo consignado?",kind="yesno",
                   on_change=lambda:self.toggle_block(self.consignado_block,self.V("consignado").get()=="Sim")); rr+=1
        self.consignado_block=self.conditional_block(g,rr,self.V("consignado").get()=="Sim")
        self.render_consignado_block()
        rr+=1; r+=1

        g,rr=self.group(r,"Informações adicionais")
        self.field(g,rr,0,"gravidez","Gravidez")
        self.field(g,rr,1,"acidente_trabalho","Acidente de trabalho"); rr+=1
        self.field(g,rr,0,"acidente","Acidente")
        self.field(g,rr,1,"atestado_saude","Atestado de Saúde"); rr+=1
        self.field(g,rr,0,"nome_social","Nome social"); r+=1

        g,rr=self.group(r,"Dados da admissão")
        self.field(g,rr,0,"data_admissao","Data de admissão",kind="date")
        self.field(g,rr,1,"salario","Salário",kind="money"); rr+=1
        self.field(g,rr,0,"funcao","Função / cargo")
        horarios=["Selecione"]+[x["horario"] for x in rows("SELECT horario FROM horarios WHERE ativo=1 ORDER BY padrao DESC,nome")]
        if self.V("horario_trabalho").get() in ("","Selecione"):
            default_h=rows("SELECT horario FROM horarios WHERE ativo=1 AND padrao=1 ORDER BY id LIMIT 1")
            if default_h:
                self.V("horario_trabalho").set(default_h[0]["horario"])
        self.field(g,rr,1,"horario_trabalho","Horário de trabalho",kind="combo",values=horarios if len(horarios)>1 else ["Selecione","Outro"]); rr+=1
        self.field(g,rr,0,"horario_sabado","Sábado")
        self.field(g,rr,1,"contrato_experiencia","Contrato de experiência",kind="combo",
                   values=["Selecione","30 dias","45 dias","60 dias","90 dias","Não fazer contrato"]); rr+=1
        self.field(g,rr,0,"grau_instrucao","Escolaridade",kind="combo",
                   values=["Selecione","Analfabeto","Ensino Fundamental incompleto até 5ª série",
                           "Ensino Fundamental incompleto com 5ª série completa",
                           "Ensino Fundamental incompleto da 6ª à 9ª série","Ensino Fundamental completo",
                           "Ensino Médio incompleto","Ensino Médio completo","Superior incompleto","Superior completo",
                           "Pós-graduação","Mestrado completo","Doutorado completo"])
        self.field(g,rr,1,"vale_transporte","Vai receber vale-transporte?",kind="yesno")

    def render_consignado_block(self):
        if not hasattr(self,"consignado_block"):
            return
        for w in self.consignado_block.winfo_children():
            w.destroy()
        self.consignado_block.grid_columnconfigure((0,1),weight=1)
        if not getattr(self,"consignados",[]):
            ctk.CTkLabel(self.consignado_block,text="Nenhum empréstimo adicionado.",text_color=MUTED,font=FONT_BODY).grid(row=0,column=0,columnspan=2,sticky="w",padx=14,pady=(4,8))
            row=1
        else:
            row=0
            for i,loan in enumerate(self.consignados):
                line=ctk.CTkFrame(self.consignado_block,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8)
                line.grid(row=row,column=0,columnspan=2,sticky="ew",padx=14,pady=4)
                line.grid_columnconfigure(0,weight=1)
                ctk.CTkLabel(line,text=f"{i+1}. Contrato: {loan.get('contrato','')}",text_color=TEXT,font=FONT_BODY).grid(row=0,column=0,sticky="w",padx=12,pady=10)
                ctk.CTkButton(line,text="REMOVER",width=85,height=29,fg_color="#eadada",hover_color="#dfcaca",text_color=RED,command=lambda idx=i:self.remove_consignado(idx)).grid(row=0,column=1,padx=8,pady=6)
                row+=1
        ctk.CTkButton(self.consignado_block,text="+ ADICIONAR EMPRÉSTIMO",command=self.add_consignado_dialog,width=190,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,font=("Segoe UI",11,"bold")).grid(row=row,column=0,sticky="w",padx=14,pady=(8,14))

    def add_consignado_dialog(self):
        win=ctk.CTkToplevel(self.root)
        win.title("Adicionar empréstimo consignado")
        win.geometry("540x270")
        win.resizable(False,False)
        win.transient(self.root)
        win.grab_set()
        win.grid_columnconfigure(0,weight=1)
        win.grid_rowconfigure(0,weight=1)

        body=ctk.CTkFrame(win,fg_color="#f7f8f9")
        body.grid(row=0,column=0,sticky="nsew",padx=12,pady=(12,0))
        body.grid_columnconfigure(0,weight=1)

        ctk.CTkLabel(
            body,text="NÚMERO DO CONTRATO *",
            text_color=LABEL,font=FONT_LABEL
        ).grid(row=0,column=0,sticky="w",padx=18,pady=(18,6))

        contract=tk.StringVar()
        entry=ctk.CTkEntry(
            body,textvariable=contract,height=44,font=FONT_INPUT,
            fg_color="#eef1f3",border_color="#aeb6bd"
        )
        entry.grid(row=1,column=0,sticky="ew",padx=18)

        footer=ctk.CTkFrame(win,fg_color="#eef1f3",corner_radius=0)
        footer.grid(row=1,column=0,sticky="ew")
        footer.grid_columnconfigure(0,weight=1)

        def save():
            value=contract.get().strip()
            if not value:
                messagebox.showwarning(
                    "Empréstimo consignado",
                    "Informe o número do contrato.",
                    parent=win
                )
                return
            self.consignados.append({"contrato":value})
            win.destroy()
            self.render_consignado_block()
            self.update_progress()
            self.autosave_draft()
            self.set_status("Empréstimo consignado adicionado.","ok")

        ctk.CTkButton(
            footer,text="CANCELAR",command=win.destroy,
            width=105,height=40,fg_color="#d9dde0",
            hover_color="#cbd1d5",text_color=TEXT,
            font=("Segoe UI",11,"bold")
        ).grid(row=0,column=1,padx=(8,6),pady=12)

        ctk.CTkButton(
            footer,text="SALVAR EMPRÉSTIMO",command=save,
            width=165,height=40,fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=("Segoe UI",11,"bold")
        ).grid(row=0,column=2,padx=(6,14),pady=12)

        self.root.after(100,entry.focus_set)

    def remove_consignado(self,idx):
        if 0<=idx<len(self.consignados):
            self.consignados.pop(idx)
            self.render_consignado_block()
            self.update_progress()
            self.autosave_draft()
            self.set_status("Empréstimo removido.","ok")

    # -------- Review --------
    def missing_fields(self):
        labels={
            "nome":"Nome completo","cep":"CEP","endereco":"Endereço","bairro":"Bairro","uf":"Estado","cidade":"Cidade",
            "telefone":"Telefone de contato","data_nascimento":"Data de nascimento","uf_nascimento":"Estado de nascimento",
            "cidade_nascimento":"Cidade de nascimento","cpf":"CPF","pis":"PIS/PASEP/NIT",
            "rg_numero":"RG","rg_orgao":"Órgão emissor do RG","rg_expedicao":"Expedição do RG",
            "data_admissao":"Data de admissão","salario":"Salário","funcao":"Função/cargo",
            "horario_trabalho":"Horário de trabalho","contrato_experiencia":"Contrato de experiência",
            "grau_instrucao":"Escolaridade"
        }
        missing=[]
        for step in range(4):
            if not self.step_complete(step):
                for k,label in labels.items():
                    if self.is_required(k) and not self.filled(k) and (k,label) not in missing:
                        missing.append((k,label))
        return missing

    def build_review(self):
        r=self.section_title("5. Revisão","Confira o cadastro antes de gerar a ficha.")
        missing=self.missing_fields()
        if missing:
            g,rr=self.group(r,"Pendências","Clique em uma pendência para voltar à etapa correspondente.")
            map_step={"nome":0,"cep":0,"endereco":0,"bairro":0,"uf":0,"cidade":0,"telefone":0,"data_nascimento":0,"uf_nascimento":0,"cidade_nascimento":0,
                      "cpf":1,"pis":1,"rg_numero":1,"rg_orgao":1,"rg_expedicao":1,
                      "data_admissao":3,"salario":3,"funcao":3,"horario_trabalho":3,"contrato_experiencia":3,"grau_instrucao":3}
            for k,label in missing[:12]:
                ctk.CTkButton(g,text=f"• {label}",anchor="w",fg_color="transparent",hover_color="#f3dddd",
                              text_color=RED,font=FONT_BODY,command=lambda kk=k:self.goto_step(map_step.get(kk,0))).grid(
                    row=rr,column=0,columnspan=2,sticky="ew",padx=12,pady=2); rr+=1
            r+=1
        else:
            ok=ctk.CTkFrame(self.form,fg_color="#eef7f1",border_color="#c7dfd0",border_width=1,corner_radius=10)
            ok.grid(row=r,column=0,columnspan=2,sticky="ew",padx=14,pady=9)
            ctk.CTkLabel(ok,text="✓ Todas as informações obrigatórias foram preenchidas.",text_color=GREEN,
                         font=("Segoe UI",14,"bold")).pack(anchor="w",padx=14,pady=14); r+=1

        g,rr=self.group(r,"Resumo")
        company=self.company_var.get()
        summary=[
            ("Empresa",company),("Nome",self.V("nome").get()),("CPF",self.format_cpf(self.V("cpf").get())),
            ("Função / cargo",self.V("funcao").get()),("Admissão",self.format_date(self.V("data_admissao").get())),
            ("Salário",self.V("salario").get()),("Escolaridade",self.V("grau_instrucao").get()),
            ("Dependentes",str(len(self.dependentes)))
        ]
        for label,val in summary:
            ctk.CTkLabel(g,text=label,text_color=MUTED,font=FONT_LABEL).grid(row=rr,column=0,sticky="w",padx=14,pady=6)
            ctk.CTkLabel(g,text=val or "Não informado",text_color=TEXT,font=FONT_BODY).grid(row=rr,column=1,sticky="w",padx=14,pady=6); rr+=1

        # document validation notices
        cpf=self.V("cpf").get()
        if cpf and len(only_digits(cpf))==11 and not cpf_valid(cpf):
            ctk.CTkLabel(g,text="⚠ CPF com dígitos verificadores inválidos.",text_color=AMBER,font=FONT_BODY).grid(row=rr,column=0,columnspan=2,sticky="w",padx=14,pady=8)


        actions=ctk.CTkFrame(self.form,fg_color="transparent")
        actions.grid(row=r+1,column=0,columnspan=2,sticky="ew",padx=14,pady=(14,18))
        ctk.CTkButton(
            actions,text="Visualizar ficha",command=self.preview_pdf,
            width=160,height=42,fg_color="#d9dde0",hover_color="#cbd1d5",
            text_color=TEXT,font=("Segoe UI",13,"bold")
        ).pack(side="right")

    # -------- keyboard arrows --------
    def bind_arrows(self):
        focusables=[]
        def walk(w):
            for c in w.winfo_children():
                if isinstance(c,(ctk.CTkEntry,ctk.CTkOptionMenu,ctk.CTkRadioButton)):
                    focusables.append(c)
                walk(c)
        walk(self.form)

        def center(w):
            try: return (w.winfo_rootx()+w.winfo_width()/2,w.winfo_rooty()+w.winfo_height()/2)
            except Exception: return (0,0)

        def move_vertical(w,d):
            x,y=center(w); cand=[]
            for o in focusables:
                if o==w or not o.winfo_ismapped():
                    continue
                ox,oy=center(o); dx,dy=ox-x,oy-y
                if d=="D" and dy>8:
                    score=dy+abs(dx)*1.7
                elif d=="U" and dy<-8:
                    score=-dy+abs(dx)*1.7
                else:
                    continue
                cand.append((score,o))
            if cand:
                cand.sort(key=lambda z:z[0])
                try: cand[0][1].focus_set()
                except Exception: pass

        for w in focusables:
            for key,d in [("<Up>","U"),("<Down>","D")]:
                try:
                    w.bind(key,lambda e,ww=w,dd=d:(move_vertical(ww,dd),"break")[1])
                except Exception:
                    pass

    # -------- format helpers --------
    def format_date(self,d):
        x=only_digits(d)
        if len(x)==8: return f"{x[:2]}/{x[2:4]}/{x[4:]}"
        return d

    def format_cpf(self,d):
        x=only_digits(d)
        if len(x)==11: return f"{x[:3]}.{x[3:6]}.{x[6:9]}-{x[9:]}"
        return d

    def format_cnpj(self,d):
        x=only_digits(d)
        if len(x)==14: return f"{x[:2]}.{x[2:5]}.{x[5:8]}/{x[8:12]}-{x[12:]}"
        return d

    def format_phone(self,d):
        x=only_digits(d)
        if len(x)==11: return f"({x[:2]}) {x[2:7]}-{x[7:]}"
        if len(x)==10: return f"({x[:2]}) {x[2:6]}-{x[6:]}"
        return d

    def format_cep(self,d):
        x=only_digits(d)
        if len(x)==8: return f"{x[:5]}-{x[5:]}"
        return d

    def display_value(self,key,val):
        if not val or val=="Selecione": return ""
        if key in {"data_nascimento","ctps_emissao","rg_expedicao","chegada_brasil","naturalizacao",
                   "orgao_classe_validade","cnh_expedicao","cnh_validade","cnh_primeira_habilitacao",
                   "pensao_nascimento","data_admissao"}: return self.format_date(val)
        if key=="telefone": return self.format_phone(val)
        if key in {"cpf","pensao_cpf"}: return self.format_cpf(val)
        if key in {"outros_vinculos_cnpj","sindicato_cnpj"}: return self.format_cnpj(val)
        if key=="cep": return self.format_cep(val)
        return val

    # -------- Save / PDF --------
    def data_dict(self):
        data={k:v.get() for k,v in self.vars.items()} | {
            "dependentes":self.dependentes,
            "consignados":self.consignados
        }
        cidade=data.get("cidade_nascimento","")
        uf=data.get("uf_nascimento","")
        data["municipio_nascimento"] = " / ".join(
            x for x in (cidade,uf) if x and x!="Selecione"
        )
        # Mantém o campo antigo apenas para compatibilidade.
        data["consignado_contrato"] = (
            self.consignados[0].get("contrato","")
            if self.consignados else ""
        )
        return data

    def open_folder(self,path):
        path=Path(path)
        path.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=="nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open",str(path)])
        except Exception:
            messagebox.showinfo("Pasta",f"Pasta:\n{path}")

    def open_local_file(self,path):
        path=str(path)
        try:
            if os.name=="nt":
                os.startfile(path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open",path])
        except Exception:
            messagebox.showinfo("Arquivo gerado",f"Arquivo criado em:\n{path}")

    def preview_pdf(self):
        d=self.data_dict()
        company=self.company_var.get()
        try:
            path=self.generate_pdf(0,d,company,preview=True,company_id=self.company_map.get(company))
            self.open_local_file(path)
        except Exception as exc:
            messagebox.showerror("Visualizar ficha",f"Não foi possível gerar a visualização.\n\n{exc}")

    def find_duplicate_cpf(self,cpf,exclude_id=None):
        digits=only_digits(cpf)
        if len(digits)!=11:
            return None
        for x in rows("SELECT id,nome,cpf,excluido_em FROM admissoes WHERE cpf IS NOT NULL AND cpf<>''",()):
            if exclude_id and int(x["id"])==int(exclude_id):
                continue
            if only_digits(x["cpf"] or "")==digits:
                return x
        return None

    def save_and_pdf(self):
        if not self.step_complete(4):
            if not messagebox.askyesno(
                "Informações pendentes",
                "Ainda existem informações obrigatórias pendentes. Deseja gerar a ficha mesmo assim?"
            ):
                return

        d=self.data_dict()
        cpf=d.get("cpf","")
        duplicate=self.find_duplicate_cpf(cpf,self.current_edit_id)
        if duplicate:
            if duplicate["excluido_em"]:
                messagebox.showwarning(
                    "CPF já cadastrado",
                    f"Este CPF já possui um cadastro na Lixeira ({duplicate['nome'] or 'sem nome'}).\n\n"
                    "Restaure o cadastro existente antes de criar outro com o mesmo CPF."
                )
                self.show_trash()
            else:
                if messagebox.askyesno(
                    "CPF já cadastrado",
                    f"Este CPF já possui uma admissão salva para:\n\n{duplicate['nome'] or 'sem nome'}\n\nDeseja abrir o cadastro existente?"
                ):
                    self.load_employee_for_edit(int(duplicate["id"]))
            return

        company_id=self.company_map.get(self.company_var.get())
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_pdf=""
        try:
            if self.current_edit_id:
                aid=self.current_edit_id
                old=rows("SELECT pdf_path FROM admissoes WHERE id=?",(aid,))
                old_pdf=(old[0]["pdf_path"] or "") if old else ""
                execute(
                    """UPDATE admissoes
                       SET empresa_id=?, atualizado_em=?, nome=?, cpf=?, funcao=?, data_admissao=?, dados_json=?, excluido_em=NULL
                       WHERE id=?""",
                    (company_id,now,d.get("nome",""),d.get("cpf",""),d.get("funcao",""),d.get("data_admissao",""),json.dumps(d,ensure_ascii=False),aid)
                )
                self.record_history(aid,"Dados alterados","Cadastro atualizado.",d.get("nome",""),d.get("cpf",""))
                action="Cadastro atualizado"
            else:
                aid=execute(
                    """INSERT INTO admissoes(
                           empresa_id,criado_em,atualizado_em,nome,cpf,funcao,data_admissao,dados_json,excluido_em,pdf_path,pdf_excluido
                       ) VALUES(?,?,?,?,?,?,?,?,NULL,'',0)""",
                    (company_id,now,now,d.get("nome",""),d.get("cpf",""),d.get("funcao",""),d.get("data_admissao",""),json.dumps(d,ensure_ascii=False))
                )
                self.record_history(aid,"Cadastro criado","Nova admissão cadastrada.",d.get("nome",""),d.get("cpf",""))
                action="Admissão salva"

            path=self.generate_pdf(aid,d,self.company_var.get(),company_id=company_id)
            execute("UPDATE admissoes SET pdf_path=?,pdf_excluido=0 WHERE id=?",(str(path),aid))
            self.record_history(aid,"Nova ficha PDF gerada",Path(path).name,d.get("nome",""),d.get("cpf",""))

            if old_pdf and old_pdf != str(path):
                safe_unlink(old_pdf)

            self.clear_draft()
            self.current_edit_id=None
            self.show_employees(highlight_id=aid)
            self.set_status(f"✓ {action} e ficha PDF gerados com sucesso.","ok",7000)
        except Exception as exc:
            self.set_status("Cadastro salvo, mas a geração do PDF falhou.","error",0)
            messagebox.showerror("Gerar PDF",f"O cadastro foi salvo, mas não foi possível gerar a ficha.\n\n{exc}")

    def generate_pdf(self,aid,d,company,preview=False,company_id=None):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        safe=safe_pdf_filename(d.get("nome","Funcionário"))

        if preview:
            path=DATA_DIR/"visualizacao_ficha.pdf"
        else:
            path=PDF_DIR/f"Ficha_Admissao_{safe}_{aid}.pdf"

        styles=getSampleStyleSheet()
        title=ParagraphStyle(
            "title",parent=styles["Title"],
            fontName="Helvetica-Bold",fontSize=12.3,leading=14.3,
            alignment=TA_CENTER,spaceAfter=4
        )
        company_style=ParagraphStyle(
            "company",parent=styles["Normal"],
            fontName="Helvetica-Bold",fontSize=9.4,leading=11,
            alignment=TA_CENTER,spaceAfter=1
        )
        cnpj_style=ParagraphStyle(
            "cnpj",parent=styles["Normal"],
            fontName="Helvetica",fontSize=8.5,leading=10,
            alignment=TA_CENTER,spaceAfter=5
        )
        normal=ParagraphStyle(
            "normalx",parent=styles["Normal"],
            fontName="Helvetica",fontSize=8.2,leading=9.5
        )
        section=ParagraphStyle(
            "section",parent=normal,
            fontName="Helvetica-Bold",fontSize=9.3,
            spaceBefore=4,spaceAfter=2
        )

        doc=SimpleDocTemplate(
            str(path),pagesize=A4,
            leftMargin=20,rightMargin=20,
            topMargin=18,bottomMargin=22
        )

        razao,cnpj=self.company_pdf_details(company_id,company)
        story=[
            Paragraph("FICHA DE INFORMAÇÕES PARA ADMISSÃO DE FUNCIONÁRIO",title),
            Paragraph(razao or company or "EMPRESA NÃO INFORMADA",company_style)
        ]
        if cnpj:
            story.append(Paragraph(f"CNPJ: {cnpj}",cnpj_style))
        else:
            story.append(Spacer(1,3))

        OMIT_NO={
            "estrangeiro","orgao_classe","possui_cnh",
            "deficiencia_motora","deficiencia_visual",
            "deficiencia_auditiva","reabilitado",
            "outros_vinculos","sindicato","pensao","consignado"
        }

        def clean(key):
            val=self.display_value(key,d.get(key,"")).strip()
            if not val or val=="Selecione":
                return ""
            if key in OMIT_NO and val=="Não":
                return ""
            return val

        def p(text,bold=False):
            if text is None:
                text=""
            safe_text=str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            if bold:
                safe_text=f"<b>{safe_text}</b>"
            return Paragraph(safe_text,normal)

        def add_section(name,pairs):
            items=[]
            for label,key in pairs:
                value=clean(key)
                if value:
                    items.append((label,value))
            if not items:
                return

            rows_data=[]
            for i in range(0,len(items),2):
                left=items[i]
                right=items[i+1] if i+1<len(items) else ("","")
                rows_data.append([
                    p(left[0],True),p(left[1]),
                    p(right[0],True) if right[0] else "",
                    p(right[1]) if right[1] else ""
                ])

            t=Table(
                rows_data,
                colWidths=[92,170,92,170],
                hAlign="LEFT",
                repeatRows=0
            )
            t.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#90969b")),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("BACKGROUND",(0,0),(-1,-1),colors.white),
                ("LEFTPADDING",(0,0),(-1,-1),3.2),
                ("RIGHTPADDING",(0,0),(-1,-1),3.2),
                ("TOPPADDING",(0,0),(-1,-1),2.2),
                ("BOTTOMPADDING",(0,0),(-1,-1),2.2),
            ]))
            story.append(Paragraph(name,section))
            story.append(t)

        add_section("Dados pessoais",[
            ("Nome","nome"),("CEP","cep"),("Endereço","endereco"),("Bairro","bairro"),
            ("Estado","uf"),("Cidade","cidade"),("Telefone","telefone"),
            ("Primeiro emprego","primeiro_emprego"),("Data de nascimento","data_nascimento"),
            ("Estado de nascimento","uf_nascimento"),("Cidade de nascimento","cidade_nascimento"),
            ("Sexo","sexo"),("Raça / cor","raca_cor"),("Altura","altura"),("Peso","peso"),
            ("Cor dos cabelos","cor_cabelos"),("Cor dos olhos","cor_olhos"),
            ("Tipagem sanguínea","tipagem_sanguinea"),("Estado civil","estado_civil"),
            ("Cônjuge","nome_conjuge"),("Nome da mãe","nome_mae"),("Nome do pai","nome_pai")
        ])

        add_section("Documentos",[
            ("CPF","cpf"),("PIS / PASEP / NIT","pis"),
            ("Carteira de trabalho digital","carteira_digital"),
            ("Número da CTPS","ctps_numero"),("Série e UF da CTPS","ctps_serie_uf"),
            ("Emissão CTPS","ctps_emissao"),("RG","rg_numero"),
            ("Órgão emissor RG","rg_orgao"),("Outro órgão emissor","rg_orgao_outro"),
            ("Expedição RG","rg_expedicao"),("Título de Eleitor","titulo_eleitor"),
            ("Zona","zona"),("Seção","secao"),("Estrangeiro","estrangeiro"),
            ("RNE / órgão / expedição","rne_orgao_data"),
            ("Chegada ao Brasil","chegada_brasil"),("Naturalização","naturalizacao"),
            ("Casado(a) com brasileiro(a)","casado_brasileiro"),
            ("Filhos com brasileiro(a)","filhos_brasileiro"),
            ("Registro em órgão de classe","orgao_classe"),
            ("Número do registro","orgao_classe_numero"),
            ("Órgão emissor / expedição","orgao_classe_emissor_data"),
            ("Validade do registro","orgao_classe_validade"),
            ("Possui CNH","possui_cnh"),("CNH","cnh_numero"),
            ("Categoria","cnh_categoria"),("Expedição CNH","cnh_expedicao"),
            ("Validade CNH","cnh_validade"),
            ("Primeira habilitação","cnh_primeira_habilitacao")
        ])

        add_section("Condições e residência",[
            ("Residência própria","residencia_propria"),
            ("Imóvel adquirido com FGTS","fgts_imovel"),
            ("Deficiência motora","deficiencia_motora"),
            ("Deficiência visual","deficiencia_visual"),
            ("Deficiência auditiva","deficiencia_auditiva"),
            ("Trabalhador reabilitado","reabilitado"),
            ("Outra deficiência","outra_deficiencia")
        ])

        pdf_dependentes=d.get("dependentes",[]) or []
        if pdf_dependentes:
            story.append(Paragraph("Dependentes",section))
            dep_rows=[
                [
                    p("Tipo",True),p("Nome",True),p("Nascimento",True),
                    p("CPF",True),p("IRRF",True),p("Salário-família",True)
                ]
            ]
            for x in pdf_dependentes:
                dep_rows.append([
                    p(x.get("tipo","")),p(x.get("nome","")),
                    p(x.get("nascimento","")),p(x.get("cpf","")),
                    p(x.get("irrf","")),p(x.get("salario_familia",""))
                ])
            t=Table(
                dep_rows,
                colWidths=[110,128,76,88,45,79],
                repeatRows=1
            )
            t.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#90969b")),
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eeeeee")),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),2.5),
                ("RIGHTPADDING",(0,0),(-1,-1),2.5),
                ("TOPPADDING",(0,0),(-1,-1),2),
                ("BOTTOMPADDING",(0,0),(-1,-1),2),
            ]))
            story.append(t)

        add_section("Contato e informações trabalhistas",[
            ("E-mail principal","email_principal"),
            ("E-mail alternativo","email_alternativo"),
            ("Filhos para IR","qtd_filhos_ir"),
            ("Filhos para salário-família","qtd_filhos_salario_familia"),
            ("Outros vínculos","outros_vinculos"),
            ("CNPJ de outra empresa","outros_vinculos_cnpj"),
            ("Outra remuneração","outra_remuneracao"),
            ("Filiado a sindicato","sindicato"),
            ("CNPJ do sindicato","sindicato_cnpj"),
            ("Pensão alimentícia","pensao"),("Beneficiário","pensao_nome"),
            ("Nascimento beneficiário","pensao_nascimento"),
            ("CPF beneficiário","pensao_cpf"),("Banco","pensao_banco"),
            ("Agência","pensao_agencia"),("Conta","pensao_conta"),
            ("Gravidez","gravidez"),("Acidente de trabalho","acidente_trabalho"),
            ("Acidente","acidente"),("Atestado de Saúde","atestado_saude"),
            ("Nome social","nome_social")
        ])

        loans=d.get("consignados",[]) or []
        legacy=(d.get("consignado_contrato") or "").strip()
        if not loans and legacy:
            loans=[{"contrato":legacy}]
        if loans:
            story.append(Paragraph("Empréstimos consignados / CLT",section))
            loan_rows=[[p("Nº",True),p("Número do contrato",True)]]
            for i,loan in enumerate(loans,1):
                loan_rows.append([p(str(i)),p(loan.get("contrato",""))])
            loan_table=Table(loan_rows,colWidths=[35,489],repeatRows=1)
            loan_table.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#90969b")),
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eeeeee")),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),3),
                ("RIGHTPADDING",(0,0),(-1,-1),3),
                ("TOPPADDING",(0,0),(-1,-1),2),
                ("BOTTOMPADDING",(0,0),(-1,-1),2),
            ]))
            story.append(loan_table)

        add_section("Dados da admissão",[
            ("Data de admissão","data_admissao"),("Salário","salario"),
            ("Função / cargo","funcao"),("Horário de trabalho","horario_trabalho"),
            ("Sábado","horario_sabado"),
            ("Contrato de experiência","contrato_experiencia"),
            ("Escolaridade","grau_instrucao"),
            ("Vale-transporte","vale_transporte")
        ])

        story += [
            Spacer(1,12),
            Paragraph(
                "_______________________________________________",
                ParagraphStyle(
                    "sig",parent=normal,alignment=TA_CENTER,
                    fontSize=9,leading=10
                )
            ),
            Paragraph(
                "Assinatura do funcionário",
                ParagraphStyle(
                    "sig2",parent=normal,alignment=TA_CENTER,
                    fontSize=7.8,leading=9
                )
            )
        ]

        doc.build(story)
        return path

    # -------- employees/generated --------
    def company_pdf_details(self,company_id=None,company_display=""):
        if company_id:
            result=rows(
                "SELECT razao_social,cnpj FROM empresas WHERE id=?",
                (company_id,)
            )
            if result:
                x=result[0]
                return (x["razao_social"] or company_display or "").strip(), (x["cnpj"] or "").strip()

        if company_display:
            result=rows(
                """SELECT razao_social,cnpj FROM empresas
                   WHERE nome_fantasia=? OR razao_social=?
                   ORDER BY id LIMIT 1""",
                (company_display,company_display)
            )
            if result:
                x=result[0]
                return (x["razao_social"] or company_display).strip(), (x["cnpj"] or "").strip()

        return company_display or "", ""

    def company_name_by_id(self,company_id):
        if not company_id:
            return ""
        result=rows(
            "SELECT razao_social,nome_fantasia FROM empresas WHERE id=?",
            (company_id,)
        )
        if not result:
            return ""
        x=result[0]
        return (x["nome_fantasia"] or "").strip() or x["razao_social"]

    def selected_employee_id(self):
        if not hasattr(self,"employee_tree"):
            return None
        sel=self.employee_tree.selection()
        if not sel:
            messagebox.showwarning("Admissões Salvas","Selecione um cadastro.")
            return None
        vals=self.employee_tree.item(sel[0],"values")
        return int(vals[0]) if vals else None

    def edit_selected_employee(self):
        aid=self.selected_employee_id()
        if aid:
            self.load_employee_for_edit(aid)

    def show_selected_history(self):
        aid=self.selected_employee_id()
        if aid:
            self.show_history_dialog(aid)

    def load_employee_for_edit(self,aid):
        self.set_active_nav("new")
        result=rows(
            "SELECT id,empresa_id,dados_json FROM admissoes WHERE id=?",
            (aid,)
        )
        if not result:
            messagebox.showerror("Admissões Salvas","Cadastro não encontrado.")
            return
        record=result[0]
        try:
            data=json.loads(record["dados_json"] or "{}")
        except Exception:
            data={}

        company=self.company_name_by_id(record["empresa_id"])

        self.clear_draft()
        self.show_new_admission(load_draft=False)
        self.restoring=True
        self.current_edit_id=aid

        if company:
            self.company_var.set(company)

        dep=data.pop("dependentes",[]) or []
        loans=data.pop("consignados",[]) or []
        legacy_contract=(data.get("consignado_contrato") or "").strip()
        if not loans and legacy_contract:
            loans=[{"contrato":legacy_contract}]
        for key,value in data.items():
            self.V(key).set("" if value is None else str(value))
        self.dependentes=dep
        self.consignados=loans
        self.restoring=False

        self.current_step=0
        self.render_step()
        self.scroll_top()
        self.update_progress()

    def admission_pdf_path(self,aid):
        result=rows("SELECT pdf_path,nome FROM admissoes WHERE id=?",(aid,))
        if not result:
            return None
        stored=(result[0]["pdf_path"] or "").strip()
        if stored and Path(stored).exists():
            return Path(stored)
        files=sorted(PDF_DIR.glob(f"*_{aid}.pdf"),key=lambda p:p.stat().st_mtime,reverse=True)
        return files[0] if files else None

    def regenerate_selected_employee(self):
        aid=self.selected_employee_id()
        if not aid:
            return
        result=rows("SELECT empresa_id,dados_json,nome,cpf FROM admissoes WHERE id=? AND excluido_em IS NULL",(aid,))
        if not result:
            messagebox.showerror("Admissões Salvas","Cadastro não encontrado.")
            return
        record=result[0]
        try:
            data=json.loads(record["dados_json"] or "{}")
        except Exception:
            data={}
        company=self.company_name_by_id(record["empresa_id"])
        try:
            path=self.generate_pdf(aid,data,company,company_id=record["empresa_id"])
            execute("UPDATE admissoes SET pdf_path=?,pdf_excluido=0,atualizado_em=? WHERE id=?",(str(path),datetime.now().strftime("%Y-%m-%d %H:%M:%S"),aid))
            self.record_history(aid,"Nova ficha PDF gerada",Path(path).name,record["nome"] or "",record["cpf"] or "")
            self.set_status(f"✓ PDF regenerado: {Path(path).name}","ok")
        except Exception as exc:
            messagebox.showerror("Gerar PDF",f"Não foi possível gerar a ficha.\n\n{exc}")

    def print_selected_employee(self):
        aid=self.selected_employee_id()
        if not aid:
            return
        path=self.admission_pdf_path(aid)
        if not path:
            self.regenerate_selected_employee()
            path=self.admission_pdf_path(aid)
        if not path:
            messagebox.showwarning("Imprimir","Não há PDF disponível para esta admissão.")
            return
        try:
            if os.name=="nt":
                os.startfile(str(path),"print")
            else:
                subprocess.Popen(["lp",str(path)])
            self.set_status("✓ Enviado para impressão.","ok")
        except Exception as exc:
            messagebox.showerror("Imprimir",f"Não foi possível enviar a ficha para impressão.\n\n{exc}")

    def delete_selected_employee(self):
        aid=self.selected_employee_id()
        if not aid:
            return
        result=rows("SELECT id,nome,cpf,pdf_path FROM admissoes WHERE id=? AND excluido_em IS NULL",(aid,))
        if not result:
            return
        x=result[0]
        name=x["nome"] or "Sem nome"
        if not messagebox.askyesno("Excluir ficha",f'Confirma a exclusão da admissão de "{name}"?\n\nO cadastro será movido para a Lixeira por {TRASH_RETENTION_DAYS} dias.'):
            return
        delete_pdf=False
        if x["pdf_path"] and Path(x["pdf_path"]).exists():
            delete_pdf=messagebox.askyesno("PDF correspondente", "Deseja excluir também o PDF correspondente?\n\nSIM = excluir cadastro e PDF\nNÃO = manter o PDF salvo.")
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execute("UPDATE admissoes SET excluido_em=?,pdf_excluido=? WHERE id=?",(now,1 if delete_pdf else 0,aid))
        if delete_pdf and x["pdf_path"]:
            safe_unlink(x["pdf_path"])
        self.record_history(aid,"Cadastro enviado para a Lixeira",\
                            "PDF excluído junto com o cadastro." if delete_pdf else "PDF mantido.",x["nome"] or "",x["cpf"] or "")
        self.refresh_admission_tree()
        self.set_status(f"✓ Cadastro de {name} movido para a Lixeira.","ok")

    def refresh_admission_tree(self,query="",highlight_id=None):
        if not hasattr(self,"employee_tree"):
            return
        tree=self.employee_tree
        for item in tree.get_children():
            tree.delete(item)

        q=(query or "").strip()
        if q:
            like=f"%{q}%"
            data=rows(
                """SELECT id,nome,cpf,funcao,data_admissao,criado_em,atualizado_em
                   FROM admissoes
                   WHERE excluido_em IS NULL AND (nome LIKE ? OR cpf LIKE ? OR funcao LIKE ?)
                   ORDER BY id DESC""",
                (like,like,like)
            )
        else:
            data=rows(
                """SELECT id,nome,cpf,funcao,data_admissao,criado_em,atualizado_em
                   FROM admissoes WHERE excluido_em IS NULL ORDER BY id DESC"""
            )

        target=None
        for x in data:
            item=tree.insert(
                "","end",
                values=(
                    x["id"],x["nome"],self.format_cpf(x["cpf"]),
                    x["funcao"],self.format_date(x["data_admissao"]),
                    x["criado_em"],x["atualizado_em"]
                )
            )
            if highlight_id and int(x["id"])==int(highlight_id):
                target=item

        if hasattr(self,"admission_count_label"):
            self.admission_count_label.configure(text=f"{len(data)} registro(s)")

        if target:
            tree.selection_set(target)
            tree.focus(target)
            tree.see(target)

    def show_employees(self,highlight_id=None):
        self.set_active_nav("employees")
        self.clear_content()
        self.page_header("ADMISSÕES SALVAS","Pesquise, abra, gere, imprima, consulte o histórico ou exclua uma admissão.")

        outer=ctk.CTkFrame(self.content,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
        outer.grid(row=1,column=0,sticky="nsew",padx=32,pady=(0,18))
        outer.grid_columnconfigure(0,weight=1)
        outer.grid_rowconfigure(2,weight=1)

        searchbar=ctk.CTkFrame(outer,fg_color="transparent")
        searchbar.grid(row=0,column=0,sticky="ew",padx=14,pady=(12,4))
        searchbar.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(searchbar,text="PESQUISAR",text_color=LABEL,font=("Segoe UI",12,"bold")).grid(row=0,column=0,padx=(0,8),sticky="w")
        self.employee_search_var=tk.StringVar()
        search=ctk.CTkEntry(searchbar,textvariable=self.employee_search_var,height=40,placeholder_text="Nome, CPF ou função...",fg_color="#eef1f3",border_color="#aeb6bd",font=FONT_INPUT)
        search.grid(row=0,column=1,sticky="ew")
        self.admission_count_label=ctk.CTkLabel(searchbar,text="",text_color=MUTED,font=("Segoe UI",11,"bold"))
        self.admission_count_label.grid(row=0,column=2,padx=(12,0),sticky="e")

        toolbar=ctk.CTkFrame(outer,fg_color="transparent")
        toolbar.grid(row=1,column=0,sticky="ew",padx=14,pady=(4,4))
        buttons=[
            ("ABRIR / EDITAR",self.edit_selected_employee,140,ACCENT,"white"),
            ("GERAR PDF",self.regenerate_selected_employee,105,"#d9dde0",TEXT),
            ("IMPRIMIR",self.print_selected_employee,90,"#d9dde0",TEXT),
            ("HISTÓRICO",self.show_selected_history,105,"#d9dde0",TEXT),
            ("EXCLUIR",self.delete_selected_employee,90,"#eadada",RED),
            ("LIXEIRA",self.show_trash,85,"#d9dde0",TEXT),
        ]
        for i,(text,cmd,width,bg,fg) in enumerate(buttons):
            ctk.CTkButton(toolbar,text=text,command=cmd,width=width,height=36,fg_color=bg,hover_color="#cbd1d5" if bg!="#eadada" else "#dfcaca",text_color=fg,font=("Segoe UI",10,"bold")).pack(side="left",padx=(0 if i==0 else 5,0))

        cols=("id","nome","cpf","funcao","data","criado","atualizado")
        style=ttk.Style()
        try:
            style.configure("RH.Treeview",font=("Segoe UI",10),rowheight=32,background="#f7f8f9",fieldbackground="#f7f8f9",foreground=TEXT)
            style.configure("RH.Treeview.Heading",font=("Segoe UI",10,"bold"),padding=6)
            style.map("RH.Treeview",background=[("selected","#cfd5da")],foreground=[("selected",TEXT)])
        except Exception:
            pass
        tree=ttk.Treeview(outer,columns=cols,show="headings",style="RH.Treeview")
        self.employee_tree=tree
        specifications=[("id","ID",45),("nome","Nome",220),("cpf","CPF",125),("funcao","Função / cargo",175),("data","Admissão",90),("criado","Criado em",140),("atualizado","Atualizado em",140)]
        for c,t,w in specifications:
            tree.heading(c,text=t)
            tree.column(c,width=w,anchor="w")
        tree.grid(row=2,column=0,sticky="nsew",padx=14,pady=(6,14))
        tree.bind("<Double-1>",lambda _e:self.edit_selected_employee())
        tree.bind("<Return>",lambda _e:self.edit_selected_employee())
        self.employee_search_var.trace_add("write",lambda *_:self.refresh_admission_tree(self.employee_search_var.get()))
        self.refresh_admission_tree(highlight_id=highlight_id)

    def restore_admission(self,aid):
        result=rows("SELECT id,nome,cpf,pdf_path,pdf_excluido FROM admissoes WHERE id=? AND excluido_em IS NOT NULL",(aid,))
        if not result:
            messagebox.showwarning("Lixeira","Cadastro não encontrado na Lixeira.")
            return
        x=result[0]
        duplicate=self.find_duplicate_cpf(x["cpf"] or "",aid)
        if duplicate and not duplicate["excluido_em"]:
            messagebox.showwarning("Restaurar","Já existe outro cadastro ativo com este CPF. Resolva a duplicidade antes de restaurar.")
            return
        execute("UPDATE admissoes SET excluido_em=NULL WHERE id=?",(aid,))
        self.record_history(aid,"Cadastro restaurado","Registro restaurado da Lixeira.",x["nome"] or "",x["cpf"] or "")
        self.set_status(f"✓ Cadastro de {x['nome'] or 'funcionário'} restaurado.","ok")
        self.show_trash()

    def permanently_delete_admission(self,aid,automatic=False):
        result=rows("SELECT id,nome,cpf,pdf_path,pdf_excluido,excluido_em FROM admissoes WHERE id=? AND excluido_em IS NOT NULL",(aid,))
        if not result:
            return
        x=result[0]
        if not automatic:
            if not messagebox.askyesno("Exclusão definitiva",f'Excluir definitivamente "{x["nome"] or "Sem nome"}"?\n\nEssa ação não poderá ser desfeita.'):
                return
        self.record_history(aid,"Exclusão definitiva", "Registro removido permanentemente da Lixeira.",x["nome"] or "",x["cpf"] or "")
        if not x["pdf_excluido"] and x["pdf_path"]:
            safe_unlink(x["pdf_path"])
        execute("DELETE FROM admissoes WHERE id=?",(aid,))
        if not automatic:
            self.set_status("✓ Cadastro excluído definitivamente.","ok")
            self.show_trash()

    def show_trash(self):
        self.purge_expired_trash()
        self.set_active_nav("trash")
        self.clear_content()
        self.page_header("LIXEIRA",f"Cadastros excluídos ficam disponíveis para restauração por {TRASH_RETENTION_DAYS} dias.")
        outer=ctk.CTkFrame(self.content,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
        outer.grid(row=1,column=0,sticky="nsew",padx=32,pady=(0,18))
        outer.grid_columnconfigure(0,weight=1)
        outer.grid_rowconfigure(1,weight=1)

        top=ctk.CTkFrame(outer,fg_color="transparent")
        top.grid(row=0,column=0,sticky="ew",padx=14,pady=(12,8))
        top.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(top,text="Lixeira de admissões",text_color=TEXT,font=("Segoe UI",17,"bold")).grid(row=0,column=0,sticky="w")
        ctk.CTkButton(top,text="VOLTAR ÀS ADMISSÕES",command=self.show_employees,width=170,height=34,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,font=("Segoe UI",10,"bold")).grid(row=0,column=1,sticky="e")

        frame=ctk.CTkScrollableFrame(outer,fg_color="transparent")
        frame.grid(row=1,column=0,sticky="nsew",padx=8,pady=(0,12))
        frame.grid_columnconfigure(0,weight=1)
        data=rows("SELECT id,nome,cpf,funcao,excluido_em,pdf_path,pdf_excluido FROM admissoes WHERE excluido_em IS NOT NULL ORDER BY excluido_em DESC")
        if not data:
            ctk.CTkLabel(frame,text="A Lixeira está vazia.",text_color=MUTED,font=FONT_BODY).grid(row=0,column=0,sticky="w",padx=12,pady=14)
            return

        for i,x in enumerate(data):
            try:
                deleted=datetime.strptime(x["excluido_em"],"%Y-%m-%d %H:%M:%S")
                expires=deleted+timedelta(days=TRASH_RETENTION_DAYS)
                remaining=max(0,(expires-datetime.now()).days)
            except Exception:
                remaining=TRASH_RETENTION_DAYS
            card=ctk.CTkFrame(frame,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=8)
            card.grid(row=i,column=0,sticky="ew",padx=5,pady=4)
            card.grid_columnconfigure(0,weight=1)
            ctk.CTkLabel(card,text=x["nome"] or "Sem nome",text_color=TEXT,font=("Segoe UI",13,"bold")).grid(row=0,column=0,sticky="w",padx=12,pady=(9,2))
            detail=f"{self.format_cpf(x['cpf'] or '')} · {x['funcao'] or 'Função não informada'} · Excluído em {x['excluido_em']} · {remaining} dia(s) restantes"
            ctk.CTkLabel(card,text=detail,text_color=MUTED,font=FONT_SMALL,wraplength=560,justify="left").grid(row=1,column=0,sticky="w",padx=12,pady=(0,8))
            if x["pdf_excluido"]:
                pdf_note="PDF excluído"
            elif x["pdf_path"] and Path(x["pdf_path"]).exists():
                pdf_note="PDF mantido"
            else:
                pdf_note="PDF não encontrado"
            ctk.CTkLabel(card,text=pdf_note,text_color=MUTED,font=("Segoe UI",10,"italic")).grid(row=2,column=0,sticky="w",padx=12,pady=(0,8))
            actions=ctk.CTkFrame(card,fg_color="transparent")
            actions.grid(row=0,column=1,rowspan=3,padx=8,pady=7)
            ctk.CTkButton(actions,text="RESTAURAR",width=100,height=32,fg_color=ACCENT,hover_color=ACCENT_HOVER,font=("Segoe UI",10,"bold"),command=lambda aid=x["id"]:self.restore_admission(aid)).pack(side="left",padx=2)
            ctk.CTkButton(actions,text="HISTÓRICO",width=95,height=32,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,font=("Segoe UI",10,"bold"),command=lambda aid=x["id"]:self.show_history_dialog(aid)).pack(side="left",padx=2)
            ctk.CTkButton(actions,text="EXCLUIR DE VEZ",width=115,height=32,fg_color="#eadada",hover_color="#dfcaca",text_color=RED,font=("Segoe UI",10,"bold"),command=lambda aid=x["id"]:self.permanently_delete_admission(aid)).pack(side="left",padx=2)

    def show_generated(self):
        self.set_active_nav("pdf")
        self.clear_content()
        self.page_header("FICHAS PDF","Arquivos gerados pelo RH Fácil.")
        box=ctk.CTkFrame(self.content,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=10)
        box.grid(row=1,column=0,sticky="nsew",padx=32,pady=(0,18))
        box.grid_columnconfigure(0,weight=1)
        box.grid_rowconfigure(1,weight=1)
        head=ctk.CTkFrame(box,fg_color="transparent")
        head.grid(row=0,column=0,sticky="ew",padx=16,pady=(12,8))
        head.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(head,text=f"Pasta: {PDF_DIR}",text_color=MUTED,font=FONT_SMALL,wraplength=700,justify="left").grid(row=0,column=0,sticky="w")
        ctk.CTkButton(head,text="ABRIR PASTA",command=lambda:self.open_folder(PDF_DIR),width=120,height=34,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,font=("Segoe UI",11,"bold")).grid(row=0,column=1,sticky="e")
        list_frame=ctk.CTkScrollableFrame(box,fg_color="transparent")
        list_frame.grid(row=1,column=0,sticky="nsew",padx=8,pady=(0,12))
        list_frame.grid_columnconfigure(0,weight=1)
        files=sorted(PDF_DIR.glob("*.pdf"),key=lambda p:p.stat().st_mtime,reverse=True)
        if not files:
            ctk.CTkLabel(list_frame,text="Nenhuma ficha PDF gerada ainda.",text_color=MUTED,font=FONT_BODY).grid(row=0,column=0,sticky="w",padx=10,pady=12)
            return
        for i,pdf in enumerate(files):
            row=ctk.CTkFrame(list_frame,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=8)
            row.grid(row=i,column=0,sticky="ew",padx=5,pady=4)
            row.grid_columnconfigure(0,weight=1)
            ctk.CTkLabel(row,text=pdf.name,text_color=TEXT,font=FONT_BODY).grid(row=0,column=0,sticky="w",padx=12,pady=10)
            ctk.CTkButton(row,text="ABRIR",width=70,height=30,fg_color=ACCENT,hover_color=ACCENT_HOVER,command=lambda path=pdf:self.open_local_file(path),font=("Segoe UI",10,"bold")).grid(row=0,column=1,padx=4,pady=6)
            ctk.CTkButton(row,text="IMPRIMIR",width=82,height=30,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,command=lambda path=pdf:self.print_pdf_file(path),font=("Segoe UI",10,"bold")).grid(row=0,column=2,padx=(2,8),pady=6)

    def print_pdf_file(self,path):
        try:
            if os.name=="nt":
                os.startfile(str(path),"print")
            else:
                subprocess.Popen(["lp",str(path)])
            self.set_status("✓ Enviado para impressão.","ok")
        except Exception as exc:
            messagebox.showerror("Imprimir",f"Não foi possível imprimir a ficha.\n\n{exc}")


    def _time_minutes(self,value):
        try:
            h,m=[int(x) for x in value.strip().split(":")]
            if 0<=h<=23 and 0<=m<=59:
                return h*60+m
        except Exception:
            pass
        return None

    def _duration_minutes(self,entrada,saida_intervalo,retorno,saida):
        e=self._time_minutes(entrada)
        si=self._time_minutes(saida_intervalo)
        r=self._time_minutes(retorno)
        s=self._time_minutes(saida)
        if e is None or s is None:
            return None
        if si is not None and r is not None:
            first=si-e
            second=s-r
            if first<0 or second<0:
                return None
            return first+second
        total=s-e
        return total if total>=0 else None

    def _format_minutes(self,minutes):
        if minutes is None:
            return "—"
        return f"{minutes//60}h{minutes%60:02d}"

    def _schedule_preview_from_values(self):
        days=[code for code,var in self.schedule_days.items() if var.get()]
        if not days:
            return "Selecione pelo menos um dia."
        ent=self.schedule_vars["entrada"].get().strip()
        out_i=self.schedule_vars["saida_intervalo"].get().strip()
        ret=self.schedule_vars["retorno"].get().strip()
        out=self.schedule_vars["saida"].get().strip()

        weekday = ""
        if ent and out:
            weekday=f"{ent}-{out_i} / {ret}-{out}" if out_i and ret else f"{ent}-{out}"

        day_labels={"SEG":"Seg","TER":"Ter","QUA":"Qua","QUI":"Qui","SEX":"Sex","SAB":"Sáb","DOM":"Dom"}
        day_txt=", ".join(day_labels[d] for d in days)

        mon_out=self.schedule_vars["segunda_saida"].get().strip()
        sat_ent=self.schedule_vars["sabado_entrada"].get().strip()
        sat_out=self.schedule_vars["sabado_saida"].get().strip()

        preview=f"{day_txt}: {weekday}" if weekday else day_txt
        if "SEG" in days and mon_out and mon_out != out:
            preview += f" | Seg saída: {mon_out}"
        if "SAB" in days and sat_ent and sat_out:
            preview += f" | Sáb diferente: {sat_ent}-{sat_out}"
        return preview

    def _schedule_week_minutes(self):
        days=[code for code,var in self.schedule_days.items() if var.get()]
        weekday_minutes=self._duration_minutes(
            self.schedule_vars["entrada"].get(),
            self.schedule_vars["saida_intervalo"].get(),
            self.schedule_vars["retorno"].get(),
            self.schedule_vars["saida"].get()
        )
        if weekday_minutes is None:
            return None

        mon_minutes=None
        mon_out=self.schedule_vars["segunda_saida"].get().strip()
        if mon_out:
            mon_minutes=self._duration_minutes(
                self.schedule_vars["entrada"].get(),
                self.schedule_vars["saida_intervalo"].get(),
                self.schedule_vars["retorno"].get(),
                mon_out
            )

        sat_minutes=None
        sat_ent=self.schedule_vars["sabado_entrada"].get().strip()
        sat_out=self.schedule_vars["sabado_saida"].get().strip()
        if sat_ent and sat_out:
            e=self._time_minutes(sat_ent)
            s=self._time_minutes(sat_out)
            if e is not None and s is not None and s>=e:
                sat_minutes=s-e

        total=0
        for d in days:
            if d=="SEG" and mon_minutes is not None:
                total += mon_minutes
            elif d=="SAB" and sat_minutes is not None:
                total += sat_minutes
            else:
                total += weekday_minutes
        return total

    def update_schedule_preview(self,*_):
        if not hasattr(self,"schedule_preview_label"):
            return
        preview=self._schedule_preview_from_values()
        daily=self._duration_minutes(
            self.schedule_vars["entrada"].get(),
            self.schedule_vars["saida_intervalo"].get(),
            self.schedule_vars["retorno"].get(),
            self.schedule_vars["saida"].get()
        )
        weekly=self._schedule_week_minutes()
        self.schedule_preview_label.configure(text=preview)
        self.schedule_daily_label.configure(text=f"Carga diária: {self._format_minutes(daily)}")
        self.schedule_weekly_label.configure(text=f"Carga semanal: {self._format_minutes(weekly)}")

    def _record_used(self,kind,record_id,text_value=""):
        if kind=="empresa":
            return bool(rows("SELECT id FROM admissoes WHERE empresa_id=? LIMIT 1",(record_id,)))
        if not text_value:
            return False
        return bool(rows("SELECT id FROM admissoes WHERE dados_json LIKE ? LIMIT 1",(f"%{text_value}%",)))

    # -------- atualizações --------
    def check_updates_on_startup(self):
        if self._update_check_in_progress or self._update_prompted:
            return
        if not repository_configured():
            return
        self._update_check_in_progress=True
        threading.Thread(target=self._update_check_worker, args=(False,), daemon=True).start()

    def check_updates_now(self):
        if self._update_check_in_progress:
            return
        if not repository_configured():
            self.set_status("Configure o repositório do GitHub para habilitar as atualizações.", "warn", 7000)
            messagebox.showinfo(
                "Atualizações",
                "O repositório de atualizações ainda não foi configurado.\n\n"
                "Informe o endereço do repositório na aba ATUALIZAÇÕES."
            )
            return
        self._update_check_in_progress=True
        self.set_status("Consultando atualizações...", "info", 0)
        threading.Thread(target=self._update_check_worker, args=(True,), daemon=True).start()

    def _update_check_worker(self, manual=False):
        try:
            info=check_for_update(VERSION, load_repository())
        except Exception:
            info=None
        self.root.after(0, lambda:self._finish_update_check(info, manual))

    def _finish_update_check(self, info, manual=False):
        self._update_check_in_progress=False
        if not info:
            if manual:
                self.set_status("✓ RH Fácil já está na versão mais recente.", "ok", 5000)
                messagebox.showinfo("Atualizações", f"O RH Fácil já está atualizado.\n\nVersão instalada: {VERSION}")
            return
        self._offer_update(info)

    def _offer_update(self, info):
        if self._update_prompted:
            return
        self._update_prompted=True
        notes=(info.get("notes") or "").strip()
        if len(notes)>900:
            notes=notes[:900].rstrip()+"..."
        body=(
            f"Uma nova versão do RH Fácil está disponível.\n\n"
            f"Versão instalada: {VERSION}\n"
            f"Nova versão: {info.get('version','')}\n\n"
        )
        if notes:
            body += "Principais alterações:\n" + notes + "\n\n"
        body += "Deseja baixar e instalar agora?\n\nSe você escolher Não, a atualização poderá ser feita depois em Configurações → Atualizações."
        if messagebox.askyesno("Nova versão disponível", body):
            self._start_update_download(info)
        else:
            self._update_prompted=False
            self.set_status("Atualização disponível para instalação posterior.", "warn", 7000)

    def _start_update_download(self, info):
        self.set_status(f"Baixando {info.get('version','')}...", "info", 0)
        threading.Thread(target=self._download_update_worker, args=(info,), daemon=True).start()

    def _download_update_worker(self, info):
        try:
            update_dir=APP_CONFIG_DIR / "updates"
            package=update_dir / info["asset_name"]
            def progress(done,total):
                if total:
                    pct=int(done*100/total)
                    self.root.after(0, lambda p=pct:self.set_status(f"Baixando atualização... {p}%", "info", 0))
                else:
                    self.root.after(0, lambda:self.set_status("Baixando atualização...", "info", 0))
            downloaded=download_update(info, package, progress)
            self.root.after(0, lambda:self._launch_updater(downloaded, info["version"]))
        except Exception as exc:
            self.root.after(0, lambda e=exc:self._update_download_failed(e))

    def _update_download_failed(self, exc):
        self._update_prompted=False
        self.set_status("Não foi possível baixar a atualização.", "error", 9000)
        messagebox.showerror(
            "Atualização",
            "Não foi possível baixar ou validar a atualização.\n\n"
            f"Detalhes: {exc}\n\n"
            "A versão atual continua disponível normalmente."
        )

    def _launch_updater(self, package, version):
        updater=INSTALL_ROOT / "RH Facil Updater.exe"
        if getattr(sys, "frozen", False):
            command=[
                str(updater), "--apply",
                "--package", str(package),
                "--target-dir", str(INSTALL_ROOT),
                "--pid", str(os.getpid()),
                "--version", str(version),
                "--restart",
            ]
        else:
            updater_script=ROOT / "atualizador.py"
            command=[
                sys.executable, str(updater_script), "--apply",
                "--package", str(package),
                "--target-dir", str(INSTALL_ROOT),
                "--pid", str(os.getpid()),
                "--version", str(version),
                "--restart",
            ]
        if not updater.exists() and getattr(sys, "frozen", False):
            self._update_prompted=False
            messagebox.showerror("Atualização", "O componente atualizador não foi encontrado. Recompile o pacote do RH Fácil com a v0.3.7 ou superior.")
            return
        try:
            subprocess.Popen(command, cwd=str(INSTALL_ROOT), close_fds=True)
            self.set_status(f"Atualizando para {version}...", "ok", 0)
            self.root.after(500, self.root.destroy)
        except Exception as exc:
            self._update_prompted=False
            messagebox.showerror("Atualização", f"Não foi possível iniciar o atualizador.\n\n{exc}")

    def save_update_repository(self):
        value=self.update_repo_var.get().strip()
        if not value:
            messagebox.showwarning("Atualizações", "Informe o repositório do GitHub no formato dono/repositorio.")
            return
        try:
            repo=save_repository(value)
            self.update_repo_var.set(repo)
            self.update_repo_status.configure(text=f"Repositório configurado: {repo}", text_color=GREEN)
            self.set_status("✓ Repositório de atualizações salvo.", "ok")
        except Exception as exc:
            messagebox.showerror("Atualizações", f"Não foi possível salvar a configuração.\n\n{exc}")

    def build_update_settings(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        head=ctk.CTkFrame(parent,fg_color="transparent")
        head.grid(row=0,column=0,sticky="ew",padx=16,pady=(14,4))
        ctk.CTkLabel(head,text="ATUALIZAÇÕES",text_color=TEXT,font=("Segoe UI",22,"bold")).pack(side="left")

        card=ctk.CTkFrame(parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10)
        card.grid(row=1,column=0,sticky="ew",padx=16,pady=10)
        card.grid_columnconfigure(0,weight=1)

        ctk.CTkLabel(card,text="VERSÃO INSTALADA",text_color=LABEL,font=("Segoe UI",13,"bold")).grid(row=0,column=0,sticky="w",padx=16,pady=(14,3))
        ctk.CTkLabel(card,text=VERSION,text_color=TEXT,font=("Segoe UI",18,"bold")).grid(row=1,column=0,sticky="w",padx=16,pady=(0,10))

        ctk.CTkLabel(card,text="REPOSITÓRIO DO GITHUB",text_color=LABEL,font=("Segoe UI",13,"bold")).grid(row=2,column=0,sticky="w",padx=16,pady=(4,5))
        self.update_repo_var=tk.StringVar(value=load_repository())
        ctk.CTkEntry(card,textvariable=self.update_repo_var,height=42,font=FONT_INPUT,fg_color="#eef1f3",border_color="#aeb6bd").grid(row=3,column=0,sticky="ew",padx=16)
        ctk.CTkLabel(card,text="Configurado: JoaoTrindade-redes/RhFacil.API • também aceita URL HTTPS ou SSH do GitHub",text_color=MUTED,font=FONT_SMALL).grid(row=4,column=0,sticky="w",padx=16,pady=(4,4))

        actions=ctk.CTkFrame(card,fg_color="transparent")
        actions.grid(row=5,column=0,sticky="w",padx=16,pady=(8,8))
        ctk.CTkButton(actions,text="SALVAR REPOSITÓRIO",command=self.save_update_repository,width=170,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,font=("Segoe UI",11,"bold")).pack(side="left")
        ctk.CTkButton(actions,text="VERIFICAR AGORA",command=self.check_updates_now,width=145,height=38,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,font=("Segoe UI",11,"bold")).pack(side="left",padx=(8,0))

        configured=repository_configured()
        self.update_repo_status=ctk.CTkLabel(card,text=(f"Repositório configurado: {load_repository()}" if configured else "Repositório ainda não configurado."),text_color=(GREEN if configured else AMBER),font=FONT_BODY)
        self.update_repo_status.grid(row=6,column=0,sticky="w",padx=16,pady=(0,12))

        info=ctk.CTkFrame(parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10)
        info.grid(row=2,column=0,sticky="ew",padx=16,pady=(10,24))
        info.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(info,text="COMO FUNCIONA",text_color=TEXT,font=("Segoe UI",17,"bold")).grid(row=0,column=0,sticky="w",padx=16,pady=(14,6))
        ctk.CTkLabel(info,text=(
            "Ao abrir o RH Fácil, o sistema consulta a última Release publicada no GitHub em segundo plano. "
            "Se houver uma versão mais nova, você decide se deseja atualizar. O banco de dados, fichas PDF, currículos e backups ficam fora do pacote do programa e não são substituídos pela atualização."
        ),text_color=MUTED,font=FONT_BODY,wraplength=900,justify="left").grid(row=1,column=0,sticky="w",padx=16,pady=(0,14))

    # -------- settings --------
    def show_settings(self):
        self.set_active_nav("settings")
        self.clear_content()
        self.page_header(
            "CONFIGURAÇÕES",
            "Gerencie empresas, horários e o local onde os dados do RH Fácil são armazenados."
        )

        tabs=ctk.CTkTabview(
            self.content,fg_color=CARD,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color="#dfe3e6",
            segmented_button_unselected_hover_color="#d1d6da",
            text_color=TEXT
        )
        tabs.grid(row=1,column=0,sticky="nsew",padx=32,pady=(0,28))

        try:
            tabs._segmented_button.configure(font=("Segoe UI",16,"bold"),height=46)
        except Exception:
            pass

        e=tabs.add("EMPRESAS")
        h=tabs.add("HORÁRIOS")
        a=tabs.add("ARMAZENAMENTO")
        u=tabs.add("ATUALIZAÇÕES")

        e_scroll=ctk.CTkScrollableFrame(
            e,fg_color="transparent",
            scrollbar_button_color="#9da5ab",
            scrollbar_button_hover_color="#7f888f"
        )
        h_scroll=ctk.CTkScrollableFrame(
            h,fg_color="transparent",
            scrollbar_button_color="#9da5ab",
            scrollbar_button_hover_color="#7f888f"
        )
        a_scroll=ctk.CTkScrollableFrame(
            a,fg_color="transparent",
            scrollbar_button_color="#9da5ab",
            scrollbar_button_hover_color="#7f888f"
        )
        u_scroll=ctk.CTkScrollableFrame(
            u,fg_color="transparent",
            scrollbar_button_color="#9da5ab",
            scrollbar_button_hover_color="#7f888f"
        )

        for frame in (e_scroll,h_scroll,a_scroll,u_scroll):
            frame.pack(fill="both",expand=True,padx=2,pady=2)
            frame.grid_columnconfigure(0,weight=1)

        self.build_company_settings(e_scroll)
        self.build_schedule_settings(h_scroll)
        self.build_storage_settings(a_scroll)
        self.build_update_settings(u_scroll)

    def build_company_settings(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        self.company_edit_id=None

        count=len(rows("SELECT id FROM empresas WHERE ativa=1"))
        head=ctk.CTkFrame(parent,fg_color="transparent")
        head.grid(row=0,column=0,sticky="ew",padx=16,pady=(14,4))
        ctk.CTkLabel(
            head,text="EMPRESAS",text_color=TEXT,font=("Segoe UI",22,"bold")
        ).pack(side="left")
        self.company_count_label=ctk.CTkLabel(
            head,text=f"{count} cadastradas",text_color=MUTED,font=("Segoe UI",13,"bold")
        )
        self.company_count_label.pack(side="right")
        ctk.CTkLabel(
            parent,text="Role para baixo para ver e editar as empresas cadastradas.",
            text_color=MUTED,font=("Segoe UI",11)
        ).grid(row=0,column=0,sticky="e",padx=(0,150),pady=(20,0))

        form=ctk.CTkFrame(parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10)
        form.grid(row=1,column=0,sticky="ew",padx=16,pady=10)
        form.grid_columnconfigure((0,1,2),weight=1)

        self.company_form_title=ctk.CTkLabel(
            form,text="ADICIONAR EMPRESA",text_color=TEXT,font=("Segoe UI",17,"bold")
        )
        self.company_form_title.grid(row=0,column=0,columnspan=3,sticky="w",padx=16,pady=(14,8))

        self.cfg_company={}
        fields=[
            ("razao","RAZÃO SOCIAL"),("fantasia","NOME FANTASIA"),("cnpj","CNPJ"),
            ("endereco","ENDEREÇO"),("complemento","COMPLEMENTO"),("bairro","BAIRRO"),
            ("cep","CEP"),("cidade","CIDADE"),("uf","UF"),("telefone","TELEFONE")
        ]
        for i,(key,label) in enumerate(fields):
            row=1+i//3
            col=i%3
            box=ctk.CTkFrame(form,fg_color="transparent")
            box.grid(row=row,column=col,sticky="ew",padx=12,pady=7)
            ctk.CTkLabel(
                box,text=label,text_color=LABEL,font=("Segoe UI",13,"bold")
            ).pack(anchor="w",pady=(0,5))
            v=tk.StringVar()
            self.cfg_company[key]=v
            ctk.CTkEntry(
                box,textvariable=v,height=42,font=FONT_INPUT,
                fg_color="#eef1f3",border_color="#aeb6bd"
            ).pack(fill="x")

        actions=ctk.CTkFrame(form,fg_color="transparent")
        actions.grid(row=5,column=0,columnspan=3,sticky="e",padx=12,pady=(8,14))
        ctk.CTkButton(
            actions,text="LIMPAR",command=self.clear_company_form,
            width=105,height=38,fg_color="#d9dde0",hover_color="#cbd1d5",
            text_color=TEXT,font=("Segoe UI",12,"bold")
        ).pack(side="left",padx=(0,8))
        self.company_save_btn=ctk.CTkButton(
            actions,text="SALVAR EMPRESA",command=self.save_company,
            width=155,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,
            font=("Segoe UI",12,"bold")
        )
        self.company_save_btn.pack(side="left")

        ctk.CTkLabel(
            parent,text="EMPRESAS CADASTRADAS",text_color=TEXT,font=("Segoe UI",17,"bold")
        ).grid(row=2,column=0,sticky="w",padx=16,pady=(12,4))

        self.company_list=ctk.CTkFrame(
            parent,fg_color="#eef1f3",border_color=BORDER,border_width=1,
            corner_radius=10
        )
        self.company_list.grid(row=3,column=0,sticky="ew",padx=16,pady=(4,24))
        self.refresh_company_list()

    def clear_company_form(self):
        self.company_edit_id=None
        if hasattr(self,"company_form_title"):
            self.company_form_title.configure(text="ADICIONAR EMPRESA")
            self.company_save_btn.configure(text="SALVAR EMPRESA")
        for v in getattr(self,"cfg_company",{}).values():
            v.set("")

    def save_company(self):
        d={k:v.get().strip() for k,v in self.cfg_company.items()}
        if not d["razao"]:
            messagebox.showwarning("Empresa","Informe a Razão Social.")
            return
        if d["cnpj"] and not cnpj_valid(d["cnpj"]):
            messagebox.showwarning("Empresa","O CNPJ informado é inválido.")
            return

        if self.company_edit_id:
            execute(
                """UPDATE empresas SET
                       razao_social=?,nome_fantasia=?,cnpj=?,endereco=?,complemento=?,
                       bairro=?,cep=?,cidade=?,uf=?,telefone=?
                   WHERE id=?""",
                (
                    d["razao"],d["fantasia"],d["cnpj"],d["endereco"],d["complemento"],
                    d["bairro"],d["cep"],d["cidade"],d["uf"],d["telefone"],
                    self.company_edit_id
                )
            )
        else:
            execute(
                """INSERT INTO empresas(
                       razao_social,nome_fantasia,cnpj,endereco,complemento,bairro,cep,
                       cidade,uf,telefone,ativa
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    d["razao"],d["fantasia"],d["cnpj"],d["endereco"],d["complemento"],
                    d["bairro"],d["cep"],d["cidade"],d["uf"],d["telefone"]
                )
            )

        self.clear_company_form()
        self.refresh_company_list()
        self.set_status("✓ Empresa salva com sucesso.","ok")

    def edit_company(self,company_id):
        result=rows("SELECT * FROM empresas WHERE id=?",(company_id,))
        if not result:
            return
        x=result[0]
        self.company_edit_id=company_id
        self.company_form_title.configure(text="EDITAR EMPRESA")
        self.company_save_btn.configure(text="SALVAR ALTERAÇÕES")
        mapping={
            "razao":"razao_social","fantasia":"nome_fantasia","cnpj":"cnpj",
            "endereco":"endereco","complemento":"complemento","bairro":"bairro",
            "cep":"cep","cidade":"cidade","uf":"uf","telefone":"telefone"
        }
        for k,col in mapping.items():
            self.cfg_company[k].set(x[col] or "")

    def remove_company(self,company_id):
        result=rows("SELECT nome_fantasia,razao_social FROM empresas WHERE id=?",(company_id,))
        if not result:
            return
        label=(result[0]["nome_fantasia"] or "").strip() or result[0]["razao_social"]
        used=self._record_used("empresa",company_id)
        if used:
            msg=f'A empresa "{label}" já foi usada em admissões. Ela será DESATIVADA para preservar o histórico. Continuar?'
        else:
            msg=f'Remover definitivamente a empresa "{label}"?'
        if not messagebox.askyesno("Remover empresa",msg):
            return
        if used:
            execute("UPDATE empresas SET ativa=0 WHERE id=?",(company_id,))
        else:
            execute("DELETE FROM empresas WHERE id=?",(company_id,))
        self.clear_company_form()
        self.refresh_company_list()

    def refresh_company_list(self):
        if not hasattr(self,"company_list"):
            return
        for w in self.company_list.winfo_children():
            w.destroy()
        data=rows("SELECT * FROM empresas WHERE ativa=1 ORDER BY nome_fantasia,razao_social")
        self.company_count_label.configure(text=f"{len(data)} cadastradas")
        for x in data:
            card=ctk.CTkFrame(
                self.company_list,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8
            )
            card.pack(fill="x",padx=5,pady=5)
            card.grid_columnconfigure(0,weight=1)

            label=(x["nome_fantasia"] or "").strip() or x["razao_social"]
            detail=" · ".join(v for v in [
                x["cnpj"] or "",
                f'{x["cidade"]}/{x["uf"]}' if x["cidade"] or x["uf"] else "",
                x["telefone"] or ""
            ] if v)
            ctk.CTkLabel(
                card,text=label.upper(),text_color=TEXT,font=("Segoe UI",14,"bold")
            ).grid(row=0,column=0,sticky="w",padx=12,pady=(10,1))
            ctk.CTkLabel(
                card,text=detail,text_color=MUTED,font=FONT_SMALL
            ).grid(row=1,column=0,sticky="w",padx=12,pady=(0,10))

            actions=ctk.CTkFrame(card,fg_color="transparent")
            actions.grid(row=0,column=1,rowspan=2,padx=10,pady=8)
            ctk.CTkButton(
                actions,text="EDITAR",width=80,height=32,
                fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,
                command=lambda cid=x["id"]:self.edit_company(cid)
            ).pack(side="left",padx=3)
            ctk.CTkButton(
                actions,text="REMOVER",width=85,height=32,
                fg_color="#eadada",hover_color="#dfcaca",text_color=RED,
                command=lambda cid=x["id"]:self.remove_company(cid)
            ).pack(side="left",padx=3)

    # ====================== HORÁRIOS ======================
    def build_schedule_settings(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        self.schedule_edit_id=None

        data=rows("SELECT id FROM horarios WHERE ativo=1")
        head=ctk.CTkFrame(parent,fg_color="transparent")
        head.grid(row=0,column=0,sticky="ew",padx=16,pady=(14,4))
        ctk.CTkLabel(
            head,text="HORÁRIOS",text_color=TEXT,font=("Segoe UI",22,"bold")
        ).pack(side="left")
        self.schedule_count_label=ctk.CTkLabel(
            head,text=f"{len(data)} cadastrados",text_color=MUTED,font=("Segoe UI",13,"bold")
        )
        self.schedule_count_label.pack(side="right")
        ctk.CTkLabel(
            parent,text="Role para baixo para visualizar, editar, duplicar ou remover horários.",
            text_color=MUTED,font=("Segoe UI",11)
        ).grid(row=0,column=0,sticky="e",padx=(0,155),pady=(20,0))

        form=ctk.CTkFrame(parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10)
        form.grid(row=1,column=0,sticky="ew",padx=16,pady=10)
        form.grid_columnconfigure((0,1,2,3),weight=1)

        self.schedule_form_title=ctk.CTkLabel(
            form,text="ADICIONAR HORÁRIO",text_color=TEXT,font=("Segoe UI",17,"bold")
        )
        self.schedule_form_title.grid(row=0,column=0,columnspan=4,sticky="w",padx=16,pady=(14,8))

        self.schedule_vars={
            "nome":tk.StringVar(),
            "entrada":tk.StringVar(value="06:45"),
            "saida_intervalo":tk.StringVar(value="11:00"),
            "retorno":tk.StringVar(value="13:00"),
            "saida":tk.StringVar(value="17:30"),
            "segunda_saida":tk.StringVar(value="17:45"),
            "sabado_entrada":tk.StringVar(),
            "sabado_saida":tk.StringVar(),
        }
        self.schedule_days={k:tk.BooleanVar(value=k in ("SEG","TER","QUA","QUI","SEX")) for k in ("SEG","TER","QUA","QUI","SEX","SAB","DOM")}
        self.schedule_default=tk.BooleanVar(value=False)

        # Nome
        b=ctk.CTkFrame(form,fg_color="transparent")
        b.grid(row=1,column=0,columnspan=2,sticky="ew",padx=12,pady=7)
        ctk.CTkLabel(b,text="NOME DO HORÁRIO",text_color=LABEL,font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,5))
        ctk.CTkEntry(
            b,textvariable=self.schedule_vars["nome"],height=42,font=FONT_INPUT,
            fg_color="#eef1f3",border_color="#aeb6bd"
        ).pack(fill="x")

        # Padrão
        p=ctk.CTkFrame(form,fg_color="transparent")
        p.grid(row=1,column=2,columnspan=2,sticky="ew",padx=12,pady=7)
        ctk.CTkLabel(p,text="DEFINIÇÃO",text_color=LABEL,font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,5))
        ctk.CTkCheckBox(
            p,text="Usar como horário padrão nas novas admissões",
            variable=self.schedule_default,onvalue=True,offvalue=False,
            font=FONT_BODY,fg_color=ACCENT,hover_color=ACCENT_HOVER
        ).pack(anchor="w",pady=8)

        # Dias
        daybox=ctk.CTkFrame(form,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8)
        daybox.grid(row=2,column=0,columnspan=4,sticky="ew",padx=12,pady=8)
        ctk.CTkLabel(
            daybox,text="DIAS APLICÁVEIS",text_color=LABEL,font=("Segoe UI",13,"bold")
        ).pack(anchor="w",padx=12,pady=(10,6))
        line=ctk.CTkFrame(daybox,fg_color="transparent")
        line.pack(fill="x",padx=12,pady=(0,10))
        for code,label in [
            ("SEG","SEG"),("TER","TER"),("QUA","QUA"),("QUI","QUI"),
            ("SEX","SEX"),("SAB","SÁB"),("DOM","DOM")
        ]:
            ctk.CTkCheckBox(
                line,text=label,variable=self.schedule_days[code],
                onvalue=True,offvalue=False,font=("Segoe UI",12,"bold"),
                fg_color=ACCENT,hover_color=ACCENT_HOVER,
                command=self.update_schedule_preview
            ).pack(side="left",padx=(0,15))

        def time_field(row,col,key,label):
            box=ctk.CTkFrame(form,fg_color="transparent")
            box.grid(row=row,column=col,sticky="ew",padx=12,pady=7)
            ctk.CTkLabel(
                box,text=label,text_color=LABEL,font=("Segoe UI",13,"bold")
            ).pack(anchor="w",pady=(0,5))
            e=ctk.CTkEntry(
                box,textvariable=self.schedule_vars[key],height=42,font=FONT_INPUT,
                fg_color="#eef1f3",border_color="#aeb6bd",placeholder_text="HH:MM"
            )
            e.pack(fill="x")
            self.schedule_vars[key].trace_add("write",self.update_schedule_preview)

        time_field(3,0,"entrada","ENTRADA")
        time_field(3,1,"saida_intervalo","SAÍDA PARA INTERVALO")
        time_field(3,2,"retorno","RETORNO")
        time_field(3,3,"saida","SAÍDA")

        monday=ctk.CTkFrame(form,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8)
        monday.grid(row=4,column=0,columnspan=4,sticky="ew",padx=12,pady=8)
        monday.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(
            monday,text="SEGUNDA-FEIRA DIFERENTE (OPCIONAL)",text_color=LABEL,
            font=("Segoe UI",13,"bold")
        ).grid(row=0,column=0,sticky="w",padx=12,pady=(10,6))

        mb=ctk.CTkFrame(monday,fg_color="transparent")
        mb.grid(row=1,column=0,sticky="ew",padx=12,pady=(0,10))
        ctk.CTkLabel(
            mb,text="SAÍDA NA SEGUNDA",text_color=LABEL,font=("Segoe UI",12,"bold")
        ).pack(anchor="w",pady=(0,4))
        ctk.CTkEntry(
            mb,textvariable=self.schedule_vars["segunda_saida"],height=40,font=FONT_INPUT,
            fg_color="#eef1f3",border_color="#aeb6bd",placeholder_text="HH:MM"
        ).pack(fill="x")
        self.schedule_vars["segunda_saida"].trace_add("write",self.update_schedule_preview)

        sat=ctk.CTkFrame(form,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8)
        sat.grid(row=5,column=0,columnspan=4,sticky="ew",padx=12,pady=8)
        sat.grid_columnconfigure((0,1),weight=1)
        ctk.CTkLabel(
            sat,text="SÁBADO DIFERENTE (OPCIONAL)",text_color=LABEL,font=("Segoe UI",13,"bold")
        ).grid(row=0,column=0,columnspan=2,sticky="w",padx=12,pady=(10,6))
        for col,(key,label) in enumerate([("sabado_entrada","ENTRADA"),("sabado_saida","SAÍDA")]):
            box=ctk.CTkFrame(sat,fg_color="transparent")
            box.grid(row=1,column=col,sticky="ew",padx=12,pady=(0,10))
            ctk.CTkLabel(box,text=label,text_color=LABEL,font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,4))
            ctk.CTkEntry(
                box,textvariable=self.schedule_vars[key],height=40,font=FONT_INPUT,
                fg_color="#eef1f3",border_color="#aeb6bd",placeholder_text="HH:MM"
            ).pack(fill="x")
            self.schedule_vars[key].trace_add("write",self.update_schedule_preview)

        preview=ctk.CTkFrame(form,fg_color="#e8ecef",border_color=BORDER,border_width=1,corner_radius=8)
        preview.grid(row=6,column=0,columnspan=4,sticky="ew",padx=12,pady=8)
        self.schedule_preview_label=ctk.CTkLabel(
            preview,text="",text_color=TEXT,font=("Segoe UI",13,"bold"),wraplength=820,justify="left"
        )
        self.schedule_preview_label.pack(anchor="w",padx=12,pady=(10,4))
        metrics=ctk.CTkFrame(preview,fg_color="transparent")
        metrics.pack(fill="x",padx=12,pady=(0,10))
        self.schedule_daily_label=ctk.CTkLabel(metrics,text="Carga diária: —",text_color=MUTED,font=FONT_BODY)
        self.schedule_daily_label.pack(side="left")
        self.schedule_weekly_label=ctk.CTkLabel(metrics,text="Carga semanal: —",text_color=MUTED,font=FONT_BODY)
        self.schedule_weekly_label.pack(side="left",padx=(24,0))

        actions=ctk.CTkFrame(form,fg_color="transparent")
        actions.grid(row=7,column=0,columnspan=4,sticky="e",padx=12,pady=(8,14))
        ctk.CTkButton(
            actions,text="LIMPAR",command=self.clear_schedule_form,
            width=105,height=38,fg_color="#d9dde0",hover_color="#cbd1d5",
            text_color=TEXT,font=("Segoe UI",12,"bold")
        ).pack(side="left",padx=(0,8))
        self.schedule_save_btn=ctk.CTkButton(
            actions,text="SALVAR HORÁRIO",command=self.save_schedule,
            width=155,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,
            font=("Segoe UI",12,"bold")
        )
        self.schedule_save_btn.pack(side="left")

        ctk.CTkLabel(
            parent,text="HORÁRIOS CADASTRADOS",text_color=TEXT,font=("Segoe UI",17,"bold")
        ).grid(row=2,column=0,sticky="w",padx=16,pady=(12,4))

        self.schedule_list=ctk.CTkFrame(
            parent,fg_color="#eef1f3",border_color=BORDER,border_width=1,
            corner_radius=10
        )
        self.schedule_list.grid(row=3,column=0,sticky="ew",padx=16,pady=(4,24))

        self.update_schedule_preview()
        self.refresh_schedule_list()

    def clear_schedule_form(self):
        self.schedule_edit_id=None
        self.schedule_form_title.configure(text="ADICIONAR HORÁRIO")
        self.schedule_save_btn.configure(text="SALVAR HORÁRIO")
        defaults={
            "nome":"","entrada":"06:45","saida_intervalo":"11:00","retorno":"13:00",
            "saida":"17:30","segunda_saida":"17:45","sabado_entrada":"","sabado_saida":""
        }
        for k,v in defaults.items():
            self.schedule_vars[k].set(v)
        for code,var in self.schedule_days.items():
            var.set(code in ("SEG","TER","QUA","QUI","SEX"))
        self.schedule_default.set(False)
        self.update_schedule_preview()

    def _valid_time_or_blank(self,value):
        return not value.strip() or self._time_minutes(value) is not None

    def save_schedule(self):
        name=self.schedule_vars["nome"].get().strip()
        if not name:
            messagebox.showwarning("Horário","Informe o nome do horário.")
            return
        days=[code for code,var in self.schedule_days.items() if var.get()]
        if not days:
            messagebox.showwarning("Horário","Selecione pelo menos um dia aplicável.")
            return

        values=[self.schedule_vars[k].get().strip() for k in (
            "entrada","saida_intervalo","retorno","saida","segunda_saida","sabado_entrada","sabado_saida"
        )]
        if any(not self._valid_time_or_blank(v) for v in values):
            messagebox.showwarning("Horário","Use o formato HH:MM nos horários.")
            return

        if self._duration_minutes(
            self.schedule_vars["entrada"].get(),
            self.schedule_vars["saida_intervalo"].get(),
            self.schedule_vars["retorno"].get(),
            self.schedule_vars["saida"].get()
        ) is None:
            messagebox.showwarning(
                "Horário",
                "Confira Entrada, Saída para intervalo, Retorno e Saída."
            )
            return

        preview=self._schedule_preview_from_values()
        is_default=1 if self.schedule_default.get() else 0
        if is_default:
            execute("UPDATE horarios SET padrao=0")

        params=(
            name,preview,json.dumps(days,ensure_ascii=False),
            self.schedule_vars["entrada"].get().strip(),
            self.schedule_vars["saida_intervalo"].get().strip(),
            self.schedule_vars["retorno"].get().strip(),
            self.schedule_vars["saida"].get().strip(),
            self.schedule_vars["segunda_saida"].get().strip(),
            self.schedule_vars["sabado_entrada"].get().strip(),
            self.schedule_vars["sabado_saida"].get().strip(),
            is_default
        )

        if self.schedule_edit_id:
            execute(
                """UPDATE horarios SET
                       nome=?,horario=?,dias_json=?,entrada=?,saida_intervalo=?,retorno=?,saida=?,
                       segunda_saida=?,sabado_entrada=?,sabado_saida=?,padrao=?
                   WHERE id=?""",
                params+(self.schedule_edit_id,)
            )
        else:
            execute(
                """INSERT INTO horarios(
                       nome,horario,ativo,dias_json,entrada,saida_intervalo,retorno,saida,
                       segunda_saida,sabado_entrada,sabado_saida,padrao
                   ) VALUES(?,?,1,?,?,?,?,?,?,?,?,?)""",
                params
            )

        self.clear_schedule_form()
        self.refresh_schedule_list()
        self.set_status("✓ Horário salvo com sucesso.","ok")

    def edit_schedule(self,schedule_id):
        result=rows("SELECT * FROM horarios WHERE id=?",(schedule_id,))
        if not result:
            return
        x=result[0]
        self.schedule_edit_id=schedule_id
        self.schedule_form_title.configure(text="EDITAR HORÁRIO")
        self.schedule_save_btn.configure(text="SALVAR ALTERAÇÕES")
        self.schedule_vars["nome"].set(x["nome"] or "")
        for key in ("entrada","saida_intervalo","retorno","saida","segunda_saida","sabado_entrada","sabado_saida"):
            self.schedule_vars[key].set(x[key] or "")
        try:
            days=json.loads(x["dias_json"] or "[]")
        except Exception:
            days=[]
        for code,var in self.schedule_days.items():
            var.set(code in days)
        self.schedule_default.set(bool(x["padrao"]))
        self.update_schedule_preview()

    def duplicate_schedule(self,schedule_id):
        result=rows("SELECT * FROM horarios WHERE id=?",(schedule_id,))
        if not result:
            return
        x=result[0]
        execute(
            """INSERT INTO horarios(
                   nome,horario,ativo,dias_json,entrada,saida_intervalo,retorno,saida,
                   segunda_saida,sabado_entrada,sabado_saida,padrao
               ) VALUES(?,?,1,?,?,?,?,?,?,?,?,0)""",
            (
                f"Cópia - {x['nome']}",x["horario"],x["dias_json"],
                x["entrada"],x["saida_intervalo"],x["retorno"],x["saida"],
                x["segunda_saida"],x["sabado_entrada"],x["sabado_saida"]
            )
        )
        self.refresh_schedule_list()

    def remove_schedule(self,schedule_id):
        result=rows("SELECT nome,horario FROM horarios WHERE id=?",(schedule_id,))
        if not result:
            return
        x=result[0]
        used=self._record_used("horario",schedule_id,x["horario"] or "")
        if used:
            msg=f'O horário "{x["nome"]}" já foi utilizado. Ele será DESATIVADO para preservar o histórico. Continuar?'
        else:
            msg=f'Remover definitivamente o horário "{x["nome"]}"?'
        if not messagebox.askyesno("Remover horário",msg):
            return
        if used:
            execute("UPDATE horarios SET ativo=0,padrao=0 WHERE id=?",(schedule_id,))
        else:
            execute("DELETE FROM horarios WHERE id=?",(schedule_id,))
        self.clear_schedule_form()
        self.refresh_schedule_list()

    def refresh_schedule_list(self):
        if not hasattr(self,"schedule_list"):
            return
        for w in self.schedule_list.winfo_children():
            w.destroy()
        data=rows("SELECT * FROM horarios WHERE ativo=1 ORDER BY padrao DESC,nome")
        self.schedule_count_label.configure(text=f"{len(data)} cadastrados")

        for x in data:
            card=ctk.CTkFrame(
                self.schedule_list,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8
            )
            card.pack(fill="x",padx=5,pady=5)
            card.grid_columnconfigure(0,weight=1)

            title=x["nome"].upper()
            if x["padrao"]:
                title += "  ·  PADRÃO"
            ctk.CTkLabel(
                card,text=title,text_color=GREEN if x["padrao"] else TEXT,
                font=("Segoe UI",14,"bold")
            ).grid(row=0,column=0,sticky="w",padx=12,pady=(9,1))
            ctk.CTkLabel(
                card,text=x["horario"] or "",text_color=MUTED,font=FONT_SMALL,
                wraplength=650,justify="left"
            ).grid(row=1,column=0,sticky="w",padx=12,pady=(0,9))

            actions=ctk.CTkFrame(card,fg_color="transparent")
            actions.grid(row=0,column=1,rowspan=2,padx=8,pady=7)
            for text,cmd,width in [
                ("EDITAR",lambda sid=x["id"]:self.edit_schedule(sid),72),
                ("DUPLICAR",lambda sid=x["id"]:self.duplicate_schedule(sid),86),
                ("REMOVER",lambda sid=x["id"]:self.remove_schedule(sid),82),
            ]:
                ctk.CTkButton(
                    actions,text=text,width=width,height=31,
                    fg_color="#d9dde0" if text!="REMOVER" else "#eadada",
                    hover_color="#cbd1d5" if text!="REMOVER" else "#dfcaca",
                    text_color=TEXT if text!="REMOVER" else RED,
                    command=cmd,font=("Segoe UI",10,"bold")
                ).pack(side="left",padx=2)

    # ====================== CARGOS ======================
    def _save_storage_setting(self,path):
        APP_CONFIG_DIR.mkdir(parents=True,exist_ok=True)
        STORAGE_SETTINGS_FILE.write_text(
            json.dumps({"data_dir":str(path)},ensure_ascii=False,indent=2),
            encoding="utf-8"
        )

    def _copy_current_data_to(self,new_dir):
        new_dir=Path(new_dir)
        new_db=new_dir/"Banco de Dados"/"rh_facil.db"
        new_pdf=new_dir/"Fichas PDF"
        new_curr=new_dir/"Currículos"
        new_backups=new_dir/"Backups"

        new_db.parent.mkdir(parents=True,exist_ok=True)
        new_pdf.mkdir(parents=True,exist_ok=True)
        new_curr.mkdir(parents=True,exist_ok=True)
        new_backups.mkdir(parents=True,exist_ok=True)

        if new_db.exists() and DB_PATH.exists() and new_db.resolve()!=DB_PATH.resolve():
            raise FileExistsError(
                "A pasta escolhida já possui um banco do RH Fácil. "
                "Escolha uma pasta vazia ou a pasta que já está configurada."
            )

        if DB_PATH.exists() and new_db.resolve()!=DB_PATH.resolve():
            shutil.copy2(DB_PATH,new_db)
        if PDF_DIR.exists() and new_pdf.resolve()!=PDF_DIR.resolve():
            shutil.copytree(PDF_DIR,new_pdf,dirs_exist_ok=True)
        if CURRICULOS_DIR.exists() and new_curr.resolve()!=CURRICULOS_DIR.resolve():
            shutil.copytree(CURRICULOS_DIR,new_curr,dirs_exist_ok=True)
        if DRAFT_PATH.exists():
            shutil.copy2(DRAFT_PATH,new_dir/"rascunho_admissao.json")

    def change_storage_folder(self):
        selected=filedialog.askdirectory(
            title="Escolha a pasta para os dados do RH Fácil",
            initialdir=str(DATA_DIR)
        )
        if not selected:
            return

        new_dir=Path(selected)
        try:
            if new_dir.resolve()==DATA_DIR.resolve():
                messagebox.showinfo("Armazenamento","Essa pasta já está em uso.")
                return
        except Exception:
            pass

        copy_existing=messagebox.askyesno(
            "Alterar armazenamento",
            "Deseja copiar os dados existentes para a nova pasta?\n\n"
            "Recomendado: SIM, para manter admissões e PDFs já salvos."
        )

        try:
            new_dir.mkdir(parents=True,exist_ok=True)
            test_file=new_dir/".rh_facil_write_test"
            test_file.write_text("ok",encoding="utf-8")
            test_file.unlink()

            if copy_existing:
                self._copy_current_data_to(new_dir)

            self._save_storage_setting(new_dir)
            _set_data_paths(new_dir)
            ensure_storage()
            init_db()

            self.refresh_storage_panel()
            messagebox.showinfo(
                "Armazenamento alterado",
                "O RH Fácil passou a usar a nova pasta.\n\n"
                f"{DATA_DIR}"
            )
        except Exception as exc:
            messagebox.showerror(
                "Alterar armazenamento",
                f"Não foi possível usar a pasta escolhida.\n\n{exc}"
            )

    def create_backup_now(self,show_message=True):
        ensure_storage()
        stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        path=BACKUP_DIR/f"RH_Facil_backup_{stamp}.zip"
        try:
            checkpoint_db()
            with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
                if DB_PATH.exists():
                    z.write(DB_PATH,arcname="Banco de Dados/rh_facil.db")
                for folder,label in ((PDF_DIR,"Fichas PDF"),(CURRICULOS_DIR,"Currículos")):
                    if folder.exists():
                        for p in folder.rglob("*"):
                            if p.is_file():
                                z.write(p,arcname=str(Path(label)/p.relative_to(folder)))
            self.refresh_storage_panel()
            self.set_status("✓ Backup concluído.","ok")
            if show_message:
                messagebox.showinfo("Backup concluído",f"Backup criado em:\n{path}")
            return path
        except Exception as exc:
            self.set_status("Não foi possível criar o backup.","error")
            if show_message:
                messagebox.showerror("Backup",f"Não foi possível criar o backup.\n\n{exc}")
            return None

    def restore_backup(self):
        selected=filedialog.askopenfilename(
            title="Escolha um backup do RH Fácil",
            initialdir=str(BACKUP_DIR),
            filetypes=[("Backup RH Fácil","*.zip"),("Todos os arquivos","*.*")]
        )
        if not selected:
            return
        backup_path=Path(selected)
        if not messagebox.askyesno(
            "Restaurar backup",
            f"Restaurar o backup abaixo?\n\n{backup_path.name}\n\n"
            "O estado atual será salvo em um novo backup antes da restauração."
        ):
            return
        current_backup=self.create_backup_now(show_message=False)
        if not current_backup:
            messagebox.showerror("Restaurar backup","Não foi possível criar o backup de segurança do estado atual. A restauração foi cancelada.")
            return
        try:
            with zipfile.ZipFile(backup_path,"r") as z:
                names=set(z.namelist())
                if "Banco de Dados/rh_facil.db" not in names:
                    raise ValueError("O arquivo escolhido não contém um banco de dados válido do RH Fácil.")
                with tempfile.TemporaryDirectory(prefix="rhfacil_restore_") as tmp:
                    tmp=Path(tmp)
                    z.extractall(tmp)
                    source_db=tmp/"Banco de Dados"/"rh_facil.db"
                    checkpoint_db()
                    for sidecar in (Path(str(DB_PATH)+"-wal"),Path(str(DB_PATH)+"-shm")):
                        try: sidecar.unlink(missing_ok=True)
                        except Exception: pass
                    shutil.copy2(source_db,DB_PATH)
                    source_pdf=tmp/"Fichas PDF"
                    source_curr=tmp/"Currículos"
                    if PDF_DIR.exists():
                        shutil.rmtree(PDF_DIR)
                    if CURRICULOS_DIR.exists():
                        shutil.rmtree(CURRICULOS_DIR)
                    PDF_DIR.mkdir(parents=True,exist_ok=True)
                    CURRICULOS_DIR.mkdir(parents=True,exist_ok=True)
                    if source_pdf.exists():
                        shutil.copytree(source_pdf,PDF_DIR,dirs_exist_ok=True)
                    if source_curr.exists():
                        shutil.copytree(source_curr,CURRICULOS_DIR,dirs_exist_ok=True)
            init_db()
            self.refresh_storage_panel()
            self.set_status("✓ Backup restaurado. O RH Fácil foi atualizado com os dados do backup.","ok",9000)
            messagebox.showinfo("Backup restaurado",f"Restauração concluída.\n\nBackup de segurança atual: {current_backup.name}")
        except Exception as exc:
            self.set_status("Falha ao restaurar o backup.","error",0)
            messagebox.showerror("Restaurar backup",f"Não foi possível restaurar o backup.\n\n{exc}\n\nO estado anterior foi preservado pelo backup de segurança.\n{current_backup}")

    def latest_backup_text(self):
        files=sorted(BACKUP_DIR.glob("RH_Facil_backup_*.zip"),key=lambda p:p.stat().st_mtime,reverse=True)
        if not files:
            return "Nenhum backup criado ainda."
        p=files[0]
        dt=datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        return f"Último backup: {dt} · {p.name}"

    def refresh_storage_panel(self):
        if hasattr(self,"storage_path_label"):
            self.storage_path_label.configure(text=str(DATA_DIR))
        if hasattr(self,"storage_backup_label"):
            self.storage_backup_label.configure(text=self.latest_backup_text())

    def build_storage_settings(self,parent):
        parent.grid_columnconfigure(0,weight=1)

        head=ctk.CTkFrame(parent,fg_color="transparent")
        head.grid(row=0,column=0,sticky="ew",padx=16,pady=(14,4))
        ctk.CTkLabel(
            head,text="ARMAZENAMENTO",text_color=TEXT,font=("Segoe UI",22,"bold")
        ).pack(side="left")

        card=ctk.CTkFrame(
            parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10
        )
        card.grid(row=1,column=0,sticky="ew",padx=16,pady=10)
        card.grid_columnconfigure(0,weight=1)

        ctk.CTkLabel(
            card,text="LOCAL DOS DADOS DO RH FÁCIL",
            text_color=LABEL,font=("Segoe UI",14,"bold")
        ).grid(row=0,column=0,sticky="w",padx=16,pady=(14,5))

        self.storage_path_label=ctk.CTkLabel(
            card,text=str(DATA_DIR),text_color=TEXT,font=("Segoe UI",13,"bold"),
            wraplength=850,justify="left"
        )
        self.storage_path_label.grid(row=1,column=0,sticky="w",padx=16,pady=(0,8))

        ctk.CTkLabel(
            card,
            text="Nesta pasta ficam o banco de admissões, as fichas PDF, futuros currículos e os backups.",
            text_color=MUTED,font=FONT_BODY,wraplength=850,justify="left"
        ).grid(row=2,column=0,sticky="w",padx=16,pady=(0,12))

        actions=ctk.CTkFrame(card,fg_color="transparent")
        actions.grid(row=3,column=0,sticky="w",padx=16,pady=(0,14))

        ctk.CTkButton(
            actions,text="ALTERAR PASTA",command=self.change_storage_folder,
            width=135,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,
            font=("Segoe UI",11,"bold")
        ).pack(side="left")

        ctk.CTkButton(
            actions,text="ABRIR PASTA",command=lambda:self.open_folder(DATA_DIR),
            width=120,height=38,fg_color="#d9dde0",hover_color="#cbd1d5",
            text_color=TEXT,font=("Segoe UI",11,"bold")
        ).pack(side="left",padx=(8,0))

        structure=ctk.CTkFrame(
            parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10
        )
        structure.grid(row=2,column=0,sticky="ew",padx=16,pady=10)

        ctk.CTkLabel(
            structure,text="ESTRUTURA DE PASTAS",text_color=TEXT,font=("Segoe UI",17,"bold")
        ).pack(anchor="w",padx=16,pady=(14,7))

        tree_text=(
            "RH Fácil\\\n"
            "├── Banco de Dados\\rh_facil.db\n"
            "├── Fichas PDF\\\n"
            "├── Currículos\\\n"
            "└── Backups\\"
        )
        ctk.CTkLabel(
            structure,text=tree_text,text_color=TEXT,
            font=("Consolas",12),justify="left"
        ).pack(anchor="w",padx=16,pady=(0,14))

        backup=ctk.CTkFrame(
            parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10
        )
        backup.grid(row=3,column=0,sticky="ew",padx=16,pady=(10,24))
        backup.grid_columnconfigure(0,weight=1)

        ctk.CTkLabel(
            backup,text="BACKUP",text_color=TEXT,font=("Segoe UI",17,"bold")
        ).grid(row=0,column=0,sticky="w",padx=16,pady=(14,4))

        self.storage_backup_label=ctk.CTkLabel(
            backup,text=self.latest_backup_text(),text_color=MUTED,font=FONT_BODY
        )
        self.storage_backup_label.grid(row=1,column=0,sticky="w",padx=16,pady=(0,10))

        actions=ctk.CTkFrame(backup,fg_color="transparent")
        actions.grid(row=2,column=0,sticky="w",padx=16,pady=(0,14))
        ctk.CTkButton(
            actions,text="FAZER BACKUP AGORA",command=self.create_backup_now,
            width=165,height=38,fg_color=ACCENT,hover_color=ACCENT_HOVER,
            font=("Segoe UI",11,"bold")
        ).pack(side="left")
        ctk.CTkButton(
            actions,text="RESTAURAR BACKUP",command=self.restore_backup,
            width=155,height=38,fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,
            font=("Segoe UI",11,"bold")
        ).pack(side="left",padx=(8,0))
    def build_role_settings(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        self.role_edit_id=None

        data=rows("SELECT id FROM cargos WHERE ativo=1")
        head=ctk.CTkFrame(parent,fg_color="transparent")
        head.grid(row=0,column=0,sticky="ew",padx=16,pady=(14,4))
        ctk.CTkLabel(
            head,text="CARGOS",text_color=TEXT,font=("Segoe UI",22,"bold")
        ).pack(side="left")
        self.role_count_label=ctk.CTkLabel(
            head,text=f"{len(data)} cadastrados",text_color=MUTED,font=("Segoe UI",13,"bold")
        )
        self.role_count_label.pack(side="right")
        ctk.CTkLabel(
            parent,text="Role para baixo para visualizar, editar ou remover cargos.",
            text_color=MUTED,font=("Segoe UI",11)
        ).grid(row=0,column=0,sticky="e",padx=(0,150),pady=(20,0))

        form=ctk.CTkFrame(parent,fg_color=SOFT,border_color=BORDER,border_width=1,corner_radius=10)
        form.grid(row=1,column=0,sticky="ew",padx=16,pady=10)
        form.grid_columnconfigure(0,weight=1)

        self.role_form_title=ctk.CTkLabel(
            form,text="ADICIONAR CARGO",text_color=TEXT,font=("Segoe UI",17,"bold")
        )
        self.role_form_title.grid(row=0,column=0,sticky="w",padx=16,pady=(14,7))

        self.role_var=tk.StringVar()
        ctk.CTkLabel(
            form,text="CARGO / FUNÇÃO",text_color=LABEL,font=("Segoe UI",13,"bold")
        ).grid(row=1,column=0,sticky="w",padx=16,pady=(0,5))
        ctk.CTkEntry(
            form,textvariable=self.role_var,height=42,font=FONT_INPUT,
            fg_color="#eef1f3",border_color="#aeb6bd"
        ).grid(row=2,column=0,sticky="ew",padx=16)

        actions=ctk.CTkFrame(form,fg_color="transparent")
        actions.grid(row=3,column=0,sticky="e",padx=16,pady=12)
        ctk.CTkButton(
            actions,text="LIMPAR",command=self.clear_role_form,
            width=100,height=36,fg_color="#d9dde0",hover_color="#cbd1d5",
            text_color=TEXT,font=("Segoe UI",11,"bold")
        ).pack(side="left",padx=(0,7))
        self.role_save_btn=ctk.CTkButton(
            actions,text="SALVAR CARGO",command=self.save_role,
            width=135,height=36,fg_color=ACCENT,hover_color=ACCENT_HOVER,
            font=("Segoe UI",11,"bold")
        )
        self.role_save_btn.pack(side="left")

        ctk.CTkLabel(
            parent,text="CARGOS CADASTRADOS",text_color=TEXT,font=("Segoe UI",17,"bold")
        ).grid(row=2,column=0,sticky="w",padx=16,pady=(12,4))

        self.role_list=ctk.CTkFrame(
            parent,fg_color="#eef1f3",border_color=BORDER,border_width=1,
            corner_radius=10
        )
        self.role_list.grid(row=3,column=0,sticky="ew",padx=16,pady=(4,24))
        self.refresh_role_list()

    def clear_role_form(self):
        self.role_edit_id=None
        self.role_var.set("")
        self.role_form_title.configure(text="ADICIONAR CARGO")
        self.role_save_btn.configure(text="SALVAR CARGO")

    def save_role(self):
        n=self.role_var.get().strip()
        if not n:
            messagebox.showwarning("Cargo","Informe o cargo / função.")
            return
        try:
            if self.role_edit_id:
                execute("UPDATE cargos SET nome=? WHERE id=?",(n,self.role_edit_id))
            else:
                execute("INSERT INTO cargos(nome,ativo) VALUES(?,1)",(n,))
        except sqlite3.IntegrityError:
            messagebox.showwarning("Cargo","Já existe um cargo com esse nome.")
            return
        self.clear_role_form()
        self.refresh_role_list()

    def edit_role(self,role_id):
        result=rows("SELECT * FROM cargos WHERE id=?",(role_id,))
        if not result:
            return
        self.role_edit_id=role_id
        self.role_var.set(result[0]["nome"] or "")
        self.role_form_title.configure(text="EDITAR CARGO")
        self.role_save_btn.configure(text="SALVAR ALTERAÇÕES")

    def remove_role(self,role_id):
        result=rows("SELECT nome FROM cargos WHERE id=?",(role_id,))
        if not result:
            return
        name=result[0]["nome"]
        used=self._record_used("cargo",role_id,name)
        if used:
            msg=f'O cargo "{name}" já foi utilizado. Ele será DESATIVADO para preservar o histórico. Continuar?'
        else:
            msg=f'Remover definitivamente o cargo "{name}"?'
        if not messagebox.askyesno("Remover cargo",msg):
            return
        if used:
            execute("UPDATE cargos SET ativo=0 WHERE id=?",(role_id,))
        else:
            execute("DELETE FROM cargos WHERE id=?",(role_id,))
        self.clear_role_form()
        self.refresh_role_list()

    def refresh_role_list(self):
        if not hasattr(self,"role_list"):
            return
        for w in self.role_list.winfo_children():
            w.destroy()
        data=rows("SELECT * FROM cargos WHERE ativo=1 ORDER BY nome")
        self.role_count_label.configure(text=f"{len(data)} cadastrados")
        for x in data:
            card=ctk.CTkFrame(
                self.role_list,fg_color=CARD,border_color=BORDER,border_width=1,corner_radius=8
            )
            card.pack(fill="x",padx=5,pady=5)
            card.grid_columnconfigure(0,weight=1)
            ctk.CTkLabel(
                card,text=(x["nome"] or "").upper(),text_color=TEXT,font=("Segoe UI",14,"bold")
            ).grid(row=0,column=0,sticky="w",padx=12,pady=10)

            actions=ctk.CTkFrame(card,fg_color="transparent")
            actions.grid(row=0,column=1,padx=8,pady=6)
            ctk.CTkButton(
                actions,text="EDITAR",width=78,height=31,
                fg_color="#d9dde0",hover_color="#cbd1d5",text_color=TEXT,
                command=lambda rid=x["id"]:self.edit_role(rid)
            ).pack(side="left",padx=2)
            ctk.CTkButton(
                actions,text="REMOVER",width=82,height=31,
                fg_color="#eadada",hover_color="#dfcaca",text_color=RED,
                command=lambda rid=x["id"]:self.remove_role(rid)
            ).pack(side="left",padx=2)

    def run(self):
        self.root.mainloop()

if __name__=="__main__":
    RHFacil().run()
