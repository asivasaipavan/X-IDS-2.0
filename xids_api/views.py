import ipaddress
import os
import tempfile
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login as django_login, logout as django_logout, get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import NetworkEvent, SystemConfig, FirewallRule
from .serializers import NetworkEventSerializer, NetworkEventListSerializer, FirewallRuleSerializer
from .services.capture import monitor
from .services.events import process_flow
from .services.flow_engine import FlowAggregator
from .services.inference import engine
from .services.intelligence import reputation_lookup, geo_lookup
from .services.reporting import build_security_report
from .services.response import block_ip, unblock_ip

from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

def visible_events(user):
    return NetworkEvent.objects.filter(
        Q(source="live", user__isnull=True) |
        Q(user=user)
    )

@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"ok": True, "service": "xids-api", "time": timezone.now().isoformat()})


@api_view(["GET"])
def dashboard_summary(request):
    # cutoff = timezone.now() - timedelta(hours=24)
    # recent = NetworkEvent.objects.filter(timestamp__gte=cutoff)
    # total = NetworkEvent.objects.count()
    # attack_qs = NetworkEvent.objects.filter(Q(anomaly_flag=True) | ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"]))
    cutoff = timezone.now() - timedelta(hours=24)
    base_qs = visible_events(request.user)
    recent = base_qs.filter(timestamp__gte=cutoff)
    total = base_qs.count()
    attack_qs = base_qs.filter(
        Q(anomaly_flag=True) |
        ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])
    )
    severity_counts = {x["severity"]: x["count"] for x in recent.values("severity").annotate(count=Count("id"))}
    protocol_counts = {x["protocol"]: x["count"] for x in recent.values("protocol").annotate(count=Count("id"))}
    prediction_counts = {x["prediction"]: x["count"] for x in recent.values("prediction").annotate(count=Count("id"))}
    # previous = NetworkEvent.objects.filter(timestamp__gte=cutoff - timedelta(hours=24), timestamp__lt=cutoff).filter(Q(anomaly_flag=True) | ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])).count()
    previous = base_qs.filter(
    timestamp__gte=cutoff - timedelta(hours=24),
    timestamp__lt=cutoff
).filter(
    Q(anomaly_flag=True) |
    ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])
).count()
    current_attacks = attack_qs.filter(timestamp__gte=cutoff).count()
    total_packets = recent.aggregate(v=Sum("packets"))["v"] or 0
    total_bytes = recent.aggregate(v=Sum("bytes_count"))["v"] or 0
    hourly = []
    now = timezone.now()
    for offset in range(11, -1, -1):
        start = (now - timedelta(hours=offset)).replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        group = recent.filter(timestamp__gte=start, timestamp__lt=end)
        hourly.append({
            "time": start.strftime("%H:%M"), "flows": group.count(),
            "attacks": group.filter(Q(anomaly_flag=True) | ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])).count(),
        })
    model_status = engine.status()
    monitor_status = monitor.status()
    attack_delta = current_attacks - previous
    risk_trend = {"direction": "rising" if attack_delta > 0 else "falling" if attack_delta < 0 else "stable", "change": attack_delta, "current_24h": current_attacks, "previous_24h": previous}
    return Response({
        "total_flows": total, "flows_24h": recent.count(), "attacks_24h": attack_qs.filter(timestamp__gte=cutoff).count(),
        "critical_24h": severity_counts.get("critical", 0), "anomalies_24h": recent.filter(anomaly_flag=True).count(),
        "unacknowledged": recent.filter(acknowledged=False).filter(Q(anomaly_flag=True) | ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])).count(),
        "packets_24h": int(total_packets), "bytes_24h": int(total_bytes),
        "protocol_distribution": protocol_counts, "prediction_distribution": prediction_counts, "risk_trend": risk_trend,
        "severity_distribution": severity_counts, "traffic_series": hourly,
        "monitor": monitor_status, "models": model_status,
        "recent_events": NetworkEventListSerializer(base_qs[:8], many=True).data,
        # "recent_events": NetworkEventListSerializer(NetworkEvent.objects.all()[:8], many=True).data,
    })


