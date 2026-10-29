from pathlib import Path


def create_demo_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    out_dir = Path(__file__).resolve().parent / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "certificado_demo_autentico.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 90, "Universidade X")

    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, height - 135, "Certificado")

    c.setFont("Helvetica", 12)
    y = height - 190
    lines = [
        "Nome: Joao Antonio",
        "Numero: CERT-2025-00152",
        "Curso: Engenharia Informatica",
        "Instituicao: Universidade X",
        "Data: 15/07/2025",
        "",
        "Declaramos que os dados acima constam no registro academico institucional.",
    ]

    for line in lines:
        c.drawString(90, y, line)
        y -= 24

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(90, 95, "Documento de demonstracao para o prototipo DocAuth AI.")
    c.save()
    print(pdf_path)


if __name__ == "__main__":
    create_demo_pdf()

