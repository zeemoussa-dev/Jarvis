"""
System Agent — query and manage the local Windows machine.
Provides CPU, memory, GPU, disk, network, and process information.
"""

import psutil
import subprocess

try:
    import pynvml
    pynvml.nvmlInit()
    _GPU_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
    _GPU_OK = True
except Exception:
    _GPU_OK = False


# ── Hardware queries ──────────────────────────────────────────────────────────

def _get_cpu() -> str:
    pct = psutil.cpu_percent(interval=1)
    freq = psutil.cpu_freq()
    cores = psutil.cpu_count(logical=False)
    threads = psutil.cpu_count(logical=True)
    freq_str = f"{freq.current:.0f} MHz" if freq else "unknown"
    procs = sorted(psutil.process_iter(["name", "cpu_percent"]),
                   key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:5]
    top = ", ".join(f"{p.info['name']} ({p.info['cpu_percent']:.1f}%)" for p in procs if p.info["cpu_percent"])
    return (f"CPU: {pct}% load, {cores} cores / {threads} threads at {freq_str}. "
            f"Top consumers: {top or 'none'}.")


def _get_memory() -> str:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    used_gb = vm.used / 1e9
    total_gb = vm.total / 1e9
    procs = sorted(psutil.process_iter(["name", "memory_info"]),
                   key=lambda p: (p.info.get("memory_info") or psutil._common.pmem(0, 0)).rss,
                   reverse=True)[:5]
    top = ", ".join(
        f"{p.info['name']} ({(p.info['memory_info'].rss / 1e6):.0f}MB)"
        for p in procs if p.info.get("memory_info")
    )
    return (f"RAM: {used_gb:.1f}GB used of {total_gb:.1f}GB ({vm.percent}%). "
            f"Swap: {sw.used / 1e9:.1f}GB of {sw.total / 1e9:.1f}GB. "
            f"Top consumers: {top or 'none'}.")


def _get_gpu() -> str:
    if not _GPU_OK:
        return "No NVIDIA GPU detected or pynvml unavailable."
    util     = pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE)
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(_GPU_HANDLE)
    temp     = pynvml.nvmlDeviceGetTemperature(_GPU_HANDLE, pynvml.NVML_TEMPERATURE_GPU)
    name     = pynvml.nvmlDeviceGetName(_GPU_HANDLE)
    used_gb  = mem_info.used / 1e9
    total_gb = mem_info.total / 1e9
    return (f"{name}: {util.gpu}% GPU load, {util.memory}% memory bandwidth. "
            f"VRAM: {used_gb:.1f}GB / {total_gb:.1f}GB. Temperature: {temp}°C.")


def _get_disk() -> str:
    lines = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            free_gb  = usage.free / 1e9
            total_gb = usage.total / 1e9
            lines.append(f"{part.device} ({part.mountpoint}): {usage.percent}% used, {free_gb:.1f}GB free of {total_gb:.1f}GB")
        except PermissionError:
            continue
    return "\n".join(lines) if lines else "No disk information available."


def _get_network() -> str:
    # Sample for 1 second to get rates
    net1 = psutil.net_io_counters()
    import time; time.sleep(1)
    net2 = psutil.net_io_counters()
    sent_mb = (net2.bytes_sent - net1.bytes_sent) / 1e6
    recv_mb = (net2.bytes_recv - net1.bytes_recv) / 1e6
    conns = len(psutil.net_connections())
    return (f"Network: ↑{sent_mb:.2f} MB/s upload, ↓{recv_mb:.2f} MB/s download. "
            f"Active connections: {conns}.")


def _list_processes(sort_by: str = "cpu", limit: int = 10) -> str:
    key = "cpu_percent" if sort_by == "cpu" else "memory_info"
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if sort_by == "cpu":
        procs.sort(key=lambda p: p.get("cpu_percent") or 0, reverse=True)
    else:
        procs.sort(key=lambda p: (p.get("memory_info") or psutil._common.pmem(0, 0)).rss, reverse=True)
    lines = [f"Top {limit} processes by {sort_by}:"]
    for p in procs[:limit]:
        mem_mb = ((p.get("memory_info") or psutil._common.pmem(0, 0)).rss) / 1e6
        cpu = p.get("cpu_percent", 0) or 0
        lines.append(f"  [{p['pid']}] {p['name']}: CPU {cpu:.1f}%, RAM {mem_mb:.0f}MB ({p.get('status', '')})")
    return "\n".join(lines)


def _kill_process(name: str) -> str:
    killed = []
    for p in psutil.process_iter(["name", "pid"]):
        if name.lower() in p.info["name"].lower():
            try:
                p.kill()
                killed.append(p.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return f"Killed: {', '.join(killed)}." if killed else f"No process matching '{name}' found."


def _get_services() -> str:
    """List running Windows services."""
    try:
        result = subprocess.run(
            ["sc", "query", "type=", "all", "state=", "running"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l for l in result.stdout.splitlines() if "SERVICE_NAME" in l]
        names = [l.split(":", 1)[1].strip() for l in lines]
        return f"Running services ({len(names)}): {', '.join(names[:20])}{'...' if len(names) > 20 else ''}."
    except Exception as e:
        return f"[Error] Could not list services: {e}"


def _system_report() -> str:
    parts = [
        _get_cpu(),
        _get_memory(),
        _get_gpu(),
    ]
    # Add disk summary
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            if usage.total > 1e9:
                free_gb = usage.free / 1e9
                parts.append(f"Disk {part.device}: {free_gb:.1f}GB free ({100-usage.percent:.0f}% available).")
        except PermissionError:
            continue
    return "\n".join(parts)


# ── Single tool ───────────────────────────────────────────────────────────────

def system_agent(action: str, sort_by: str = "cpu", limit: int = 10, name: str = None) -> str:
    try:
        match action:
            case "get_cpu":       return _get_cpu()
            case "get_memory":    return _get_memory()
            case "get_gpu":       return _get_gpu()
            case "get_disk":      return _get_disk()
            case "get_network":   return _get_network()
            case "list_processes": return _list_processes(sort_by, limit)
            case "kill_process":  return _kill_process(name or "")
            case "get_services":  return _get_services()
            case "system_report": return _system_report()
            case _:               return f"[Error] Unknown action '{action}'."
    except Exception as exc:
        return f"[Error] system_agent({action}) failed: {exc}"


TOOL_SCHEMA = {
    "name": "system_agent",
    "description": (
        "Query and manage the local machine. "
        "Actions: get_cpu, get_memory, get_gpu, get_disk, get_network, "
        "list_processes, kill_process, get_services, system_report."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "get_cpu", "get_memory", "get_gpu", "get_disk", "get_network",
                    "list_processes", "kill_process", "get_services", "system_report",
                ],
                "description": "The system action to perform.",
            },
            "sort_by": {"type": "string", "enum": ["cpu", "memory"], "description": "Sort order for list_processes."},
            "limit":   {"type": "integer", "description": "Number of processes to return (default 10)."},
            "name":    {"type": "string",  "description": "Process name fragment for kill_process."},
        },
        "required": ["action"],
    },
}

DISPATCH = {
    "system_agent": lambda **kw: system_agent(**kw),
}
