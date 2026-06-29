import os
import tempfile
from datetime import datetime
from typing import Dict, Any


class ReportGenerator:

    def build_text_report(
        self,
        client_name: str,
        date_label: str,
        data: Dict[str, Any],
    ) -> str:
        s = data["summary"]
        campaigns = data["campaigns"]
        generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

        lines = [
            f"<b>SKF Boosting — Ads Report</b>",
            f"<b>Client:</b> {client_name}",
            f"<b>Period:</b> {date_label}",
            f"<b>Generated:</b> {generated_at}",
            "",
            "<b>SUMMARY</b>",
            f"Total Spend:       <b>{s['total_spend']:,.2f} BDT</b>",
            f"Impressions:       {s['total_impressions']:,}",
            f"Reach:             {s['total_reach']:,}",
            f"Clicks:            {s['total_clicks']:,}",
            f"Avg CTR:           {s['avg_ctr']:.2f}%",
            f"Avg CPC:           {s['avg_cpc']:.2f} BDT",
        ]

        if s["total_conversions"] > 0:
            lines += [
                f"Conversions:       {s['total_conversions']:,}",
                f"Revenue:           {s['total_revenue']:,.2f} BDT",
                f"ROAS:              {s['roas']:.2f}x",
                f"Cost/Conversion:   {s['cost_per_conversion']:.2f} BDT",
            ]

        lines += [
            f"Active Campaigns:  {s['campaign_count']}",
            "",
        ]

        if campaigns:
            lines.append("<b>CAMPAIGN BREAKDOWN</b>")
            for i, c in enumerate(campaigns[:10], 1):
                name = c.get("campaign_name", f"Campaign {i}")
                spend = float(c.get("spend", 0))
                impressions = int(c.get("impressions", 0))
                clicks = int(c.get("clicks", 0))
                ctr = float(c.get("ctr", 0))
                cpc = float(c.get("cpc", 0))

                lines.append(
                    f"\n{i}. <b>{name[:35]}</b>\n"
                    f"   Spend: {spend:,.2f} | Imp: {impressions:,} | "
                    f"Clicks: {clicks:,} | CTR: {ctr:.2f}% | CPC: {cpc:.2f}"
                )

            if len(campaigns) > 10:
                lines.append(f"\n...এবং আরও {len(campaigns) - 10}টা campaign (PDF এ দেখুন)")

        lines.append("\n<i>SKF Boosting Automation</i>")
        return "\n".join(lines)

    def build_pdf_report(
        self,
        client_name: str,
        date_label: str,
        data: Dict[str, Any],
    ) -> str:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            )
        except ImportError:
            raise ImportError("reportlab not installed. Run: pip install reportlab")

        s = data["summary"]
        campaigns = data["campaigns"]
        generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        doc = SimpleDocTemplate(
            tmp_path,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        brand_blue = colors.HexColor("#1877F2")
        dark = colors.HexColor("#1C1E21")
        muted = colors.HexColor("#65676B")

        title_style = ParagraphStyle(
            "Title", parent=styles["Title"],
            fontSize=20, textColor=brand_blue, spaceAfter=4
        )
        sub_style = ParagraphStyle(
            "Sub", parent=styles["Normal"],
            fontSize=10, textColor=muted, spaceAfter=2
        )
        section_style = ParagraphStyle(
            "Section", parent=styles["Heading2"],
            fontSize=12, textColor=brand_blue,
            spaceBefore=14, spaceAfter=6,
            borderPad=4,
        )
        normal = ParagraphStyle(
            "Normal2", parent=styles["Normal"],
            fontSize=10, textColor=dark, spaceAfter=3
        )

        story = []

        story.append(Paragraph("SKF Boosting — Ads Performance Report", title_style))
        story.append(Paragraph(f"Client: {client_name}", sub_style))
        story.append(Paragraph(f"Period: {date_label}", sub_style))
        story.append(Paragraph(f"Generated: {generated_at}", sub_style))
        story.append(Spacer(1, 0.4 * cm))

        story.append(Paragraph("Summary", section_style))

        summary_data = [
            ["Metric", "Value"],
            ["Total Spend", f"{s['total_spend']:,.2f} BDT"],
            ["Impressions", f"{s['total_impressions']:,}"],
            ["Reach", f"{s['total_reach']:,}"],
            ["Clicks", f"{s['total_clicks']:,}"],
            ["Avg CTR", f"{s['avg_ctr']:.2f}%"],
            ["Avg CPC", f"{s['avg_cpc']:.2f} BDT"],
            ["Active Campaigns", str(s["campaign_count"])],
        ]

        if s["total_conversions"] > 0:
            summary_data += [
                ["Conversions", f"{s['total_conversions']:,}"],
                ["Revenue", f"{s['total_revenue']:,.2f} BDT"],
                ["ROAS", f"{s['roas']:.2f}x"],
                ["Cost/Conversion", f"{s['cost_per_conversion']:.2f} BDT"],
            ]

        summary_table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F2F5")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADDE1")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.4 * cm))

        if campaigns:
            story.append(Paragraph("Campaign Breakdown", section_style))

            camp_data = [["Campaign", "Spend", "Imp", "Clicks", "CTR", "CPC"]]
            for c in campaigns:
                name = c.get("campaign_name", "Unknown")
                if len(name) > 30:
                    name = name[:28] + "..."
                camp_data.append([
                    name,
                    f"{float(c.get('spend', 0)):,.0f}",
                    f"{int(c.get('impressions', 0)):,}",
                    f"{int(c.get('clicks', 0)):,}",
                    f"{float(c.get('ctr', 0)):.2f}%",
                    f"{float(c.get('cpc', 0)):.2f}",
                ])

            camp_table = Table(
                camp_data,
                colWidths=[6.5 * cm, 2 * cm, 2.5 * cm, 2 * cm, 2 * cm, 2 * cm]
            )
            camp_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F2F5")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADDE1")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]))
            story.append(camp_table)

        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(
            "Generated by SKF Boosting Automation Bot",
            ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=muted)
        ))

        doc.build(story)
        return tmp_path
