"""Bounded host stack diagnostics for a stalled, fresh restore test process.

Raw sample output remains in a temporary local folder and is never exported.
Only counts for fixed known function names leave this tool.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time

SYMBOLS = (
    "dwc3_td_fetch", "dwc3_bd_length", "dwc3_bd_writeback", "dwc3_process_packet",
    "dwc3_bd_rw", "dart_translate", "dart_tlb_invalidate", "cpu_exec", "tcg_cpu_exec",
    "qemu_mutex_lock_impl", "bql_lock_impl", "__psynch_mutexwait", "__ulock_wait",
    "__ulock_wait2", "poll", "recv", "read", "GuestUSB.bulkOut", "GuestUSB.serviceMux",
    "GuestUSB.transfer", "GuestUSB.sendMux", "GuestUSB.readMux", "LogCapture",
)


def summarize(raw):
    # Never return an unknown symbol, stack line, address, argument or path.
    return {symbol: len(re.findall(r"(?<![A-Za-z0-9_])" + re.escape(symbol)
                                  + r"(?![A-Za-z0-9_])", raw)) for symbol in SYMBOLS}


def sample(pid, output, index):
    with tempfile.TemporaryDirectory(prefix="inferno-host-sample-") as temporary:
        raw = pathlib.Path(temporary) / "host.txt"
        try:
            result = subprocess.run(["/usr/bin/sample", str(pid), "2", "10", "-file", str(raw)],
                                    capture_output=True, timeout=30)
            report = {"sample_exit": result.returncode, "known_stack_symbols": {}}
            if result.returncode == 0 and raw.exists():
                report["known_stack_symbols"] = summarize(raw.read_text(errors="replace"))
        except (OSError, subprocess.TimeoutExpired):
            report = {"sample_unavailable": True, "known_stack_symbols": {}}
    report.update(format=1, elapsed_unix_seconds=int(time.time()),
                  guest_memory_exported=False, raw_stack_exported=False)
    output.mkdir(parents=True, exist_ok=True)
    (output / ("host-stall-%d.json" % index)).write_text(json.dumps(report, indent=2))
    # Make this bounded result visible in the running Actions step, rather
    # than waiting hours for its final artifact upload. Never print raw text.
    print("Host stall diagnostic: " + json.dumps(report, sort_keys=True), flush=True)


def watch(pid, output):
    started = time.time()
    last_sample = 0
    captures = 0
    while captures < 3:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        try:
            live = output / "smoke-live.json"
            snapshot = json.loads(live.read_text())
            age = time.time() - live.stat().st_mtime
            stalled = age >= 600 or snapshot.get("last_progress_age_seconds", 0) >= 600
        except (OSError, ValueError):
            stalled = time.time() - started >= 600
        if stalled and time.time() - last_sample >= 600:
            captures += 1
            sample(pid, output, captures)
            last_sample = time.time()
        time.sleep(15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    if args.pid <= 1:
        parser.error("An explicit test app PID is required")
    watch(args.pid, args.output)
