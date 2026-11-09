import threading
import time
from collections import Counter
from datetime import datetime, timezone

from django.db import close_old_connections

from .flow_engine import FlowAggregator
from .events import process_flow


class MonitorManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.thread = None
        self.stop_event = threading.Event()
        self.running = False
        self.interface = None
        self.started_at = None
        self.started_monotonic = None
        self.error = None
        self.packets_seen = 0
        self.bytes_seen = 0
        self.protocols = Counter()
        self._last_packet_at = None

    def interfaces(self):
        from scapy.all import get_if_list, get_if_addr
        result = []
        for name in get_if_list():
            try:
                address = get_if_addr(name)
            except Exception:
                address = ""
            result.append({"name": str(name), "ipv4": address})
        return result

    def start(self, interface=None):
        from scapy.all import get_if_list
        available = get_if_list()
        if interface and interface not in available:
            raise ValueError(f"Interface '{interface}' was not found. Refresh the interface list.")
        with self.lock:
            if self.running:
                return self.status()
            self.stop_event.clear()
            self.interface = interface or None
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.started_monotonic = time.monotonic()
            self.error = None
            self.packets_seen = 0
            self.bytes_seen = 0
            self.protocols = Counter()
            self.running = True
            self.thread = threading.Thread(target=self._run, name="xids-packet-capture", daemon=True)
            self.thread.start()
            return self.status()

    def stop(self):
        self.stop_event.set()
        thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=6)
        with self.lock:
            self.running = False
        return self.status()

    
    def _run(self):
        from scapy.all import sniff

        aggregator = FlowAggregator(idle_timeout=2.5)

        try:
            capture_interface = self.interface

            # Convert Windows GUID into the Npcap device path
            if capture_interface and not capture_interface.startswith(r"\Device\NPF_"):
                capture_interface = r"\Device\NPF_" + capture_interface

            while not self.stop_event.is_set():
                sniff(
                    iface=capture_interface,
                    prn=lambda pkt: self._on_packet(pkt, aggregator),
                    store=False,
                    timeout=1,
                    promisc=True
                )

                for flow in aggregator.flush_expired():
                    process_flow(flow, source="live")

            for flow in aggregator.flush_expired(force=True):
                process_flow(flow, source="live")

        except Exception as exc:
            with self.lock:
                self.error = str(exc)

        finally:
            with self.lock:
                self.running = False
            close_old_connections()

    def _on_packet(self, packet, aggregator):
        with self.lock:
            self.packets_seen += 1
            self.bytes_seen += int(len(packet))
            self._last_packet_at = time.time()
            if packet.haslayer("TCP"):
                self.protocols["TCP"] += 1
            elif packet.haslayer("UDP"):
                self.protocols["UDP"] += 1
            elif packet.haslayer("ICMP"):
                self.protocols["ICMP"] += 1
            else:
                self.protocols["OTHER"] += 1
        aggregator.add_packet(packet)

    def status(self):
        with self.lock:
            elapsed = max(1.0, time.monotonic() - self.started_monotonic) if self.started_monotonic else 0.0
            return {
                "running": self.running, "interface": self.interface, "started_at": self.started_at,
                "packets_seen": self.packets_seen, "bytes_seen": self.bytes_seen,
                "packets_per_second": round(self.packets_seen / elapsed, 2) if elapsed else 0.0,
                "bytes_per_second": round(self.bytes_seen / elapsed, 2) if elapsed else 0.0,
                "uptime_seconds": int(elapsed), "protocols": dict(self.protocols), "last_packet_at": self._last_packet_at,
                "error": self.error,
            }


monitor = MonitorManager()
