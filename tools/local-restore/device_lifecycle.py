"""Start/stop only the configured local GTK VM; never erase or restore disks."""
import json
import os
from pathlib import Path
import subprocess
import time

from qmp import execute

CONTAINER = "inferno-native-window"
VM = Path(__file__).resolve().parents[3] / "local-inferno-vm-qmp-sparse"


def docker(*args, timeout=15):
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def normalized(path):
    return os.path.normcase(os.path.abspath(path)).rstrip("\\/")


def inspect_vm():
    result = docker("inspect", "--type", "container", CONTAINER)
    if result.returncode:
        raise RuntimeError("Контейнер iOS недоступен. Проверь Docker Desktop.")
    info = json.loads(result.stdout)[0]
    command = info["Config"].get("Cmd") or []
    mounts = info.get("Mounts", [])
    expected = normalized(VM)
    if (info["Config"]["Image"] != "inferno-local:native-gui" or
            "/app-source/tools/local-restore/run.py" not in command or
            "--display" not in command or "gtk" not in command or
            "--restore" in command or "--patch-only" in command or
            not any(m.get("Destination") == "/vm" and m.get("RW") and
                    normalized(m["Source"]) == expected for m in mounts)):
        raise RuntimeError("Конфигурация контейнера отличается. Запуск и остановка отменены.")
    bindings = info.get("HostConfig", {}).get("PortBindings", {}).get("4444/tcp", [])
    if not any(p.get("HostIp") == "127.0.0.1" and p.get("HostPort") == "4444" for p in bindings):
        raise RuntimeError("Порт управления контейнера отличается. Действие отменено.")
    return info


def state():
    if docker("info", "--format", "{{.ServerVersion}}", timeout=8).returncode:
        return "offline"
    info = inspect_vm()
    if not info["State"]["Running"]:
        return "stopped"
    return "running" if execute("query-status").get("running") else "paused"


def ensure_exclusive():
    result = docker("ps", "-q")
    if result.returncode:
        raise RuntimeError("Не удалось проверить запущенные виртуальные машины.")
    ids = result.stdout.split()
    if not ids:
        return
    result = docker("inspect", *ids)
    if result.returncode:
        raise RuntimeError("Не удалось проверить, свободны ли диски iOS.")
    for info in json.loads(result.stdout):
        for mount in info.get("Mounts", []):
            source = normalized(mount.get("Source", ""))
            target = normalized(VM)
            if mount.get("RW") and (source == target or target.startswith(source + os.sep)
                                    or source.startswith(target + os.sep)):
                raise RuntimeError("Диски iOS уже использует другая виртуальная машина.")


def start(progress=lambda text: None):
    if docker("info", "--format", "{{.ServerVersion}}", timeout=8).returncode:
        progress("Запускаю Docker Desktop…")
        result = docker("desktop", "start", "--timeout", "120", timeout=125)
        if result.returncode:
            raise RuntimeError("Docker Desktop не запустился. Открой его и повтори запуск.")
    info = inspect_vm()
    if info["State"]["Running"]:
        if not execute("query-status").get("running"):
            execute("cont")
        return "running"
    ensure_exclusive()
    progress("Запускаю QEMU и установленную iOS…")
    if docker("start", CONTAINER, timeout=30).returncode:
        raise RuntimeError("Не удалось запустить QEMU. Диски не изменялись панелью.")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not inspect_vm()["State"]["Running"]:
            raise RuntimeError("QEMU завершился при запуске. Нужна проверка журнала.")
        try:
            if execute("query-status").get("running"):
                return "running"
        except (OSError, RuntimeError, ValueError):
            pass
        time.sleep(.5)
    raise RuntimeError("QEMU запущен, но пока не отвечает. Повторный запуск не выполнялся.")


def stop(progress=lambda text: None):
    info = inspect_vm()
    if not info["State"]["Running"]:
        return "stopped"
    progress("Останавливаю QEMU с сохранением дисков…")
    try:
        execute("quit")
    except (ConnectionError, OSError):
        pass  # QMP can disconnect before acknowledging quit; check actual exit below.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not inspect_vm()["State"]["Running"]:
            return "stopped"
        time.sleep(.5)
    raise RuntimeError("QEMU не завершился. Принудительная остановка не выполнялась.")


def restart(progress=lambda text: None):
    stop(progress)
    return start(progress)
