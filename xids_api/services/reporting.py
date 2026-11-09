from io import BytesIO
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from xids_api.models import NetworkEvent


# def build_security_report():
def build_security_report(events_qs):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="XidsTitle", parent=styles["Title"], textColor=colors.HexColor("#0e7490"), alignment=0))
    story = [Paragraph("X-IDS Security Report", styles["XidsTitle"]),
             Paragraph(f"Generated {timezone.localtime().strftime('%d %b %Y, %I:%M %p')}", styles["Normal"]), Spacer(1, 8*mm)]
    # total = NetworkEvent.objects.count()
    # from django.db.models import Q
    # attacks = NetworkEvent.objects.filter(Q(anomaly_flag=True) | ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])).count()
    # critical = NetworkEvent.objects.filter(severity="critical").count()
    # acknowledged = NetworkEvent.objects.filter(acknowledged=True).count()
    from django.db.models import Q

    total = events_qs.count()

    attacks = events_qs.filter(
        Q(anomaly_flag=True) |
        ~Q(prediction__in=["Normal", "Benign", "UNSCORABLE", "Pending"])
    ).count()

    critical = events_qs.filter(severity="critical").count()

    acknowledged = events_qs.filter(acknowledged=True).count()
    data = [["Metric", "Value"], ["Observed flows", str(total)], ["Predicted attacks", str(attacks)], ["Critical events", str(critical)], ["Acknowledged events", str(acknowledged)]]
    table = Table(data, colWidths=[90*mm, 55*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f172a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#cbd5e1")), ("PAD", (0,0), (-1,-1), 7),
        ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#f8fafc")),
    ]))
    story += [Paragraph("Executive summary", styles["Heading2"]), table, Spacer(1, 8*mm), Paragraph("Recent detected flows", styles["Heading2"])]
    rows = [["Time", "Source", "Destination", "Protocol", "Prediction", "Confidence"]]
    # for e in NetworkEvent.objects.order_by("-timestamp")[:35]:
    for e in events_qs.order_by("-timestamp")[:35]:
        rows.append([e.timestamp.strftime("%d-%b %H:%M:%S"), f"{e.src_ip}:{e.src_port}", f"{e.dst_ip}:{e.dst_port}", e.protocol, e.prediction, f"{e.confidence:.1%}"])
    events_table = Table(rows, repeatRows=1, colWidths=[27*mm, 36*mm, 36*mm, 17*mm, 25*mm, 19*mm])
    events_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0f172a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 7), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(events_table)
    story += [Spacer(1, 6*mm), Paragraph("Note: IDS predictions are decision-support signals, not proof of compromise. Validate critical findings with packet captures and other security telemetry.", styles["Italic"])]
    doc.build(story)
    buffer.seek(0)
    return buffer
