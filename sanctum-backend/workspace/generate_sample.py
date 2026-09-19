"""Generate sample test documents (PDF with plain text and tables) for pipeline testing."""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def generate_sample_pdf(output_path: str | Path) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(out_path), pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="InspectionTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A365D"),
    )

    story = [
        Paragraph("REFINERY PRESSURE VESSEL INSPECTION REPORT", title_style),
        Spacer(1, 12),
        Paragraph(
            "<b>Facility:</b> Northern PSU Refinery Unit 4<br/>"
            "<b>Equipment Tag:</b> PV-204B (Secondary Hydrocracker)<br/>"
            "<b>Inspection Standard:</b> API 510 Pressure Vessel Inspection Code<br/>"
            "<b>Status:</b> Scheduled Ultrasonic & Visual Wall Thickness Evaluation",
            styles["Normal"],
        ),
        Spacer(1, 14),
        Paragraph("1. Wall Thickness Ultrasonic Measurements", styles["Heading2"]),
        Spacer(1, 6),
    ]

    # Sample Table
    table_data = [
        ["Inspection Zone", "Nominal (mm)", "Measured (mm)", "Min Required (mm)", "Compliance"],
        ["Shell Ring 1", "38.50", "37.85", "32.00", "PASS"],
        ["Shell Ring 2", "38.50", "36.90", "32.00", "PASS"],
        ["Top Head Crown", "42.00", "41.10", "35.50", "PASS"],
        ["Bottom Nozzle N1", "25.40", "22.80", "21.00", "MONITOR"],
    ]

    t = Table(table_data, colWidths=[130, 85, 85, 105, 80])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
        ])
    )
    story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("2. Governing Formula", styles["Heading2"]))
    story.append(
        Paragraph(
            "Minimum required thickness is calculated using ASME Section VIII Div 1 formula:<br/>"
            "<b>t_min = (P * R) / (S * E - 0.6 * P)</b>",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 14))

    story.append(Paragraph("3. Inspector Sign-off", styles["Heading2"]))
    story.append(
        Paragraph(
            "Inspector ID: INSP-7749<br/>"
            "Recommendation: Re-inspect nozzle N1 at 12-month interval. All other shell rings approved for service.",
            styles["Normal"],
        )
    )

    doc.build(story)
    return out_path


if __name__ == "__main__":
    target = Path(__file__).parent / "sample_inspection.pdf"
    generate_sample_pdf(target)
    print(f"Sample inspection PDF generated at: {target}")
