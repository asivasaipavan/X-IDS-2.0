from django.db import models
from django.conf import settings

class NetworkEvent(models.Model):
    SEVERITIES = [("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low"), ("info", "Info")]
    SOURCES = [("live", "Live capture"), ("pcap", "PCAP analysis"), ("csv", "CSV analysis")]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name="network_events"
)
    src_ip = models.GenericIPAddressField(protocol="both", db_index=True)
    dst_ip = models.GenericIPAddressField(protocol="both", db_index=True)
    src_port = models.PositiveIntegerField(default=0)
    dst_port = models.PositiveIntegerField(default=0)
    protocol = models.CharField(max_length=16, default="OTHER", db_index=True)
    packets = models.PositiveIntegerField(default=0)
    bytes_count = models.PositiveBigIntegerField(default=0)
    prediction = models.CharField(max_length=80, default="UNSCORABLE", db_index=True)
    confidence = models.FloatField(default=0)
    anomaly_flag = models.BooleanField(default=False, db_index=True)
    anomaly_score = models.FloatField(default=0)
    severity = models.CharField(max_length=16, choices=SEVERITIES, default="info", db_index=True)
    source = models.CharField(max_length=12, choices=SOURCES, default="live")
    model_details = models.JSONField(default=dict, blank=True)
    feature_vector = models.JSONField(default=dict, blank=True)
    explanation = models.JSONField(default=dict, blank=True)
    geo = models.JSONField(default=dict, blank=True)
    acknowledged = models.BooleanField(default=False, db_index=True)
    blocked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["-timestamp", "severity"])]

    @property
    def is_attack(self):
        return self.anomaly_flag or self.prediction.lower() not in {"normal", "benign", "unscorable", "pending"}


class SystemConfig(models.Model):
    """Single-row local response configuration. Automatic blocking is off by default."""
    auto_block_enabled = models.BooleanField(default=False)
    detection_threshold = models.FloatField(default=0.85)
    email_alerts_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class FirewallRule(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    inbound_rule = models.CharField(max_length=120, blank=True)
    outbound_rule = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
