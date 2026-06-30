import os
import tempfile
from datetime import datetime
from typing import Dict, Any, List
from database import get_settings, next_invoice_number


class ReportGenerator:

    def build_text_report(self, client_name: str, date_label: str, data: Dict[str, Any]) -> str:
        s = data["summary"]
        campaigns = data["campaigns"]
        settings = get_settings()
        generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

        lines = [
            f"<b>{settings['agency_name']} — Ads Report</b>",
            f"<b>Client:</b> {client_name}",
            f"<b>Period:</b> {date_label}",
            f"<b>Generated:</b> {generated_at}",
            "",
            "<b>━━━ SUMMARY ━━━</b>",
            f"💸 Total Spend:      <b>{s['total_spend']:,.2f} BDT</b>",
            f"👁 Impressions:      {s['total_impressions']:,}",
            f"🎯 Reach:            {s['total_reach']:,}",
            f"🖱 Clicks:           {s['total_clicks']:,}",
            f"📊 Avg CTR:          {s['avg_ctr']:.2f}%",
            f"💰 Avg CPC:          {s['avg_cpc']:.2f} BDT",
        ]
        if s["total_conversions"] > 0:
            lines += [
                f"✅ Conversions:      {s['total_conversions']:,}",
                f"💵 Revenue:          {s['total_revenue']:,.2f} BDT",
                f"📈 ROAS:             {s['roas']:.2f}x",
                f"🎯 Cost/Conv:        {s['cost_per_conversion']:.2f} BDT",
            ]
        lines += [f"📋 Campaigns:        {s['campaign_count']}", ""]

        if campaigns:
            lines.append("<b>━━━ CAMPAIGN BREAKDOWN ━━━</b>")
            for i, c in enumerate(campaigns[:10], 1):
                name = c.get("campaign_name", f"Campaign {i}")
                spend = float(c.get("spend", 0))
                impressions = int(c.get("impressions", 0))
                clicks = int(c.get("clicks", 0))
                ctr = float(c.get("ctr", 0))
                cpc = float(c.get("cpc", 0))
                lines.append(
                    f"\n<b>{i}. {name[:35]}</b>\n"
                    f"   💸 {spend:,.2f} | 👁 {impressions:,} | "
                    f"🖱 {clicks:,} | CTR {ctr:.2f}% | CPC {cpc:.2f}"
                )
            if len(campaigns) > 10:
                lines.append(f"\n...আরও {len(campaigns) - 10}টা campaign (PDF এ দেখুন)")

        lines.append(f"\n<i>{settings['agency_name']}</i>")
        return "\n".join(lines)

    def build_geo_text(self, client_name: str, date_label: str, geo_data: List[dict]) -> str:
        settings = get_settings()
        lines = [
            f"<b>{settings['agency_name']} — GEO Report</b>",
            f"<b>Client:</b> {client_name}",
            f"<b>Period:</b> {date_label}", "",
            "<b>━━━ COUNTRY BREAKDOWN ━━━</b>",
        ]
        sorted_geo = sorted(geo_data, key=lambda x: float(x.get("spend", 0)), reverse=True)
        for i, g in enumerate(sorted_geo[:15], 1):
            country = g.get("country", "Unknown")
            spend = float(g.get("spend", 0))
            impressions = int(g.get("impressions", 0))
            clicks = int(g.get("clicks", 0))
            lines.append(f"{i}. 🌍 <b>{country}</b> — {spend:,.2f} BDT | {impressions:,} imp | {clicks:,} clicks")
        return "\n".join(lines)

    def build_pdf_report(self, client_name: str, date_label: str, data: Dict[str, Any]) -> str:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        settings = get_settings()
        s = data["summary"]
        campaigns = data["campaigns"]
        generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        doc = SimpleDocTemplate(tmp_path, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        brand = colors.HexColor("#1877F2")
        dark = colors.HexColor("#1C1E21")
        muted = colors.HexColor("#65676B")
        light_bg = colors.HexColor("#F0F2F5")

        story = []
        story.append(Paragraph(f"{settings['agency_name']} — Ads Performance Report",
                               ParagraphStyle("T", parent=styles["Title"], fontSize=18,
                                              textColor=brand, spaceAfter=4)))
        story.append(Paragraph(f"Client: {client_name} | Period: {date_label} | {generated_at}",
                               ParagraphStyle("S", parent=styles["Normal"], fontSize=9,
                                              textColor=muted, spaceAfter=12)))
        story.append(Spacer(1, 0.3*cm))

        summary_data = [["Metric", "Value"],
                        ["Total Spend", f"{s['total_spend']:,.2f} BDT"],
                        ["Impressions", f"{s['total_impressions']:,}"],
                        ["Reach", f"{s['total_reach']:,}"],
                        ["Clicks", f"{s['total_clicks']:,}"],
                        ["Avg CTR", f"{s['avg_ctr']:.2f}%"],
                        ["Avg CPC", f"{s['avg_cpc']:.2f} BDT"],
                        ["Active Campaigns", str(s["campaign_count"])]]
        if s["total_conversions"] > 0:
            summary_data += [
                ["Conversions", f"{s['total_conversions']:,}"],
                ["Revenue", f"{s['total_revenue']:,.2f} BDT"],
                ["ROAS", f"{s['roas']:.2f}x"],
                ["Cost/Conversion", f"{s['cost_per_conversion']:.2f} BDT"],
            ]

        t = Table(summary_data, colWidths=[8*cm, 8*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADDE1")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        if campaigns:
            story.append(Paragraph("Campaign Breakdown",
                                   ParagraphStyle("H", parent=styles["Heading2"],
                                                  fontSize=13, textColor=brand, spaceAfter=6)))
            camp_data = [["Campaign", "Spend", "Imp", "Clicks", "CTR", "CPC"]]
            for c in campaigns:
                name = c.get("campaign_name", "Unknown")
                if len(name) > 30:
                    name = name[:28] + "..."
                camp_data.append([name,
                                   f"{float(c.get('spend', 0)):,.0f}",
                                   f"{int(c.get('impressions', 0)):,}",
                                   f"{int(c.get('clicks', 0)):,}",
                                   f"{float(c.get('ctr', 0)):.2f}%",
                                   f"{float(c.get('cpc', 0)):.2f}"])
            ct = Table(camp_data, colWidths=[6.5*cm, 2*cm, 2.5*cm, 2*cm, 2*cm, 2*cm])
            ct.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), brand),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADDE1")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]))
            story.append(ct)

        story.append(Spacer(1, 0.6*cm))
        story.append(Paragraph(f"Generated by {settings['agency_name']} Bot",
                               ParagraphStyle("F", parent=styles["Normal"],
                                              fontSize=8, textColor=muted)))
        doc.build(story)
        return tmp_path

    def build_invoice_pdf(self, client_name: str, items: List[dict],
                          ad_spend: float, service_charge: float) -> str:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

        settings = get_settings()
        inv_number = next_invoice_number()
        inv_date = datetime.now().strftime("%d %b %Y")
        total = ad_spend + service_charge

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        doc = SimpleDocTemplate(tmp_path, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        brand = colors.HexColor("#1877F2")
        dark = colors.HexColor("#1C1E21")
        muted = colors.HexColor("#65676B")

        story = []

        # Header
        story.append(Paragraph(settings["agency_name"],
                               ParagraphStyle("AgName", parent=styles["Title"],
                                              fontSize=24, textColor=brand)))
        story.append(Paragraph("Digital Marketing Agency",
                               ParagraphStyle("AgSub", parent=styles["Normal"],
                                              fontSize=11, textColor=muted, spaceAfter=4)))
        if settings.get("agency_phone"):
            story.append(Paragraph(f"📞 {settings['agency_phone']}",
                                   ParagraphStyle("Ph", parent=styles["Normal"],
                                                  fontSize=10, textColor=dark)))
        story.append(HRFlowable(width="100%", thickness=2, color=brand, spaceAfter=12))

        # Invoice info
        info_data = [
            ["INVOICE", inv_number],
            ["Date", inv_date],
            ["Bill To", client_name],
        ]
        info_t = Table(info_data, colWidths=[4*cm, 12*cm])
        info_t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), muted),
            ("TEXTCOLOR", (1, 0), (1, 0), brand),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (1, 0), (1, 0), 14),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(info_t)
        story.append(Spacer(1, 0.5*cm))

        # Items
        item_data = [["Description", "Amount (BDT)"]]
        item_data.append(["Ad Spend (Meta)", f"{ad_spend:,.2f}"])
        item_data.append(["Service Charge", f"{service_charge:,.2f}"])
        for item in items:
            item_data.append([item.get("desc", ""), f"{item.get('amount', 0):,.2f}"])
        item_data.append(["", ""])
        item_data.append(["TOTAL", f"{total:,.2f} BDT"])

        it = Table(item_data, colWidths=[12*cm, 4*cm])
        it.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#DADDE1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -3), [colors.white, colors.HexColor("#F0F2F5")]),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 12),
            ("TEXTCOLOR", (0, -1), (-1, -1), brand),
            ("LINEABOVE", (0, -1), (-1, -1), 2, brand),
        ]))
        story.append(it)
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph("ধন্যবাদ আমাদের সাথে থাকার জন্য! 🙏",
                               ParagraphStyle("TY", parent=styles["Normal"],
                                              fontSize=11, textColor=muted)))
        doc.build(story)
        return tmp_path