@api_view(["GET"])
def events_list(request):
    # qs = NetworkEvent.objects.all()
    qs = visible_events(request.user)
    kind = request.GET.get("kind")
    severity = request.GET.get("severity")
    search = request.GET.get("q")
    if kind == "alerts":
        qs = qs.filter(Q(anomaly_flag=True) | ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"]))
    if severity:
        qs = qs.filter(severity=severity)
    if search:
        qs = qs.filter(src_ip__icontains=search) | qs.filter(dst_ip__icontains=search) | qs.filter(prediction__icontains=search)
    return Response(NetworkEventListSerializer(qs[:200], many=True).data)


@api_view(["GET"])
def event_detail(request, event_id):
    try:
        event = visible_events(request.user).get(pk=event_id)
    except NetworkEvent.DoesNotExist:
        return Response({"error": "Event not found."}, status=404)
    return Response(NetworkEventSerializer(event).data)


@api_view(["POST"])
def explain_event(request, event_id):
    try:
        event = visible_events(request.user).get(pk=event_id)
    except NetworkEvent.DoesNotExist:
        return Response({"error": "Event not found."}, status=404)
    if not event.feature_vector:
        return Response({"error": "This event does not contain a feature vector."}, status=400)
    try:
        explanation = engine.explain(event.feature_vector)
        event.explanation = explanation
        event.save(update_fields=["explanation"])
        return Response(explanation)
    except Exception as exc:
        return Response({"error": str(exc)}, status=503)


@api_view(["POST"])
def acknowledge_event(request, event_id):
    try:
        event = visible_events(request.user).get(pk=event_id)
    except NetworkEvent.DoesNotExist:
        return Response({"error": "Event not found."}, status=404)
    event.acknowledged = True
    event.save(update_fields=["acknowledged"])
    return Response({"ok": True, "event": NetworkEventSerializer(event).data})


@api_view(["GET"])
def monitor_status(request):
    return Response(monitor.status())


@api_view(["GET"])
def monitor_interfaces(request):
    try:
        return Response({"interfaces": monitor.interfaces()})
    except Exception as exc:
        return Response({"interfaces": [], "error": str(exc)}, status=503)


@api_view(["POST"])
def monitor_start(request):
    try:
        state = monitor.start(request.data.get("interface") or None)
        return Response(state)
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)


