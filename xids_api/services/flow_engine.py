"""Lightweight bidirectional flow aggregation for live packets and PCAP files.

This maps observed packet statistics to the feature names stored with the
provided CIC-IDS2017 model. It is intentionally transparent: features that
cannot be reconstructed from ordinary packet headers are zero-filled. For
research-grade parity, replace this adapter with CICFlowMeter/NFStream output
and validate the feature distributions before trusting live predictions.
"""
from collections import defaultdict
from dataclasses import dataclass, field
import math
import time

from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.inet6 import IPv6


FEATURE_NAMES = [
    "DestinationPort", "TotalFwdPackets", "TotalBackwardPackets", "TotalLengthofFwdPackets",
    "TotalLengthofBwdPackets", "FwdPacketLengthMax", "FwdPacketLengthMin", "FwdPacketLengthMean",
    "FwdPacketLengthStd", "BwdPacketLengthMax", "BwdPacketLengthMin", "BwdPacketLengthMean",
    "BwdPacketLengthStd", "FlowPackets/s", "FlowIATMean", "FlowIATStd", "FlowIATMax", "FlowIATMin",
    "FwdIATTotal", "FwdIATMean", "FwdIATStd", "FwdIATMax", "FwdIATMin", "BwdIATTotal",
    "BwdIATMean", "BwdIATStd", "BwdIATMax", "BwdIATMin", "FwdPSHFlags", "BwdPSHFlags",
    "FwdURGFlags", "BwdURGFlags", "FwdHeaderLength", "BwdHeaderLength", "FwdPackets/s", "BwdPackets/s",
    "MinPacketLength", "MaxPacketLength", "PacketLengthMean", "PacketLengthStd", "PacketLengthVariance",
    "FINFlagCount", "SYNFlagCount", "RSTFlagCount", "PSHFlagCount", "ACKFlagCount", "URGFlagCount",
    "CWEFlagCount", "ECEFlagCount", "Down/UpRatio", "AveragePacketSize", "AvgFwdSegmentSize",
    "AvgBwdSegmentSize", "FwdHeaderLength1", "FwdAvgBytes/Bulk", "FwdAvgPackets/Bulk", "FwdAvgBulkRate",
    "BwdAvgBytes/Bulk", "BwdAvgPackets/Bulk", "BwdAvgBulkRate", "SubflowFwdPackets", "SubflowFwdBytes",
    "SubflowBwdPackets", "SubflowBwdBytes", "Init_Win_bytes_forward", "Init_Win_bytes_backward",
    "act_data_pkt_fwd", "min_seg_size_forward", "ActiveMean", "ActiveStd", "ActiveMax", "ActiveMin",
    "IdleMean", "IdleStd", "IdleMax", "IdleMin",
]


def _stats(values):
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    return float(max(values)), float(min(values)), float(sum(values) / len(values)), float(_std(values))


