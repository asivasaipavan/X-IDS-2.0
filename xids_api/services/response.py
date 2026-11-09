import ipaddress
import os
import re
import subprocess
from django.conf import settings
from xids_api.models import FirewallRule


def _validate_public_ip(value):
    ip = ipaddress.ip_address(value)
    if not ip.is_global:
        raise ValueError("For safety, X-IDS firewall actions are restricted to public/routable IPs. Local and private hosts cannot be blocked from this dashboard.")
    whitelist = {x.strip() for x in getattr(settings, "XIDS_IP_WHITELIST", "").split(",") if x.strip()}
    if str(ip) in whitelist:
        raise ValueError("This IP is on the X-IDS allowlist and cannot be blocked.")
    return str(ip)


def _rule_name(ip, direction):
    return "XIDS_" + direction + "_" + re.sub(r"[^A-Za-z0-9]", "_", ip)


def block_ip(value, note="Manual X-IDS block"):
    ip = _validate_public_ip(value)
    existing = FirewallRule.objects.filter(ip_address=ip).first()
    if existing and existing.active:
        return existing, "IP is already blocked by X-IDS."
    inbound, outbound = _rule_name(ip, "IN"), _rule_name(ip, "OUT")
    if os.name == "nt":
        commands = [
            ["netsh", "advfirewall", "firewall", "add", "rule", f"name={inbound}", "dir=in", "action=block", f"remoteip={ip}", "enable=yes"],
            ["netsh", "advfirewall", "firewall", "add", "rule", f"name={outbound}", "dir=out", "action=block", f"remoteip={ip}", "enable=yes"],
        ]
    else:
        commands = [["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"], ["iptables", "-I", "OUTPUT", "-d", ip, "-j", "DROP"]]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
    if existing:
        existing.inbound_rule = inbound
        existing.outbound_rule = outbound
        existing.active = True
        existing.note = note[:255]
        existing.save()
        rule = existing
    else:
        rule = FirewallRule.objects.create(ip_address=ip, inbound_rule=inbound, outbound_rule=outbound, active=True, note=note[:255])
    return rule, "Firewall rules added."


def unblock_ip(value):
    ip = _validate_public_ip(value)
    rule = FirewallRule.objects.filter(ip_address=ip, active=True).first()
    if not rule:
        raise ValueError("No active X-IDS firewall rule exists for this IP.")
    if os.name == "nt":
        commands = [
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule.inbound_rule}"],
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule.outbound_rule}"],
        ]
    else:
        commands = [["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"], ["iptables", "-D", "OUTPUT", "-d", ip, "-j", "DROP"]]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
    rule.active = False
    rule.save(update_fields=["active"])
    return rule
