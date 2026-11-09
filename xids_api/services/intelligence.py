import ipaddress
import os
import requests
from django.conf import settings


def reputation_lookup(value):
    ip = ipaddress.ip_address(value)
    if not ip.is_global:
        return {"ip": str(ip), "available": False, "message": "Private, loopback or reserved IPs are not queried against public reputation services."}
    key = getattr(settings, "ABUSEIPDB_API_KEY", "")
    if not key:
        return {"ip": str(ip), "available": False, "message": "Configure ABUSEIPDB_API_KEY in the backend .env file to enable reputation lookups."}
    response = requests.get(
        "https://api.abuseipdb.com/api/v2/check",
        headers={"Accept": "application/json", "Key": key},
        params={"ipAddress": str(ip), "maxAgeInDays": 90, "verbose": ""}, timeout=12,
    )
    response.raise_for_status()
    data = response.json().get("data", {})
    return {
        "ip": str(ip), "available": True, "abuse_confidence_score": data.get("abuseConfidenceScore"),
        "total_reports": data.get("totalReports"), "country_code": data.get("countryCode"),
        "isp": data.get("isp"), "domain": data.get("domain"), "is_tor": data.get("isTor"),
        "last_reported_at": data.get("lastReportedAt"), "usage_type": data.get("usageType"),
    }


def geo_lookup(value):
    ip = ipaddress.ip_address(value)
    if not ip.is_global:
        return {"ip": str(ip), "available": False, "message": "Private/local IP address; public GeoIP location is not applicable."}
    db_path = getattr(settings, "GEOIP_DB_PATH", "")
    if not db_path or not os.path.isfile(db_path):
        return {"ip": str(ip), "available": False, "message": "Add a MaxMind GeoLite2-City.mmdb database and set GEOIP_DB_PATH in .env."}
    import geoip2.database
    with geoip2.database.Reader(db_path) as reader:
        response = reader.city(str(ip))
        return {
            "ip": str(ip), "available": True,
            "country": response.country.name, "country_code": response.country.iso_code,
            "city": response.city.name, "region": response.subdivisions.most_specific.name,
            "latitude": response.location.latitude, "longitude": response.location.longitude,
            "timezone": response.location.time_zone,
        }