def _std(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _iat_stats(times):
    intervals = [max(0.0, (b - a) * 1_000_000) for a, b in zip(times, times[1:])]
    if not intervals:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    return (float(sum(intervals)), float(sum(intervals) / len(intervals)), float(_std(intervals)),
            float(max(intervals)), float(min(intervals)))


@dataclass
class Flow:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    first_seen: float
    last_seen: float
    packets: int = 0
    bytes_count: int = 0
    fwd_lengths: list = field(default_factory=list)
    bwd_lengths: list = field(default_factory=list)
    fwd_times: list = field(default_factory=list)
    bwd_times: list = field(default_factory=list)
    all_times: list = field(default_factory=list)
    fwd_headers: list = field(default_factory=list)
    bwd_headers: list = field(default_factory=list)
    tcp_flags: list = field(default_factory=list)
    fwd_tcp_flags: list = field(default_factory=list)
    bwd_tcp_flags: list = field(default_factory=list)
    fwd_windows: list = field(default_factory=list)
    bwd_windows: list = field(default_factory=list)
    min_seg: list = field(default_factory=list)

    def add(self, packet, src_ip, dst_ip, src_port, dst_port, protocol, timestamp):
        forward = (src_ip, src_port) == (self.src_ip, self.src_port)
        ip_layer = packet[IP] if packet.haslayer(IP) else packet[IPv6]
        if packet.haslayer(IP) and getattr(ip_layer, "len", None):
            length = int(ip_layer.len)
        elif packet.haslayer(IPv6) and getattr(ip_layer, "plen", None) is not None:
            length = int(ip_layer.plen) + 40
        else:
            length = int(len(packet))
        header_len = int(getattr(ip_layer, "ihl", 5) or 5) * 4 if packet.haslayer(IP) else 40
        payload_len = max(0, length - header_len)
        self.packets += 1
        self.bytes_count += length
        self.last_seen = timestamp
        self.all_times.append(timestamp)
        if forward:
            self.fwd_lengths.append(length)
            self.fwd_times.append(timestamp)
            self.fwd_headers.append(header_len)
        else:
            self.bwd_lengths.append(length)
            self.bwd_times.append(timestamp)
            self.bwd_headers.append(header_len)
        if packet.haslayer(TCP):
            tcp = packet[TCP]
            flags = str(tcp.flags)
            self.tcp_flags.append(flags)
            (self.fwd_tcp_flags if forward else self.bwd_tcp_flags).append(flags)
            win = int(tcp.window)
            (self.fwd_windows if forward else self.bwd_windows).append(win)
            self.min_seg.append(int(tcp.dataofs or 5) * 4)
        elif packet.haslayer(UDP):
            self.min_seg.append(8)

    def feature_map(self):
        fmax, fmin, fmean, fstd = _stats(self.fwd_lengths)
        bmax, bmin, bmean, bstd = _stats(self.bwd_lengths)
        # Avoid an artificial million-packet/second rate for single-packet flows.
        total_duration = max(0.001, self.last_seen - self.first_seen)
        fp, bp = len(self.fwd_lengths), len(self.bwd_lengths)
        f_iat = _iat_stats(self.fwd_times)
        b_iat = _iat_stats(self.bwd_times)
        all_iat = _iat_stats(self.all_times)
        all_lengths = self.fwd_lengths + self.bwd_lengths
        _, _, packet_mean, packet_std = _stats(all_lengths)
        flags = self.tcp_flags
        count_flag = lambda flag: sum(1 for f in flags if flag in f)
        count_flag_fwd = lambda flag: sum(1 for f in self.fwd_tcp_flags if flag in f)
        count_flag_bwd = lambda flag: sum(1 for f in self.bwd_tcp_flags if flag in f)
        active_gaps = [((b - a) * 1_000_000) for a, b in zip(self.all_times, self.all_times[1:]) if (b-a) <= 1.0]
        idle_gaps = [((b - a) * 1_000_000) for a, b in zip(self.all_times, self.all_times[1:]) if (b-a) > 1.0]
        def avg(v): return float(sum(v) / len(v)) if v else 0.0
        def std(v): return float(_std(v)) if v else 0.0
        feature = {name: 0.0 for name in FEATURE_NAMES}
        feature.update({
            "DestinationPort": float(self.dst_port),
            "TotalFwdPackets": float(fp), "TotalBackwardPackets": float(bp),
            "TotalLengthofFwdPackets": float(sum(self.fwd_lengths)), "TotalLengthofBwdPackets": float(sum(self.bwd_lengths)),
            "FwdPacketLengthMax": fmax, "FwdPacketLengthMin": fmin, "FwdPacketLengthMean": fmean, "FwdPacketLengthStd": fstd,
            "BwdPacketLengthMax": bmax, "BwdPacketLengthMin": bmin, "BwdPacketLengthMean": bmean, "BwdPacketLengthStd": bstd,
            "FlowPackets/s": float(self.packets / total_duration), "FlowIATMean": all_iat[1], "FlowIATStd": all_iat[2],
            "FlowIATMax": all_iat[3], "FlowIATMin": all_iat[4],
            "FwdIATTotal": f_iat[0], "FwdIATMean": f_iat[1], "FwdIATStd": f_iat[2], "FwdIATMax": f_iat[3],
            "FwdIATMin": f_iat[4], "BwdIATTotal": b_iat[0], "BwdIATMean": b_iat[1], "BwdIATStd": b_iat[2],
            "BwdIATMax": b_iat[3], "BwdIATMin": b_iat[4],
            "FwdPSHFlags": float(count_flag_fwd("P")), "BwdPSHFlags": float(count_flag_bwd("P")),
            "FwdURGFlags": float(count_flag_fwd("U")), "BwdURGFlags": float(count_flag_bwd("U")),
            "FwdHeaderLength": float(sum(self.fwd_headers)), "BwdHeaderLength": float(sum(self.bwd_headers)),
            "FwdPackets/s": float(fp / total_duration), "BwdPackets/s": float(bp / total_duration),
            "MinPacketLength": float(min(all_lengths)) if all_lengths else 0.0,
            "MaxPacketLength": float(max(all_lengths)) if all_lengths else 0.0,
            "PacketLengthMean": packet_mean, "PacketLengthStd": packet_std, "PacketLengthVariance": packet_std ** 2,
            "FINFlagCount": float(count_flag("F")), "SYNFlagCount": float(count_flag("S")), "RSTFlagCount": float(count_flag("R")),
            "PSHFlagCount": float(count_flag("P")), "ACKFlagCount": float(count_flag("A")), "URGFlagCount": float(count_flag("U")),
            "CWEFlagCount": float(count_flag("C")), "ECEFlagCount": float(count_flag("E")),
            "Down/UpRatio": float(bp / max(1, fp)), "AveragePacketSize": float(avg(all_lengths)),
            "AvgFwdSegmentSize": fmean, "AvgBwdSegmentSize": bmean,
            "FwdHeaderLength1": float(sum(self.fwd_headers)),
            "SubflowFwdPackets": float(fp), "SubflowFwdBytes": float(sum(self.fwd_lengths)),
            "SubflowBwdPackets": float(bp), "SubflowBwdBytes": float(sum(self.bwd_lengths)),
            "Init_Win_bytes_forward": float(self.fwd_windows[0]) if self.fwd_windows else 0.0,
            "Init_Win_bytes_backward": float(self.bwd_windows[0]) if self.bwd_windows else 0.0,
            "act_data_pkt_fwd": float(sum(1 for p in self.fwd_lengths if p > 0)),
            "min_seg_size_forward": float(min(self.min_seg)) if self.min_seg else 0.0,
            "ActiveMean": avg(active_gaps), "ActiveStd": std(active_gaps), "ActiveMax": max(active_gaps) if active_gaps else 0.0,
            "ActiveMin": min(active_gaps) if active_gaps else 0.0,
            "IdleMean": avg(idle_gaps), "IdleStd": std(idle_gaps), "IdleMax": max(idle_gaps) if idle_gaps else 0.0,
            "IdleMin": min(idle_gaps) if idle_gaps else 0.0,
        })
        return {k: float(v) if math.isfinite(float(v)) else 0.0 for k, v in feature.items()}

    def as_dict(self):
        return {
            "src_ip": self.src_ip, "dst_ip": self.dst_ip, "src_port": self.src_port, "dst_port": self.dst_port,
            "protocol": self.protocol, "packets": self.packets, "bytes_count": self.bytes_count,
            "feature_vector": self.feature_map(),
        }


class FlowAggregator:
    def __init__(self, idle_timeout=3.0, max_flows=10000):
        self.idle_timeout = idle_timeout
        self.max_flows = max_flows
        self.flows = {}

    @staticmethod
    def parse_packet(packet):
        if packet.haslayer(IP):
            ip = packet[IP]
            src, dst = ip.src, ip.dst
        elif packet.haslayer(IPv6):
            ip = packet[IPv6]
            src, dst = ip.src, ip.dst
        else:
            return None
        if packet.haslayer(TCP):
            layer, proto = packet[TCP], "TCP"
        elif packet.haslayer(UDP):
            layer, proto = packet[UDP], "UDP"
        else:
            return None
        return src, dst, int(layer.sport), int(layer.dport), proto

    def add_packet(self, packet):
        parsed = self.parse_packet(packet)
        if not parsed:
            return
        src, dst, sport, dport, proto = parsed
        timestamp = float(getattr(packet, "time", time.time()))
        endpoints = sorted([(src, sport), (dst, dport)])
        key = (endpoints[0], endpoints[1], proto)
        flow = self.flows.get(key)
        if flow is None:
            flow = Flow(src, dst, sport, dport, proto, timestamp, timestamp)
            self.flows[key] = flow
        flow.add(packet, src, dst, sport, dport, proto, timestamp)
        if len(self.flows) > self.max_flows:
            oldest_key = min(self.flows, key=lambda k: self.flows[k].last_seen)
            self.flows.pop(oldest_key, None)

    def flush_expired(self, now=None, force=False):
        now = now or time.time()
        expired = [k for k, f in self.flows.items() if force or (now - f.last_seen) >= self.idle_timeout]
        output = []
        for key in expired:
            flow = self.flows.pop(key)
            if flow.packets:
                output.append(flow.as_dict())
        return output
