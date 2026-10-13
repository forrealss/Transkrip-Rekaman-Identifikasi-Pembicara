"""Helper GPU.

Di Windows, ctranslate2 (mesin di balik faster-whisper) mencari DLL CUDA 12
(cublas64_12.dll, cudnn64_9.dll). DLL itu dipasang lewat paket pip
nvidia-cublas-cu12 / nvidia-cudnn-cu12, tapi foldernya tidak otomatis ada di
PATH. Fungsi siapkan_dll() mendaftarkan folder-folder itu.
"""
import os
import site
import sys
from pathlib import Path

_sudah = False


def siapkan_dll():
    global _sudah
    if _sudah or sys.platform != "win32":
        return
    for sp in site.getsitepackages():
        nvidia = Path(sp) / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in nvidia.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            # Sebagian DLL memuat DLL lain lewat PATH, jadi tambahkan juga ke PATH.
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
    _sudah = True


def pilih_device():
    """Kembalikan (device, compute_type) untuk faster-whisper."""
    import torch

    if torch.cuda.is_available():
        # int8_float16: bobot int8, hitungan float16 -> hemat VRAM (cocok untuk 6 GB)
        return "cuda", "int8_float16"
    return "cpu", "int8"


def info_perangkat():
    """Teks singkat perangkat yang dipakai, mis. 'NVIDIA GeForce RTX 3050 6GB Laptop GPU (6.0 GB VRAM, CUDA)'."""
    import torch

    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        return f"{p.name} ({p.total_memory / 1024**3:.1f} GB VRAM, CUDA)"
    import platform

    return f"CPU saja ({platform.processor() or platform.machine()})"


def _nama_cpu():
    import platform

    if sys.platform == "win32":
        try:
            import winreg

            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def _ram_gb():
    if sys.platform == "win32":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys / 1024**3
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (ValueError, OSError, AttributeError):
        return None


def _driver_nvidia():
    import subprocess

    try:
        hasil = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=10)
        return hasil.stdout.strip().splitlines()[0] if hasil.returncode == 0 else None
    except (OSError, IndexError, subprocess.SubprocessError):
        return None


def info_sistem():
    """Spesifikasi lengkap untuk dicatat bersama hasil (supaya hasil & kecepatan bisa dibandingkan)."""
    import platform
    from importlib.metadata import PackageNotFoundError, version

    import torch

    def v(paket):
        try:
            return version(paket)
        except PackageNotFoundError:
            return "?"

    ram = _ram_gb()
    info = {
        "GPU": info_perangkat(),
        "Driver NVIDIA": _driver_nvidia() or "-",
        "CPU": _nama_cpu(),
        "RAM": f"{ram:.0f} GB" if ram else "?",
        "Sistem operasi": f"{platform.system()} {platform.release()} (build {platform.version()})",
        "Python": platform.python_version(),
        "PyTorch": f"{torch.__version__} (CUDA {torch.version.cuda or '-'})",
        "faster-whisper": v("faster-whisper"),
        "ctranslate2": v("ctranslate2"),
        "pyannote.audio": v("pyannote.audio"),
    }
    return info


def bebaskan_vram():
    import gc

    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
