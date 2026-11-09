from django.conf import settings
from django.core.mail import send_mail


def send_attack_email(event):
    if not getattr(settings, "XIDS_EMAIL_ENABLED", False):
        return False, "Email alerts are disabled. Configure SMTP and XIDS_EMAIL_ENABLED=true in .env."
    recipient = getattr(settings, "XIDS_ALERT_RECIPIENT", "")
    if not recipient:
        return False, "Set XIDS_ALERT_RECIPIENT in .env."
    subject = f"[X-IDS] {event.severity.upper()} threat detected: {event.prediction}"
    body = (
        f"X-IDS detected a potentially malicious network flow.\n\n"
        f"Time: {event.timestamp}\nPrediction: {event.prediction}\nConfidence: {event.confidence:.1%}\n"
        f"Severity: {event.severity}\nSource: {event.src_ip}:{event.src_port}\n"
        f"Destination: {event.dst_ip}:{event.dst_port}\nProtocol: {event.protocol}\n"
        f"Packets: {event.packets}\nBytes: {event.bytes_count}\n\n"
        "This is an automated detection and should be reviewed before taking action."
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
    return True, f"Alert email sent to {recipient}."
