#!/usr/bin/env python3
"""SMART SERVER ENGINE. Python standard library; Minecraft stays unmodified."""
import argparse
import collections
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import queue
import re
import shutil
import signal
import socket
import socketserver
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

VERSION = "1.12.2"
SERVER_SHA1 = "886945bfb2b978778c3a0288fd7fab09d315b25f7"
SERVER_URL = f"https://piston-data.mojang.com/v1/objects/{SERVER_SHA1}/server.jar"
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MIB = 1024 * 1024


class SmartError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".smart-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def settings(path):
    """No shell evaluation, interpolation, or imports from user configuration."""
    data = {}
    if not Path(path).exists():
        return data
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        if "=" not in line:
            raise SmartError(f"Linha inválida em {path}: {line}")
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def number(cfg, key, default, low=0, high=1000000):
    try:
        val = int(cfg.get(key, default))
    except (TypeError, ValueError) as exc:
        raise SmartError(f"{key} precisa ser inteiro") from exc
    if not low <= val <= high:
        raise SmartError(f"{key}: permitido {low}..{high}")
    return val


def boolean(cfg, key, default=False):
    value = str(cfg.get(key, str(default))).lower()
    if value not in ("true", "false"):
        raise SmartError(f"{key} deve ser true ou false")
    return value == "true"


