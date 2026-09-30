"""Verificação e aplicação de atualizações do RH Fácil via GitHub Releases.

Quando importado pelo aplicativo, expõe funções para consultar a versão mais recente
em um repositório público do GitHub. Quando executado como RH Facil Updater.exe,
aplica um pacote ZIP depois que o RH Fácil principal foi encerrado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Optional

APP_NAME = "RH Fácil"
DEFAULT_REPOSITORY = "JoaoTrindade-redes/RhFacil.API"
API_VERSION = "2026-03-10"
ASSET_PREFIX = "RH_Facil_v"
ASSET_SUFFIX = "_Portatil_Windows_x64.zip"


def _config_dir() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        path = Path(os.environ["LOCALAPPDATA"]) / "RHFacil"
    else:
        path = Path.home() / ".rhfacil"
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = _config_dir() / "update.json"
LOG_PATH = _config_dir() / "update.log"


def _log(message: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def load_repository() -> str:
    """Lê o repositório configurado; aceita owner/repo ou URL do GitHub."""
    try:
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            value = str(raw.get("repository", "")).strip()
            if value:
                return normalize_repository(value)
    except Exception:
        pass
    return normalize_repository(DEFAULT_REPOSITORY)


def save_repository(repository: str) -> str:
    repo = normalize_repository(repository)
    CONFIG_PATH.write_text(json.dumps({"repository": repo}, ensure_ascii=False, indent=2), encoding="utf-8")
    return repo


def normalize_repository(repository: str) -> str:
    """Converte URL HTTPS/SSH ou owner/repo para o formato owner/repo."""
    value = (repository or "").strip().rstrip("/")
    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    if value.endswith(".git"):
        value = value[:-4]
    return value


def repository_configured() -> bool:
    repo = load_repository()
    return bool(repo and "/" in repo and not repo.startswith("SEU_USUARIO/"))


def version_tuple(value: str) -> tuple[int, ...]:
    value = str(value or "").strip().lower().lstrip("v")
    parts = []
    for piece in value.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def _request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "RH-Facil-Updater/0.3.7",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def check_for_update(current_version: str, repository: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Retorna informações da release mais recente se ela for mais nova."""
    repo = normalize_repository(repository or load_repository())
    if not repo or "/" not in repo or repo.startswith("SEU_USUARIO/"):
        return None

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        release = _request_json(url)
        tag = str(release.get("tag_name") or release.get("name") or "").strip()
        if not tag or not is_newer(tag, current_version):
            return None

        assets = release.get("assets") or []
        asset = None
        for item in assets:
            name = str(item.get("name") or "")
            if name.startswith(ASSET_PREFIX) and name.endswith(ASSET_SUFFIX):
                asset = item
                break
        if not asset:
            _log(f"Release {tag} encontrada, mas sem pacote Windows esperado.")
            return None

        return {
            "version": tag,
            "name": str(release.get("name") or tag),
            "notes": str(release.get("body") or "").strip(),
            "asset_name": str(asset.get("name") or ""),
            "download_url": str(asset.get("browser_download_url") or ""),
            "digest": str(asset.get("digest") or ""),
            "size": int(asset.get("size") or 0),
            "html_url": str(release.get("html_url") or ""),
        }
    except Exception as exc:
        _log(f"Falha ao consultar atualizações: {exc}")
        return None


def download_update(info: dict[str, Any], destination: Path, progress_callback=None) -> Path:
    """Baixa o ZIP da release e valida o digest SHA-256 fornecido pelo GitHub."""
    url = info["download_url"]
    if not url:
        raise RuntimeError("A release não possui endereço de download.")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": "RH-Facil-Updater/0.3.7"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, temp_path.open("wb") as out:
            total = int(response.headers.get("Content-Length") or info.get("size") or 0)
            done = 0
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress_callback:
                    progress_callback(done, total)
        digest = (info.get("digest") or "").strip().lower()
        if digest.startswith("sha256:"):
            expected = digest.split(":", 1)[1]
            actual = hashlib.sha256(temp_path.read_bytes()).hexdigest()
            if actual.lower() != expected:
                raise RuntimeError("A verificação de integridade do pacote falhou (SHA-256 diferente do informado pelo GitHub).")
        temp_path.replace(destination)
        return destination
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _wait_for_process(pid: int, timeout: float = 30.0) -> None:
    if pid <= 0:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _process_exists(pid):
            return
        time.sleep(0.4)


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            pass
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _find_package_root(extracted: Path) -> Path:
    expected = extracted / "RH Facil"
    if expected.is_dir():
        return expected
    children = [p for p in extracted.iterdir() if p.is_dir()]
    if len(children) == 1 and (children[0] / "RH Facil.exe").exists():
        return children[0]
    if (extracted / "RH Facil.exe").exists():
        return extracted
    for p in extracted.rglob("RH Facil.exe"):
        return p.parent
    raise RuntimeError("O pacote não contém RH Facil.exe em uma estrutura reconhecida.")


def apply_update(package: Path, target_dir: Path, pid: int = 0, expected_version: str = "") -> int:
    """Aplica o pacote preservando os dados fora da pasta do executável."""
    package = Path(package).resolve()
    target_dir = Path(target_dir).resolve()
    _log(f"Aplicando atualização {expected_version} de {package} para {target_dir}.")
    _wait_for_process(pid)

    if not package.exists():
        raise RuntimeError("Pacote de atualização não encontrado.")
    if not target_dir.exists():
        raise RuntimeError("Pasta de instalação do RH Fácil não encontrada.")

    with tempfile.TemporaryDirectory(prefix="rhfacil_update_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(package, "r") as z:
            z.extractall(tmp_path)
        source = _find_package_root(tmp_path)

        backup_dir = tmp_path / "old_program"
        backup_dir.mkdir()
        # Move apenas arquivos da aplicação. O banco externo fica em Documentos\RH Fácil.
        for source_item in source.iterdir():
            destination = target_dir / source_item.name
            if destination.exists() and destination.is_dir():
                shutil.copytree(source_item, destination, dirs_exist_ok=True)
            elif source_item.is_file():
                shutil.copy2(source_item, destination)

    try:
        package.unlink(missing_ok=True)
    except Exception:
        pass
    _log(f"Atualização {expected_version} aplicada com sucesso.")
    return 0


def launch_updated_app(target_dir: Path) -> None:
    exe = Path(target_dir) / "RH Facil.exe"
    if exe.exists():
        subprocess.Popen([str(exe)], cwd=str(target_dir), close_fds=True)


def run_updater_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Atualizador do RH Fácil")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--package", required=False)
    parser.add_argument("--target-dir", required=False)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--version", default="")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args(argv)

    if not args.apply:
        return 0
    try:
        result = apply_update(Path(args.package), Path(args.target_dir), args.pid, args.version)
        if args.restart:
            launch_updated_app(Path(args.target_dir))
        return result
    except Exception as exc:
        _log(f"ERRO ao aplicar atualização: {exc}")
        # Em modo GUI, registre o erro. O aplicativo antigo continua disponível.
        return 1


if __name__ == "__main__":
    raise SystemExit(run_updater_cli())
