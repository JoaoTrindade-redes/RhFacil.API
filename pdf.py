"""Pequenos utilitários usados na geração das fichas PDF."""
import re

def safe_pdf_filename(name):
    return re.sub(r"[^A-Za-zÀ-ÿ0-9 _-]","",str(name or "Funcionário")).strip() or "Funcionario"