@contextlib.contextmanager
def lock(path, blocking=False):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise SmartError(f"Operação concorrente bloqueada: {Path(path).name}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def prepare(root):
    os.umask(0o077)
    for name in ("logs", "backups", ".run", ".runtime", ".cache"):
        (root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root / ".run", 0o700)
    if len(os.fsencode(root / ".run/control.sock")) >= 104:
        raise SmartError("Caminho longo demais para console Unix. Mova o projeto para ~/no ou /srv/smart-vanilla.")


def event(root, msg):
    line = f"{now()} {msg}"
    print(line, flush=True)
    try:
        with open(root / "logs/engine.log", "a", encoding="utf-8") as out:
            out.write(line + "\n")
    except OSError:
        print("Não foi possível gravar engine.log; confira espaço/permissões.", file=sys.stderr)


def props(root):
    cfg = settings(root / "server.properties")
    world = cfg.get("level-name", "world")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", world):
        raise SmartError("level-name deve conter somente letras, números, _ ou -, até 64 caracteres")
    number(cfg, "server-port", 25565, 1, 65535)
    if boolean(cfg, "enable-rcon"):
        raise SmartError("A engine usa stdin local. Mantenha enable-rcon=false.")
    if cfg.get("server-ip", "") not in ("", "127.0.0.1"):
        raise SmartError("Use server-ip= vazio, ou 127.0.0.1 para testes privados.")
    return cfg


def free_mb(root):
    return shutil.disk_usage(root).free // MIB


def ram():
    """Host /proc plus effective cgroup ancestor limits; unknown is not zero."""
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, val = line.split(":", 1)
            info[key] = int(val.strip().split()[0]) * 1024
        total = info["MemTotal"]
        available = info.get("MemAvailable")
        if available is None:
            raise ValueError("MemAvailable indisponível")
    except (OSError, ValueError, KeyError) as exc:
        raise SmartError("RAM disponível não pode ser medida neste ambiente (/proc/meminfo).") from exc
    # Walk the mounted cgroup directory and the process's relative hierarchy.
    bases = {Path("/sys/fs/cgroup")}
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            _, controllers, rel = line.split(":", 2)
            if not controllers or "memory" in controllers.split(","):
                mount = Path("/sys/fs/cgroup") / ("memory" if controllers else "")
                candidate = mount / rel.lstrip("/")
                if ".." not in candidate.parts:
                    bases.add(candidate)
    except OSError:
        pass
    for base in list(bases):
        while str(base).startswith("/sys/fs/cgroup"):
            for limitfile, currentfile in (("memory.max", "memory.current"),
                                           ("memory.limit_in_bytes", "memory.usage_in_bytes")):
                try:
                    limit = int((base / limitfile).read_text().strip())
                    used = int((base / currentfile).read_text().strip())
                    if 0 < limit < (1 << 60):
                        total = min(total, limit)
                        available = min(available, max(0, limit - used))
                except (OSError, ValueError):
                    pass
            if base == Path("/sys/fs/cgroup"):
                break
            base = base.parent
    return total // MIB, available // MIB


def memory_plan(cfg, total=None, available=None):
    if total is None or available is None:
        total, available = ram()
    profile = cfg.get("PROFILE", "equilibrado")
    ratios = {"economico": 20, "equilibrado": 30, "desempenho": 40}
    if profile not in ratios:
        raise SmartError("PROFILE: economico, equilibrado ou desempenho")
    reserve = number(cfg, "RESERVED_MB", 1024, 384, 65536)
    # Native VM overhead + OS/apps reserve; no swap included in available RAM.
    safe = min(total // 2, available - reserve - 256)
    requested = cfg.get("HEAP_MAX_MB", "auto")
    if requested == "auto":
        heap = min(total * ratios[profile] // 100, safe,
                   number(cfg, "MAX_AUTO_HEAP_MB", 2048, 512, 32768))
        heap = heap // 64 * 64
    else:
        heap = number(cfg, "HEAP_MAX_MB", 1024, 512, 65536)
        if heap > safe:
            raise SmartError(f"Heap {heap} MiB excede teto seguro atual {safe} MiB; reduza o heap/feche apps.")
    if heap < 512:
        raise SmartError(f"RAM insuficiente para heap seguro mínimo de 512 MiB (disponível {available} MiB).")
    initial = min(number(cfg, "HEAP_MIN_MB", 256, 128, 65536), heap)
    gc = ["-XX:+UseSerialGC"] if profile == "economico" else [
        "-XX:+UseG1GC", "-XX:ParallelGCThreads=2", "-XX:ConcGCThreads=1"]
    return {"profile": profile, "total_mb": total, "available_mb": available,
            "xms_mb": initial, "xmx_mb": heap,
            "flags": [f"-Xms{initial}M", f"-Xmx{heap}M", *gc,
                      "-Djava.awt.headless=true", "-Dfile.encoding=UTF-8"]}


def find_java(root):
    candidates = [os.environ.get("SMART_JAVA"), str(root / ".runtime/java8/bin/java")]
    if os.environ.get("JAVA_HOME"):
        candidates.append(str(Path(os.environ["JAVA_HOME"]) / "bin/java"))
    candidates.append(shutil.which("java"))
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
            continue
        try:
            run = subprocess.run([candidate, "-version"], capture_output=True, text=True, timeout=15)
            version = run.stderr + run.stdout
            if run.returncode == 0 and re.search(r'version "1\.8\.', version):
                return str(Path(candidate).resolve())
        except (OSError, subprocess.TimeoutExpired):
            pass
    raise SmartError("Java 8 executável não encontrado. Execute o instalador; Java 17/21 não é aceito automaticamente.")


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(MIB), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, hosts):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise SmartError(f"Origem de download não permitida: {parsed.hostname}")
    req = urllib.request.Request(url, headers={"User-Agent": "SmartVanillaServer/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        final = urllib.parse.urlsplit(response.url)
        if final.scheme != "https" or final.hostname not in hosts:
            raise SmartError("Redirecionamento de download não permitido")
        with open(dest, "wb") as out:
            shutil.copyfileobj(response, out, MIB)
            out.flush()
            os.fsync(out.fileno())


def download(root):
    target = root / "server.jar"
    with lock(root / ".run/download.lock"):
        if target.exists() and digest(target, "sha1") == SERVER_SHA1:
            print("Servidor oficial 1.12.2 já validado (SHA-1 fixado).")
            return
        if target.exists():
            raise SmartError("server.jar existente tem hash diferente; mova-o manualmente antes de reinstalar.")
        official = {"piston-meta.mojang.com", "launchermeta.mojang.com"}
        manifest = root / ".cache/version_manifest.json"
        fetch(MANIFEST_URL, manifest, official)
        versions = json.loads(manifest.read_text())["versions"]
        entry = next(v for v in versions if v["id"] == VERSION)
        metadata = root / ".cache/1.12.2.json"
        fetch(entry["url"], metadata, official)
        if digest(metadata, "sha1") != entry["sha1"]:
            raise SmartError("Metadados oficiais com SHA-1 inválido")
        info = json.loads(metadata.read_text())
        server = info["downloads"]["server"]
        if info["id"] != VERSION or server["sha1"] != SERVER_SHA1:
            raise SmartError("Manifesto não corresponde ao servidor oficial 1.12.2 fixado")
        tmp = root / ".cache/server.jar.partial"
        try:
            fetch(server["url"], tmp, {"piston-data.mojang.com", "launcher.mojang.com"})
            if tmp.stat().st_size != server["size"] or digest(tmp, "sha1") != SERVER_SHA1:
                raise SmartError("Falha de integridade no JAR oficial")
            with zipfile.ZipFile(tmp) as jar:
                if "net/minecraft/server/MinecraftServer.class" not in jar.namelist():
                    raise SmartError("JAR sem classe do servidor Vanilla")
            os.replace(tmp, target)
            atomic(root / "server.jar.sha256", digest(target) + "  server.jar\n")
            event(root, f"Download oficial confirmado: Minecraft {VERSION}, SHA-1 {SERVER_SHA1}")
        finally:
            tmp.unlink(missing_ok=True)


def install_java(root):
    try:
        print(find_java(root))
        return
    except SmartError:
        pass
    if "com.termux" in os.environ.get("PREFIX", "") and not os.environ.get("PD_CONTAINER"):
        raise SmartError("Temurin Linux usa glibc, incompatível com Bionic. Use install-termux.sh e PRoot.")
    arches = {"aarch64": "aarch64", "arm64": "aarch64", "x86_64": "x64", "amd64": "x64",
              "armv7l": "arm", "armv8l": "arm"}
    arch = arches.get(platform.machine().lower())
    if not arch:
        raise SmartError(f"Java 8 automático não suportado nesta arquitetura: {platform.machine()}")
    with lock(root / ".run/java-install.lock"):
        meta = root / ".cache/adoptium.json"
        url = f"https://api.adoptium.net/v3/assets/latest/8/hotspot?architecture={arch}&image_type=jdk&os=linux&vendor=eclipse"
        fetch(url, meta, {"api.adoptium.net"})
        assets = json.loads(meta.read_text())
        if not assets:
            raise SmartError("Adoptium não oferece Java 8 para esta arquitetura")
        asset = assets[0]
        binary = asset["binary"]
        package = binary["package"]
        if binary["architecture"] != arch or binary["os"] != "linux" or asset["version"]["major"] != 8:
            raise SmartError("Runtime baixado não corresponde ao Java 8/Linux esperado")
        checksum = package["checksum"]
        if not re.fullmatch("[a-f0-9]{64}", checksum):
            raise SmartError("Checksum inválido do runtime")
        archive = root / ".cache/java8.tar.gz.partial"
        stage = Path(tempfile.mkdtemp(prefix="java8-", dir=root / ".runtime"))
        try:
            fetch(package["link"], archive, {"github.com", "release-assets.githubusercontent.com",
                                           "objects.githubusercontent.com", "api.adoptium.net"})
            if digest(archive) != checksum:
                raise SmartError("SHA-256 do Java 8 inválido")
            with tarfile.open(archive, "r:gz") as tar:
                # Runtime trusted only after digest check. Reject traversal and unsafe links.
                members = tar.getmembers()
                for member in members:
                    p = PurePosixPath(member.name)
                    if p.is_absolute() or ".." in p.parts or not p.parts:
                        raise SmartError("Caminho inseguro no runtime")
                    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                        raise SmartError("Tipo de arquivo inesperado no runtime")
                    if member.issym() or member.islnk():
                        target = PurePosixPath(member.linkname)
                        base = stage / member.name
                        resolved = ((base.parent if member.issym() else stage) / member.linkname).resolve()
                        if target.is_absolute() or not resolved.is_relative_to(stage.resolve()):
                            raise SmartError("Link inseguro no runtime")
                # Files first, links last: compatible with Python 3.9+, without
                # relying on a distro-specific tarfile security backport.
                for member in members:
                    dest = stage / member.name
                    if member.isdir():
                        dest.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with tar.extractfile(member) as src, open(dest, "xb") as out:
                            shutil.copyfileobj(src, out, MIB)
                        os.chmod(dest, 0o755 if member.mode & 0o111 else 0o644)
                for member in members:
                    dest = stage / member.name
                    if member.islnk():
                        os.link(stage / member.linkname, dest)
                for member in members:
                    if member.issym():
                        os.symlink(member.linkname, stage / member.name)
            tops = list(stage.iterdir())
            if len(tops) != 1 or not (tops[0] / "bin/java").exists():
                raise SmartError("Estrutura inesperada do Java 8")
            dest = root / ".runtime/java8"
            if dest.exists():
                raise SmartError("Runtime anterior inválido: mova .runtime/java8 antes de reinstalar")
            os.replace(tops[0], dest)
            print(find_java(root))
            atomic(root / ".runtime/java8-source.json", json.dumps({"url": package["link"], "sha256": checksum, "installed_at": now()}, indent=2))
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            archive.unlink(missing_ok=True)


def ensure_eula(root, accept=False):
    path = root / "eula.txt"
    if settings(path).get("eula", "false").lower() == "true":
        return
    if not accept and sys.stdin.isatty():
        print("Leia https://aka.ms/MinecraftEULA . Você aceita a EULA? Digite ACEITO:")
        accept = input().strip() == "ACEITO"
    if not accept:
        if not path.exists():
            atomic(path, "# Leia https://aka.ms/MinecraftEULA\neula=false\n")
        raise SmartError("EULA não aceita. Execute o instalador em um terminal ou use --accept-eula após ler e aceitar.")
    atomic(path, "# Aceitação explícita pelo operador. https://aka.ms/MinecraftEULA\neula=true\n")


def sockpath(root):
    return str(root / ".run/control.sock")


def request(root, op, **kwargs):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(900 if op == "backup" else 180)
        try:
            client.connect(sockpath(root))
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise SmartError("Supervisor desligado; execute start-termux.sh ou start-linux.sh.") from exc
        client.sendall((json.dumps({"op": op, **kwargs}) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk:
                raise SmartError("Console fechou antes da resposta; consulte os logs.")
            data += chunk
            if len(data) > 2 * MIB:
                raise SmartError("Resposta do console muito grande")
        answer = json.loads(data)
        if not answer.get("ok"):
            raise SmartError(answer.get("error", "Falha no console"))
        return answer.get("result")


def directory_size(path):
    size = 0
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            p = Path(parent) / name
            if p.is_symlink():
                raise SmartError(f"Link no mundo não permitido: {p}")
            if not (stat.S_ISREG(p.stat().st_mode) or stat.S_ISDIR(p.stat().st_mode)):
                raise SmartError(f"Arquivo especial no mundo não permitido: {p}")
            if p.is_file():
                size += p.stat().st_size
    return size


def backup_offline(root, reason="manual"):
    """Caller holds engine.lock, and Java MUST have exited before calling."""
    cfg = settings(root / "config/backup.conf")
    name = props(root).get("level-name", "world")
    world = root / name
    if not world.is_dir() or world.is_symlink() or not (world / "level.dat").is_file():
        raise SmartError("Mundo válido ainda não existe para backup")
    with lock(root / ".run/backup.lock"):
        size = directory_size(world)
        reserve = number(cfg, "BACKUP_RESERVE_MB", 512, 16)
        if free_mb(root) < ((size * 2) // MIB + reserve):
            raise SmartError("Sem espaço seguro para backup; nenhum backup anterior será apagado para abrir espaço")
        prefix = "pre-restore-" if reason == "pre-restore" else "smartvanilla-"
        dest = root / "backups" / (prefix + stamp() + ".tar.gz")
        temp = dest.with_suffix(dest.suffix + ".partial")
        try:
            manifest = {"format": 1, "minecraft": VERSION, "world": name, "created_at": now(),
                        "reason": reason, "consistent": "java-stopped"}
            with tarfile.open(temp, "w:gz", compresslevel=1) as tar:
                tar.add(world, arcname=name, recursive=True)
                for extra in ("server.properties", "ops.json", "whitelist.json", "banned-ips.json", "banned-players.json"):
                    p = root / extra
                    if p.is_file() and not p.is_symlink():
                        tar.add(p, arcname=extra)
                import io
                raw = json.dumps(manifest, indent=2).encode()
                item = tarfile.TarInfo("smart-backup.json")
                item.size = len(raw)
                item.mode = 0o600
                tar.addfile(item, io.BytesIO(raw))
            with open(temp, "rb") as handle:
                os.fsync(handle.fileno())
            checksum = digest(temp)
            os.replace(temp, dest)
            atomic(str(dest) + ".sha256", checksum + "  " + dest.name + "\n")
            atomic(root / ".run/last-backup.json", json.dumps({"at": now(), "file": dest.name}))
            # Rotation only after a successful snapshot. Pre-restore copies are retained.
            keep = number(cfg, "KEEP_BACKUPS", 10, 1, 10000)
            olds = sorted((root / "backups").glob("smartvanilla-*.tar.gz"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
            for old in olds[keep:]:
                if Path(str(old) + ".sha256").exists():
                    old.unlink()
                    Path(str(old) + ".sha256").unlink(missing_ok=True)
            event(root, f"Backup consistente: {dest.name}")
            return str(dest)
        finally:
            temp.unlink(missing_ok=True)


def restore(root, archive, confirmed):
    if not confirmed:
        raise SmartError("Restauração requer --confirm-restore após parar o servidor e conferir o arquivo")
    with lock(root / ".run/engine.lock"), lock(root / ".run/backup.lock"):
        # Validate everything before moving the current world.
        archive = Path(archive).resolve()
        check = Path(str(archive) + ".sha256")
        expected = check.read_text().split() if check.is_file() else []
        if not expected or not re.fullmatch("[a-f0-9]{64}", expected[0]) or digest(archive) != expected[0]:
            raise SmartError("Backup sem SHA-256 válido")
        world_name = props(root).get("level-name", "world")
        stage = Path(tempfile.mkdtemp(prefix="restore-", dir=root / ".cache"))
        try:
            with tarfile.open(archive, "r:gz") as tar:
                members = tar.getmembers()
                names = set()
                allowed = {world_name, "smart-backup.json", "server.properties", "ops.json", "whitelist.json", "banned-ips.json", "banned-players.json"}
                for item in members:
                    p = PurePosixPath(item.name)
                    if (not p.parts or p.is_absolute() or ".." in p.parts or p.parts[0] not in allowed
                            or not (item.isfile() or item.isdir()) or item.name in names):
                        raise SmartError("Arquivo inseguro ou inesperado no backup")
                    names.add(item.name)
                total = sum(m.size for m in members if m.isfile())
                if free_mb(root) < total // MIB + 512:
                    raise SmartError("Espaço insuficiente para preparar restauração")
                # Manual extraction: no symlinks, devices, traversal, owner/mode restoration.
                for item in members:
                    dest = stage / item.name
                    if item.isdir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with tar.extractfile(item) as src, open(dest, "xb") as out:
                            shutil.copyfileobj(src, out, MIB)
            meta = read_json(stage / "smart-backup.json", {})
            if meta.get("format") != 1 or meta.get("minecraft") != VERSION or meta.get("world") != world_name:
                raise SmartError("Backup incompatível com esta versão/level-name")
            if not (stage / world_name / "level.dat").is_file():
                raise SmartError("Backup não contém level.dat")
            old = root / world_name
            if old.is_symlink():
                raise SmartError("Mundo atual é um link; restauração recusada")
            previous = root / "backups" / ("restore-previous-" + stamp())
            if old.exists():
                previous.mkdir()
                os.replace(old, previous / world_name)
            try:
                os.replace(stage / world_name, old)
            except OSError:
                if (previous / world_name).exists():
                    os.replace(previous / world_name, old)
                raise
            event(root, f"Mundo restaurado de {archive.name}; mundo anterior preservado em {previous.name}")
            return str(old)
        finally:
            shutil.rmtree(stage, ignore_errors=True)


def tcp_open(root):
    cfg = props(root)
    try:
        with socket.create_connection(("127.0.0.1", number(cfg, "server-port", 25565, 1, 65535)), timeout=1):
            return True
    except OSError:
        return False


def process_metrics(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        ticks = int(fields[11]) + int(fields[12])
        rss = int(fields[21]) * os.sysconf("SC_PAGE_SIZE") / MIB
        return {"rss_mb": round(rss, 1), "cpu_seconds": ticks / os.sysconf("SC_CLK_TCK")}
    except (OSError, ValueError, IndexError):
        return {"rss_mb": None, "cpu_seconds": None}


class Supervisor:
    def __init__(self, root):
        self.root = root
        self.mc = settings(root / "config/memory.conf")
        self.maint = settings(root / "config/maintenance.conf")
        self.bc = settings(root / "config/backup.conf")
        props(root)
        if boolean(self.maint, "DESTRUCTIVE_ITEM_CLEANUP"):
            raise SmartError("Limpeza destrutiva não pode garantir preservação no Vanilla 1.12.2; use false.")
        if self.mc.get("CRITICAL_ACTION", "restart") not in ("stop", "restart"):
            raise SmartError("CRITICAL_ACTION deve ser stop ou restart")
        self.stopping = threading.Event()
        self.ready = threading.Event()
        self.requests = queue.Queue()
        self.lines = collections.deque(maxlen=2000)
        self.cond = threading.Condition()
        self.seq = 0
        self.child = None
        self.reader = None
        self.server = None
        self.started = time.monotonic()
        self.phase = "preparando"
        self.restarts = 0
        self.critical_samples = 0
        self.last_cpu = None
        self.cpu_pct = None
        self.plan = None
        self.last_save = read_json(root / ".run/last-save.json")
        self.intent = None
        self.ready_once = False
        self.logfile = None
        self.overload_events = 0
        self.last_overload = None
        self.last_overload_log = 0

    def state(self):
        pid = self.child.pid if self.child and self.child.poll() is None else None
        return {"state": self.phase, "supervisor_pid": os.getpid(), "java_pid": pid,
                "uptime_seconds": round(time.monotonic() - self.started),
                "java_uptime_seconds": round(time.monotonic() - self.child_started) if pid else None,
                "java": process_metrics(pid) if pid else None, "cpu_percent": self.cpu_pct,
                "free_disk_mb": free_mb(self.root), "heap": self.plan,
                "last_save": self.last_save, "last_backup": read_json(self.root / ".run/last-backup.json"),
                "tcp_local": tcp_open(self.root), "restarts": self.restarts,
                "overload_events": self.overload_events, "last_overload": self.last_overload,
                "metrics_note": "CPU amostrada por processo; N/D quando Android restringe /proc. TCP local não prova acesso público. TPS não disponível."}

    def serve_console(self):
        supervisor = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(5)
                try:
                    raw = self.rfile.readline(4097)
                    if len(raw) > 4096:
                        raise SmartError("Pedido muito grande")
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise SmartError("Pedido precisa ser um objeto JSON")
                    op = data.get("op")
                    if op == "status":
                        result = supervisor.state()
                    elif op == "stop":
                        supervisor.stopping.set()
                        result = "Encerramento solicitado; aguarde o salvamento e o backup final."
                    elif op in ("command", "save", "restart", "backup", "audit-items"):
                        if supervisor.stopping.is_set():
                            raise SmartError("Encerramento já solicitado")
                        if op == "command" and str(data.get("command", "")).strip().lstrip("/").lower() == "stop":
                            supervisor.stopping.set()
                            result = "Encerramento solicitado."
                        else:
                            task = {"data": data, "done": threading.Event()}
                            supervisor.requests.put(task)
                            if not task["done"].wait(850 if op == "backup" else 160):
                                raise SmartError("Pedido ainda não concluído; confira logs antes de repetir")
                            if "error" in task:
                                raise SmartError(task["error"])
                            result = task.get("result")
                    else:
                        raise SmartError("Operação desconhecida")
                    answer = {"ok": True, "result": result}
                except (SmartError, OSError, ValueError) as exc:
                    answer = {"ok": False, "error": str(exc)}
                try:
                    self.wfile.write((json.dumps(answer) + "\n").encode())
                except OSError:
                    pass

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        path = Path(sockpath(self.root))
        path.unlink(missing_ok=True)
        self.server = Server(str(path), Handler)
        os.chmod(path, 0o600)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def record_output(self, child, output):
        for line in child.stdout:
            line = line.rstrip("\r\n")
            try:
                output.write(line + "\n")
                output.flush()
            except OSError:
                self.stopping.set()
            try:
                print(line, flush=True)
            except (OSError, BrokenPipeError):
                pass
            with self.cond:
                self.seq += 1
                self.lines.append((self.seq, line))
                if "Can't keep up!" in line:
                    self.overload_events += 1
                    self.last_overload = now()
                    if time.monotonic() - self.last_overload_log >= 60:
                        event(self.root, "Sobrecarga indicada pelo log Vanilla: Can't keep up. Reduza exploração simultânea/view-distance após parar.")
                        self.last_overload_log = time.monotonic()
                if "Done (" in line and "For help" in line:
                    self.ready.set()
                    self.ready_once = True
                if "Flushed all saves" in line:
                    self.last_save = {"at": now(), "kind": "save-all flush confirmed"}
                    try:
                        atomic(self.root / ".run/last-save.json", json.dumps(self.last_save))
                    except OSError:
                        self.stopping.set()
                self.cond.notify_all()
        output.close()

    def command(self, cmd, expect=None, timeout=60):
        if not self.child or self.child.poll() is not None:
            raise SmartError("Java não está em execução")
        if "\n" in cmd or "\r" in cmd or len(cmd) > 2048:
            raise SmartError("Comando inválido")
        with self.cond:
            before = self.seq
            try:
                self.child.stdin.write(cmd.strip().lstrip("/") + "\n")
                self.child.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise SmartError("stdin do servidor indisponível") from exc
            if expect:
                end = time.monotonic() + timeout
                while time.monotonic() < end:
                    found = [line for seq, line in self.lines if seq > before and expect in line]
                    if found:
                        return "\n".join(found)
                    if self.child.poll() is not None:
                        break
                    self.cond.wait(min(0.5, max(0.01, end - time.monotonic())))
                raise SmartError(f"Sem confirmação '{expect}'; operação abortada")
        return "Comando enviado ao stdin; resposta aparece no log."

    def save(self):
        if not self.ready.is_set():
            raise SmartError("Servidor ainda não pronto")
        return self.command("save-all flush", "Flushed all saves")

    def launch_command(self):
        if digest(self.root / "server.jar", "sha1") != SERVER_SHA1:
            raise SmartError("server.jar tem hash inválido; início recusado")
        if settings(self.root / "eula.txt").get("eula", "false").lower() != "true":
            raise SmartError("Aceite a EULA pelo instalador antes de iniciar")
        return [find_java(self.root), *self.plan["flags"], "-jar", str(self.root / "server.jar"), "nogui"]

    def start_child(self):
        minimum = number(self.maint, "MIN_FREE_DISK_MB", 512, 16)
        if free_mb(self.root) < minimum:
            raise SmartError(f"Espaço livre abaixo de {minimum} MiB; início recusado")
        self.plan = memory_plan(self.mc)
        self.ready.clear()
        self.lines.clear()
        self.last_cpu = None
        self.cpu_pct = None
        self.critical_samples = 0
        self.phase = "iniciando"
        args = self.launch_command()
        event(self.root, f"Iniciando Java 8, heap {self.plan['xmx_mb']} MiB, perfil {self.plan['profile']}")
        self.logfile = self.root / "logs" / ("console-" + stamp() + ".log")
        output = open(self.logfile, "a", encoding="utf-8")
        self.child_started = time.monotonic()
        try:
            self.child = subprocess.Popen(args, cwd=self.root, stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          text=True, encoding="utf-8", errors="replace", bufsize=1)
        except BaseException:
            output.close()
            raise
        atomic(self.root / ".run/java.pid", str(self.child.pid))
        self.reader = threading.Thread(target=self.record_output, args=(self.child, output), daemon=True)
        self.reader.start()
        self.child_started = time.monotonic()

    def stop_child(self):
        if not self.child or self.child.poll() is not None:
            return
        self.phase = "salvando e encerrando"
        if self.ready.is_set():
            try:
                self.save()
            except SmartError as exc:
                event(self.root, f"Aviso no save-all: {exc}; solicitando stop para salvar no encerramento")
        self.command("stop")
        timeout = number(self.maint, "STOP_TIMEOUT_SECONDS", 120, 5, 600)
        try:
            self.child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            event(self.root, "Stop sem resposta: enviando SIGTERM para shutdown hook; não será usado SIGKILL")
            self.child.terminate()
            # Never copy or launch another Java while the old one is alive.
            while self.child.poll() is None:
                self.phase = "aguardando Java encerrar; intervenção pode ser necessária"
                time.sleep(1)
        self.reader.join(timeout=10)
        if self.child.returncode != 0:
            raise SmartError(f"Java terminou com código {self.child.returncode}; backup consistente recusado")

    def maintenance_backup(self):
        if not self.ready.is_set():
            raise SmartError("Aguarde servidor pronto para backup")
        self.phase = "aviso de backup"
        self.command("say [SMART] Backup consistente: reconecte apos a manutencao.")
        self.stopping.wait(number(self.maint, "BACKUP_WARNING_SECONDS", 10, 0, 120))
        self.stop_child()
        self.phase = "backup offline"
        self.intent = "maintenance"
        result = backup_offline(self.root)
        return result

    def task(self, task):
        try:
            data = task["data"]
            op = data["op"]
            if op == "command":
                cmd = str(data.get("command", "")).strip().lstrip("/")
                first = cmd.split(" ", 1)[0].lower()
                if first in ("stop", "save-all", "save-off", "save-on"):
                    raise SmartError("Use stop-server.sh ou console.sh --save; controles de salvamento reservados à engine")
                if not cmd:
                    raise SmartError("Comando vazio")
                task["result"] = self.command(cmd)
            elif op == "save":
                task["result"] = self.save()
            elif op == "restart":
                self.stop_child()
                self.intent = "maintenance"
                task["result"] = "Java encerrado com segurança; reinício solicitado."
            elif op == "backup":
                task["result"] = self.maintenance_backup()
            elif op == "audit-items":
                self.command("testfor @e[type=item]")
                task["result"] = "Auditoria enviada; veja logs. Nenhum item será apagado: Vanilla 1.12.2 não permite provar a ausência de nome/valor com seletores."
        except (SmartError, OSError) as exc:
            task["error"] = str(exc)
            event(self.root, f"Operação recusada/falhou: {exc}")
        finally:
            task["done"].set()

    def monitor(self):
        metrics = process_metrics(self.child.pid)
        current = time.monotonic()
        if metrics["cpu_seconds"] is not None:
            if self.last_cpu:
                old_time, old_cpu = self.last_cpu
                self.cpu_pct = round(max(0, metrics["cpu_seconds"] - old_cpu) / (current - old_time) * 100, 1)
            self.last_cpu = (current, metrics["cpu_seconds"])
        if free_mb(self.root) < number(self.maint, "CRITICAL_FREE_DISK_MB", 128, 16):
            event(self.root, "Espaço crítico: encerramento preventivo; sem reinício automático")
            self.stopping.set()
            return
        try:
            _, available = ram()
        except SmartError as exc:
            event(self.root, f"Métrica de memória indisponível: {exc}")
            return
        if available < number(self.mc, "CRITICAL_AVAILABLE_MB", 256, 64):
            self.critical_samples += 1
        else:
            self.critical_samples = 0
        if self.critical_samples >= number(self.mc, "CRITICAL_SAMPLES", 3, 1, 60):
            event(self.root, f"Pressão crítica de memória: {available} MiB disponíveis; parada controlada")
            if self.mc.get("CRITICAL_ACTION", "restart") == "restart" and boolean(self.maint, "AUTO_RECOVERY", True):
                self.intent = "pressure"
            else:
                self.stopping.set()

    def run(self):
        code = 0
        with lock(self.root / ".run/engine.lock"):
            atomic(self.root / ".run/supervisor.pid", str(os.getpid()))
            self.serve_console()
            old_handlers = {}
            for sig in (signal.SIGTERM, signal.SIGINT):
                old_handlers[sig] = signal.signal(sig, lambda *_: self.stopping.set())
            try:
                while not self.stopping.is_set():
                    self.intent = None
                    self.start_child()
                    last_save = last_backup = last_monitor = time.monotonic()
                    stable_reset = False
                    while self.child.poll() is None:
                        if self.stopping.is_set() or self.intent in ("pressure", "maintenance"):
                            self.stop_child()
                            break
                        if self.ready.is_set():
                            self.phase = "online"
                        elif time.monotonic() - self.child_started > number(self.maint, "STARTUP_TIMEOUT_SECONDS", 240, 5, 1800):
                            event(self.root, "Timeout de inicialização; parada sem reinício cego")
                            self.stopping.set()
                            code = 1
                            continue
                        try:
                            task = self.requests.get(timeout=0.2)
                            self.task(task)
                        except queue.Empty:
                            pass
                        if self.child.poll() is not None:
                            break
                        current = time.monotonic()
                        if current - last_monitor >= number(self.maint, "MONITOR_INTERVAL_SECONDS", 10, 1, 3600):
                            self.monitor()
                            last_monitor = current
                        if self.ready.is_set() and current - last_save >= number(self.maint, "SAVE_INTERVAL_SECONDS", 300, 10, 86400):
                            try:
                                self.save()
                            except SmartError as exc:
                                event(self.root, f"Salvamento não confirmado: {exc}")
                            last_save = current
                        interval = number(self.bc, "BACKUP_INTERVAL_SECONDS", 21600, 0, 604800)
                        if self.ready.is_set() and interval and current - last_backup >= interval:
                            try:
                                self.maintenance_backup()
                            except (SmartError, OSError) as exc:
                                event(self.root, f"Backup automático falhou: {exc}")
                            last_backup = current
                        if not stable_reset and self.ready.is_set() and current - self.child_started >= number(self.maint, "STABLE_RESET_SECONDS", 900, 30):
                            self.restarts = 0
                            stable_reset = True
                    self.child.wait()
                    self.reader.join(timeout=10)
                    self.child.stdin.close()
                    self.child.stdout.close()
                    (self.root / ".run/java.pid").unlink(missing_ok=True)
                    rc = self.child.returncode
                    event(self.root, f"Java encerrado: exit={rc}, motivo={self.intent or ('manual' if self.stopping.is_set() else 'processo')}")
                    if self.stopping.is_set():
                        if rc == 0 and self.ready_once and boolean(self.bc, "BACKUP_ON_STOP", True):
                            try:
                                backup_offline(self.root, "stop")
                            except (SmartError, OSError) as exc:
                                event(self.root, f"Backup final não criado: {exc}")
                        break
                    if self.intent == "maintenance":
                        self.phase = "reinício após manutenção"
                        self.stopping.wait(2)
                        continue
                    if rc == 0 and self.intent != "pressure":
                        if not self.ready.is_set():
                            event(self.root, "Java encerrou antes de Done; confira o console. Início não confirmado.")
                            code = 1
                        # /stop in game is also an intentional shutdown.
                        break
                    recent = "\n".join(line for _, line in self.lines)
                    apparent = "possível falta de memória" if ("OutOfMemoryError" in recent or rc in (-9, 137)) else "falha; consultar console/crash-reports"
                    event(self.root, f"Motivo aparente: {apparent}; SIGKILL também pode vir do Android, sem diagnóstico conclusivo")
                    if not boolean(self.maint, "AUTO_RECOVERY", True):
                        code = 1
                        break
                    self.restarts += 1
                    if self.restarts > number(self.maint, "MAX_RESTART_ATTEMPTS", 3, 0, 20):
                        event(self.root, "Limite de reinícios atingido; intervenção necessária")
                        code = 1
                        break
                    self.phase = "aguardando recuperação"
                    self.stopping.wait(number(self.maint, "RESTART_DELAY_SECONDS", 20, 1, 600))
            except (SmartError, OSError) as exc:
                event(self.root, f"Engine interrompida: {exc}")
                code = 1
                self.stopping.set()
                if self.child and self.child.poll() is None:
                    try:
                        self.stop_child()
                    except (SmartError, OSError) as stop_error:
                        event(self.root, f"Falha ao encerrar: {stop_error}")
            finally:
                if self.server:
                    self.server.shutdown()
                    self.server.server_close()
                if self.child and self.child.poll() is not None:
                    for stream in (self.child.stdin, self.child.stdout):
                        if stream:
                            stream.close()
                for sig, handler in old_handlers.items():
                    signal.signal(sig, handler)
                Path(sockpath(self.root)).unlink(missing_ok=True)
                (self.root / ".run/supervisor.pid").unlink(missing_ok=True)
                (self.root / ".run/java.pid").unlink(missing_ok=True)
                self.phase = "offline"
                atomic(self.root / ".run/last-exit.json", json.dumps({"at": now(), "code": code}))
                event(self.root, f"Supervisor finalizado; código {code}")
        return code


def print_status(root, as_json=False):
    try:
        data = request(root, "status")
    except SmartError:
        data = {"state": "offline / console indisponível", "java_pid": None,
                "free_disk_mb": free_mb(root), "last_backup": read_json(root / ".run/last-backup.json"),
                "last_save": read_json(root / ".run/last-save.json"), "tcp_local": tcp_open(root)}
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print("SMART VANILLA SURVIVAL 1.12.2")
    for key, label in (("state", "Estado"), ("java_pid", "PID Java"), ("uptime_seconds", "Tempo da engine (s)"),
                       ("java_uptime_seconds", "Tempo do Java (s)"),
                       ("java", "RAM/CPU acumulada"), ("cpu_percent", "CPU amostrada (%)"),
                       ("free_disk_mb", "Disco livre (MiB)"), ("last_save", "Último save"),
                       ("last_backup", "Último backup"), ("tcp_local", "TCP localhost")):
        print(f"{label}: {data.get(key) if data.get(key) is not None else 'N/D'}")
    print("TPS: indisponível no Vanilla. TCP local não confirma acesso externo.")
    try:
        print("Eventos recentes:\n" + "\n".join((root / "logs/engine.log").read_text().splitlines()[-6:]))
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    sub = parser.add_subparsers(dest="op", required=True)
    for name in ("run", "download", "install-java", "java", "memory", "backup", "save", "restart", "stop", "audit-items", "health"):
        sub.add_parser(name)
    setup = sub.add_parser("setup")
    setup.add_argument("--accept-eula", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    console = sub.add_parser("command")
    console.add_argument("text", nargs="+")
    rest = sub.add_parser("restore")
    rest.add_argument("archive")
    rest.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    prepare(root)
    if args.op == "setup":
        # Never replace configuration or world data during repeated installs.
        props(root)
        ensure_eula(root, args.accept_eula)
        find_java(root)
        download(root)
        print(json.dumps(memory_plan(settings(root / "config/memory.conf")), indent=2))
        print("Instalação preparada; use o inicializador.")
    elif args.op == "run":
        return Supervisor(root).run()
    elif args.op == "download":
        download(root)
    elif args.op == "install-java":
        install_java(root)
    elif args.op == "java":
        print(find_java(root))
    elif args.op == "memory":
        print(json.dumps(memory_plan(settings(root / "config/memory.conf")), indent=2))
    elif args.op == "status":
        print_status(root, args.json)
    elif args.op == "restore":
        print(restore(root, args.archive, args.confirm_restore))
    elif args.op == "backup":
        try:
            with lock(root / ".run/engine.lock"):
                print(backup_offline(root))
        except SmartError as exc:
            if "engine.lock" not in str(exc):
                raise
            print(request(root, "backup"))
    elif args.op == "health":
        data = request(root, "status")
        if data["state"] != "online" or not data["tcp_local"]:
            raise SmartError(f"Servidor não saudável: {data['state']}")
        print("Supervisor pronto e TCP local acessível; acesso público não foi verificado.")
    elif args.op == "command":
        print(request(root, "command", command=" ".join(args.text)))
    elif args.op == "stop":
        try:
            with lock(root / ".run/engine.lock"):
                print("Supervisor já está desligado. Nenhum processo externo foi alterado.")
                return 0
        except SmartError:
            pass
        print(request(root, "stop"))
        # Wait on the lock, not on stale PIDs; includes final backup completion.
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            try:
                with lock(root / ".run/engine.lock"):
                    print("Supervisor e Java encerrados.")
                    return 0
            except SmartError:
                time.sleep(0.5)
        raise SmartError("Parada ainda em andamento; não force reinício. Consulte os logs.")
    else:
        print(request(root, args.op))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (SmartError, OSError, ValueError, KeyError, StopIteration, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
