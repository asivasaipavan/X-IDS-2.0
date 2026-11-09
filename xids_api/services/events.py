from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import close_old_connections
from django.utils import timezone
from xids_api.models import NetworkEvent, SystemConfig
from .inference import engine
from .notifications import send_attack_email
from .response import block_ip


def _severity(prediction, confidence, scorable, anomaly_flag=False):
    if not scorable:
        return "info"
    if anomaly_flag and prediction.lower() in {"normal", "benign"}:
        return "medium"
    if prediction.lower() in {"normal", "benign"}:
        return "low"
    if confidence >= 0.95:
        return "critical"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.70:
        return "medium"
    return "low"


def event_payload(event):
    return {
        "id": event.id, "timestamp": event.timestamp.isoformat(), "src_ip": event.src_ip,
        "dst_ip": event.dst_ip, "src_port": event.src_port, "dst_port": event.dst_port,
        "protocol": event.protocol, "packets": event.packets, "bytes_count": event.bytes_count,
        "prediction": event.prediction, "confidence": event.confidence, "anomaly_flag": event.anomaly_flag,
        "anomaly_score": event.anomaly_score, "severity": event.severity,
        "source": event.source, "acknowledged": event.acknowledged, "blocked": event.blocked,
    }


def process_flow(flow, source="live", user=None):
    close_old_connections()
    result = engine.predict(flow["feature_vector"])
    severity = _severity(result["prediction"], result["confidence"], result["scorable"], result.get("anomaly_flag", False))
    event = NetworkEvent.objects.create(
        user=user,
        src_ip=flow["src_ip"], dst_ip=flow["dst_ip"], src_port=int(flow["src_port"]),
        dst_port=int(flow["dst_port"]), protocol=flow["protocol"], packets=int(flow["packets"]),
        bytes_count=int(flow["bytes_count"]), prediction=result["prediction"], confidence=result["confidence"],
        anomaly_flag=result.get("anomaly_flag", False), anomaly_score=result.get("anomaly_score", 0.0),
        severity=severity, source=source, model_details=result["model_details"], feature_vector=flow["feature_vector"],
    )
    is_attack = result["scorable"] and (result["prediction"].lower() not in {"normal", "benign"} or result.get("anomaly_flag", False))
    model_attack = result["scorable"] and result["prediction"].lower() not in {"normal", "benign"}
    if is_attack:
        config = SystemConfig.current()
        if config.email_alerts_enabled:
            try:
                send_attack_email(event)
            except Exception as exc:
                event.model_details = {**event.model_details, "email_error": str(exc)}
                event.save(update_fields=["model_details"])
        if config.auto_block_enabled and model_attack and result["confidence"] >= config.detection_threshold:
            try:
                import ipaddress
                source_ip = ipaddress.ip_address(event.src_ip)
                remote_candidate = event.src_ip if source_ip.is_global else event.dst_ip
                rule, _ = block_ip(remote_candidate, note=f"Automatic block: event #{event.id}")
                event.blocked = True
                event.save(update_fields=["blocked"])
            except Exception as exc:
                event.model_details = {**event.model_details, "auto_block_error": str(exc)}
                event.save(update_fields=["model_details"])
    payload = event_payload(event)
    try:
        layer = get_channel_layer()
        if layer and source == "live":
            async_to_sync(layer.group_send)("live_events", {"type": "event.message", "payload": payload})
    except Exception:
        pass
    close_old_connections()
    return event
