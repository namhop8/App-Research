"""Theo dõi CPU, RAM, GPU của máy cho thanh trạng thái trên app (chỉ dùng thư viện chuẩn).

CPU/RAM: Windows API qua ctypes. GPU: nvidia-smi (card NVIDIA); không có thì bỏ trống.
Đo trong một luồng nền mỗi 3 giây; app đọc kết quả mới nhất qua stats().
"""
import ctypes
import os
import shutil
import subprocess
import threading
import time

_stats = {"cpu": None, "ram": None, "gpu": None, "t": 0}
_started = False


class _FILETIME(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


class _MEMSTATUS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
                ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64)]


def _ft(f):
    return (f.hi << 32) | f.lo


def _cpu_times():
    idle, kern, user = _FILETIME(), _FILETIME(), _FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    return _ft(idle), _ft(kern) + _ft(user)  # thời gian kernel đã gồm idle


def _ram():
    m = _MEMSTATUS()
    m.dwLength = ctypes.sizeof(_MEMSTATUS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    total, free = m.ullTotalPhys, m.ullAvailPhys
    return {"pct": round((total - free) * 100 / total, 1), "used_gb": round((total - free) / 2**30, 1),
            "total_gb": round(total / 2**30, 1)}


def _gpu():
    exe = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    if not os.path.exists(exe):
        return None
    r = subprocess.run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not r.stdout.strip():
        return None
    name, util, used, total, temp = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
    return {"name": name.replace("NVIDIA GeForce ", ""), "pct": float(util), "mem_gb": round(float(used) / 1024, 1),
            "mem_total_gb": round(float(total) / 1024, 1), "temp": float(temp) if temp.replace(".", "").isdigit() else None}


def _loop():
    prev = _cpu_times() if os.name == "nt" else None
    while True:
        time.sleep(3)
        try:
            if os.name == "nt":
                cur = _cpu_times()
                d_idle, d_total = cur[0] - prev[0], cur[1] - prev[1]
                prev = cur
                _stats["cpu"] = {"pct": round(max(0.0, 100 * (1 - d_idle / d_total)), 1) if d_total else 0.0,
                                 "cores": os.cpu_count()}
                _stats["ram"] = _ram()
            _stats["gpu"] = _gpu()
            _stats["t"] = int(time.time())
        except Exception:  # noqa: BLE001  đo hỏng một lần thì bỏ qua, lần sau đo lại
            pass


def start():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_loop, daemon=True).start()


def stats():
    return dict(_stats)
