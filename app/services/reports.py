from io import BytesIO


def build_verification_report(verification):
    buffer = BytesIO()

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Relatorio de Verificacao")

    result = verification.result
    fields = verification.extracted_fields or {}
    validation = verification.validation_summary or {}

    story = [
        Paragraph("Relatorio de Verificacao Documental", styles["Title"]),
        Spacer(1, 14),
        Paragraph(
            "Este relatorio apresenta uma indicacao de risco e nao constitui decisao juridica definitiva.",
            styles["BodyText"],
        ),
        Spacer(1, 16),
    ]

    summary = [
        ["Documento", verification.document.original_filename],
        ["Tipo", verification.document.document_type.name],
        ["Utilizador", verification.user.name],
        ["Data", verification.created_at.strftime("%d/%m/%Y %H:%M")],
        ["Nivel de risco", result.risk_level],
        ["Score", f"{result.risk_score}/100"],
        ["Motor", result.ai_decision],
    ]

    table = Table(summary, colWidths=[130, 330])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f6")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d1d9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Campos extraidos", styles["Heading2"]))
    field_rows = [[label, fields.get(key, "")] for key, label in {
        "holder_name": "Nome",
        "document_number": "Numero",
        "process_number": "Numero de processo",
        "holder_id_number": "Numero de identificacao",
        "course": "Curso",
        "institution": "Instituicao",
        "issue_date": "Data",
    }.items()]
    story.append(Table(field_rows, colWidths=[130, 330]))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Motivos da classificacao", styles["Heading2"]))
    for reason in result.reasons or []:
        story.append(Paragraph(f"- {reason}", styles["BodyText"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Recomendacoes", styles["Heading2"]))
    for recommendation in result.recommendations or []:
        story.append(Paragraph(f"- {recommendation}", styles["BodyText"]))

    if validation.get("official_record"):
        story.append(Spacer(1, 12))
        story.append(Paragraph("Registro oficial associado", styles["Heading2"]))
        for key, value in validation["official_record"].items():
            story.append(Paragraph(f"{key}: {value}", styles["BodyText"]))

    doc.build(story)
    buffer.seek(0)
    return buffer
