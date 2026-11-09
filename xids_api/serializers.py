from rest_framework import serializers
from .models import NetworkEvent, FirewallRule


class NetworkEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkEvent
        fields = "__all__"


class FirewallRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirewallRule
        fields = "__all__"


class NetworkEventListSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkEvent
        fields = ["id", "timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "protocol",
                  "packets", "bytes_count", "prediction", "confidence", "anomaly_flag", "anomaly_score",
                  "severity", "source", "acknowledged", "blocked"]
