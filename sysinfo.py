#!/usr/bin/env python3
"""Sistem bilgilerini toplayan script (sadece stdlib, harici bağımlılık yok)."""

import json
import os
import platform
import socket
import subprocess


def get_cpu_info():
    info = {"core_count": os.cpu_count()}
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["model"] = line.split(":")[1].strip()
                    break
    except FileNotFoundError:
        info["model"] = platform.processor() or "unknown"
    try:
        load1, load5, load15 = os.getloadavg()
        info["load_avg"] = {"1min": load1, "5min": load5, "15min": load15}
    except OSError:
        pass
    return info


def get_memory_info():
    info = {}
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True
            )
            total_bytes = int(result.stdout.strip())
            info["total_mb"] = round(total_bytes / (1024 * 1024), 1)
            vm = subprocess.run(
                ["vm_stat"], capture_output=True, text=True
            )
            pages = {}
            for line in vm.stdout.strip().split("\n")[1:]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    val = val.strip().rstrip(".")
                    if val.isdigit():
                        pages[key.strip()] = int(val)
            page_size = 16384
            free = pages.get("Pages free", 0) * page_size
            inactive = pages.get("Pages inactive", 0) * page_size
            available = free + inactive
            info["available_mb"] = round(available / (1024 * 1024), 1)
            used = total_bytes - available
            info["used_mb"] = round(used / (1024 * 1024), 1)
            info["usage_percent"] = round(used / total_bytes * 100, 1)
            swap = subprocess.run(
                ["sysctl", "-n", "vm.swapusage"],
                capture_output=True, text=True
            )
            for part in swap.stdout.split(","):
                part = part.strip()
                if part.startswith("total"):
                    val = part.split("=")[1].strip().rstrip("M")
                    info["swap_total_mb"] = float(val)
                elif part.startswith("free"):
                    val = part.split("=")[1].strip().rstrip("M")
                    info["swap_free_mb"] = float(val)
        except Exception:
            pass
    else:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    key = parts[0].rstrip(":")
                    val_kb = int(parts[1])
                    if key == "MemTotal":
                        info["total_mb"] = round(val_kb / 1024, 1)
                    elif key == "MemAvailable":
                        info["available_mb"] = round(val_kb / 1024, 1)
                    elif key == "SwapTotal":
                        info["swap_total_mb"] = round(val_kb / 1024, 1)
                    elif key == "SwapFree":
                        info["swap_free_mb"] = round(val_kb / 1024, 1)
            if "total_mb" in info and "available_mb" in info:
                used = info["total_mb"] - info["available_mb"]
                info["used_mb"] = round(used, 1)
                info["usage_percent"] = round(used / info["total_mb"] * 100, 1)
        except FileNotFoundError:
            pass
    return info


def get_disk_info():
    disks = []
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["df", "-h"], capture_output=True, text=True
            )
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 9 and parts[0].startswith("/"):
                    disks.append({
                        "device": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "usage_percent": parts[4],
                        "mount": parts[8],
                    })
        else:
            result = subprocess.run(
                ["df", "-h", "--output=source,size,used,avail,pcent,target"],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 6 and parts[0].startswith("/"):
                    disks.append({
                        "device": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "usage_percent": parts[4],
                        "mount": parts[5],
                    })
    except Exception:
        pass
    return disks


def get_network_info():
    info = {"hostname": socket.gethostname()}
    try:
        info["fqdn"] = socket.getfqdn()
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["primary_ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return info


def get_os_info():
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sw_vers"], capture_output=True, text=True
            )
            for line in result.stdout.strip().split("\n"):
                if "ProductName" in line:
                    info["distro"] = line.split(":", 1)[1].strip()
                elif "ProductVersion" in line:
                    info["distro_version"] = line.split(":", 1)[1].strip()
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsb_release", "-d", "-s"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                info["distro"] = result.stdout.strip()
        except FileNotFoundError:
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            info["distro"] = line.split("=", 1)[1].strip().strip('"')
                            break
            except FileNotFoundError:
                pass
    return info


def get_uptime():
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "kern.boottime"],
                capture_output=True, text=True
            )
            import re
            match = re.search(r"sec = (\d+)", result.stdout)
            if match:
                import time
                boot_time = int(match.group(1))
                seconds = time.time() - boot_time
                days = int(seconds // 86400)
                hours = int((seconds % 86400) // 3600)
                minutes = int((seconds % 3600) // 60)
                return f"{days}d {hours}h {minutes}m"
        except Exception:
            pass
        return "unknown"
    else:
        try:
            with open("/proc/uptime") as f:
                seconds = float(f.read().split()[0])
                days = int(seconds // 86400)
                hours = int((seconds % 86400) // 3600)
                minutes = int((seconds % 3600) // 60)
                return f"{days}d {hours}h {minutes}m"
        except FileNotFoundError:
            return "unknown"


def main():
    report = {
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disks": get_disk_info(),
        "network": get_network_info(),
        "uptime": get_uptime(),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