@api_view(["POST"])
def monitor_stop(request):
    return Response(monitor.stop())


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def pcap_analyze(request):
    upload = request.FILES.get("pcap_file")
    if not upload:
        return Response({"error": "Choose a .pcap or .pcapng file."}, status=400)
    if not upload.name.lower().endswith((".pcap", ".pcapng", ".cap")):
        return Response({"error": "Only PCAP/PCAPNG files are supported."}, status=400)
    if upload.size > 100 * 1024 * 1024:
        return Response({"error": "Maximum PCAP upload size is 100 MB."}, status=400)
    from scapy.utils import PcapReader
    aggregator = FlowAggregator(idle_timeout=0)
    count = 0
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(upload.name)[1],
            delete=False
        ) as temp:
            temp_path = temp.name
            for chunk in upload.chunks():
                temp.write(chunk)

        # File is now closed, so Scapy can open it on Windows
        with PcapReader(temp_path) as reader:
            for packet in reader:
                aggregator.add_packet(packet)
                count += 1
                if count >= 1_000_000:
                    break

        flows = aggregator.flush_expired(force=True)
        created = 0

        for flow in flows[:5000]:
            # process_flow(flow, source="pcap")
            process_flow(flow, source="pcap", user=request.user)
            created += 1

        return Response({
            "ok": True,
            "file": upload.name,
            "packets_read": count,
            "flows_extracted": len(flows),
            "events_created": created,
            "note": "Packet headers are converted to the saved model feature schema; fields not available from the capture are zero-filled."
        })

    except Exception as exc:
        return Response(
            {"error": f"PCAP analysis failed: {exc}"},
            status=400
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
    # try:
    #     with tempfile.NamedTemporaryFile(suffix=os.path.splitext(upload.name)[1], delete=True) as temp:
    #         for chunk in upload.chunks():
    #             temp.write(chunk)
    #         temp.flush()
    #         with PcapReader(temp.name) as reader:
    #             for packet in reader:
    #                 aggregator.add_packet(packet)
    #                 count += 1
    #                 if count > 1_000_000:
    #                     break
    #     flows = aggregator.flush_expired(force=True)
    #     created = 0
    #     for flow in flows[:5000]:
    #         process_flow(flow, source="pcap")
    #         created += 1
    #     return Response({"ok": True, "file": upload.name, "packets_read": count, "flows_extracted": len(flows), "events_created": created,
    #                      "note": "Packet headers are converted to the saved model feature schema; fields not available from the capture are zero-filled."})
    # except Exception as exc:
    #     return Response({"error": f"PCAP analysis failed: {exc}"}, status=400)


@api_view(["POST"])
def ip_reputation(request):
    value = str(request.data.get("ip", "")).strip()
    try:
        return Response(reputation_lookup(value))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    except Exception as exc:
        return Response({"error": f"Reputation lookup failed: {exc}"}, status=502)


@api_view(["GET", "POST"])
def ip_geo(request):
    value = str(request.data.get("ip", "") if request.method == "POST" else request.GET.get("ip", "")).strip()
    try:
        return Response(geo_lookup(value))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    except Exception as exc:
        return Response({"error": f"GeoIP lookup failed: {exc}"}, status=502)


@api_view(["GET"])
def topology(request):
    # qs = NetworkEvent.objects.order_by("-timestamp")[:500]
    qs = visible_events(request.user).order_by("-timestamp")[:500]
    nodes, edges = {}, {}
    for event in qs:
        for ip in (event.src_ip, event.dst_ip):
            if ip not in nodes:
                parsed = ipaddress.ip_address(ip)
                nodes[ip] = {"id": ip, "label": ip, "local": parsed.is_private or parsed.is_loopback, "events": 0}
            nodes[ip]["events"] += 1
        key = f"{event.src_ip}|{event.dst_ip}|{event.protocol}"
        if key not in edges:
            edges[key] = {"id": key, "source": event.src_ip, "target": event.dst_ip, "protocol": event.protocol, "flows": 0, "attacks": 0}
        edges[key]["flows"] += 1
        if event.anomaly_flag or event.prediction.lower() not in {"normal", "benign", "unscorable", "pending"}:
            edges[key]["attacks"] += 1
    return Response({"nodes": list(nodes.values())[:100], "edges": list(edges.values())[:200]})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def block(request):
    value = str(request.data.get("ip", "")).strip()
    try:
        rule, message = block_ip(value, note="Manual block from X-IDS dashboard")
        return Response({"ok": True, "message": message, "rule": FirewallRuleSerializer(rule).data})
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    except Exception as exc:
        return Response({"error": f"Firewall action failed. Run the backend with administrator privileges: {exc}"}, status=503)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def unblock(request):
    value = str(request.data.get("ip", "")).strip()
    try:
        rule = unblock_ip(value)
        return Response({"ok": True, "rule": FirewallRuleSerializer(rule).data})
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    except Exception as exc:
        return Response({"error": f"Firewall action failed: {exc}"}, status=503)


@api_view(["GET"])
def firewall_rules(request):
    return Response(FirewallRuleSerializer(FirewallRule.objects.all(), many=True).data)


@api_view(["GET"])
def report_pdf(request):
    try:
        # buffer = build_security_report()
        buffer = build_security_report(visible_events(request.user))
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="xids-security-report.pdf"'
        return response
    except Exception as exc:
        return Response({"error": f"Could not generate report: {exc}"}, status=500)


@api_view(["GET", "POST"])
def system_config(request):
    config = SystemConfig.current()
    if request.method == "POST":
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Administrator role required to change system policy."}, status=403)
        if "auto_block_enabled" in request.data:
            config.auto_block_enabled = bool(request.data["auto_block_enabled"])
        if "email_alerts_enabled" in request.data:
            config.email_alerts_enabled = bool(request.data["email_alerts_enabled"])
        if "detection_threshold" in request.data:
            threshold = float(request.data["detection_threshold"])
            if not 0.5 <= threshold <= 1:
                return Response({"error": "Detection threshold must be between 0.50 and 1.00."}, status=400)
            config.detection_threshold = threshold
        config.save()
    return Response({"auto_block_enabled": config.auto_block_enabled, "email_alerts_enabled": config.email_alerts_enabled,
                     "detection_threshold": config.detection_threshold,
                     "smtp_configured": bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER),
                     "abuseipdb_configured": bool(getattr(settings, "ABUSEIPDB_API_KEY", "")),
                     "geoip_configured": bool(getattr(settings, "GEOIP_DB_PATH", "") and os.path.isfile(getattr(settings, "GEOIP_DB_PATH", "")))})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def test_email(request):
    recipient = str(request.data.get("email", "")).strip()
    if "@" not in recipient:
        return Response({"error": "Enter a valid recipient email address."}, status=400)
    try:
        send_mail("X-IDS email test", "Your X-IDS SMTP configuration is working.", settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        return Response({"ok": True, "message": f"Test email sent to {recipient}."})
    except Exception as exc:
        return Response({"error": f"Email send failed: {exc}"}, status=503)


@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
@ensure_csrf_cookie
def auth_csrf(request):
    return Response({"ok": True})

@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def auth_register(request):
    User = get_user_model()

    full_name = str(request.data.get("full_name", "")).strip()
    username = str(request.data.get("username", "")).strip()
    email = str(request.data.get("email", "")).strip().lower()
    password = str(request.data.get("password", ""))
    confirm_password = str(request.data.get("confirm_password", ""))

    if not full_name or len(username) < 3 or not email:
        return Response({"error": "Name, username and email are required."}, status=400)

    if password != confirm_password:
        return Response({"error": "Passwords do not match."}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return Response({"error": "Username already exists."}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return Response({"error": "Email already registered."}, status=400)

    try:
        validate_password(password)
    except ValidationError as exc:
        return Response({"error": " ".join(exc.messages)}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=full_name,
        is_staff=False,
        is_superuser=False,
    )

    return Response({
        "ok": True,
        "message": "Account created successfully.",
        "username": user.username
    }, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def auth_login(request):
    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({"error": "Invalid username or password."}, status=400)

    django_login(request, user)

    return Response({
        "ok": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_staff or user.is_superuser
        }
    })

@api_view(["POST"])
def auth_logout(request):
    django_logout(request)
    return Response({"ok": True})


@api_view(["GET"])
def auth_me(request):
    user = request.user
    return Response({"id": user.id, "username": user.username, "email": user.email, "is_admin": user.is_staff or user.is_superuser})


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def user_management(request):
    User = get_user_model()
    if request.method == "POST":
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        email = str(request.data.get("email", "")).strip()
        role = str(request.data.get("role", "analyst"))
        if len(username) < 3 or len(password) < 10:
            return Response({"error": "Username must have at least 3 characters and password at least 10 characters."}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({"error": "That username already exists."}, status=400)
        created = User.objects.create_user(username=username, password=password, email=email, is_staff=(role == "admin"))
        return Response({"id": created.id, "username": created.username, "email": created.email, "is_admin": created.is_staff}, status=201)
    return Response([{"id": u.id, "username": u.username, "email": u.email, "is_admin": u.is_staff or u.is_superuser, "active": u.is_active}
                     for u in User.objects.all().order_by("username")])
