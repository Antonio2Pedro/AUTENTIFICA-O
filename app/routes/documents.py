from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (
    AuditLog,
    Document,
    DocumentType,
    Institution,
    ReferenceDocument,
    Verification,
    VerificationResult,
)
from ..services.document_processor import process_document, refresh_reference_profile
from ..services.reports import build_verification_report


documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


def allowed_file(filename):
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in current_app.config["ALLOWED_EXTENSIONS"]


@documents_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    types = DocumentType.query.order_by(DocumentType.name).all()
    institutions = Institution.query.order_by(Institution.name).all()
    references = ReferenceDocument.query.filter_by(active=True).order_by(
        ReferenceDocument.created_at.desc()
    ).all()

    if request.method == "POST":
        document_type_id = request.form.get("document_type_id")
        institution_id = request.form.get("institution_id")
        reference_document_id = request.form.get("reference_document_id")
        file = request.files.get("document")

        if not document_type_id or not file:
            flash("Selecione o tipo e o ficheiro do documento.", "warning")
            return redirect(url_for("documents.new"))

        if not allowed_file(file.filename):
            flash("Formato invalido. Use PDF, JPG ou PNG.", "danger")
            return redirect(url_for("documents.new"))

        reference = None
        if reference_document_id:
            reference = db.session.get(ReferenceDocument, int(reference_document_id))
        elif institution_id:
            reference = (
                ReferenceDocument.query.filter_by(
                    institution_id=int(institution_id),
                    document_type_id=int(document_type_id),
                    active=True,
                )
                .order_by(ReferenceDocument.created_at.desc())
                .first()
            )

        if reference and reference.document_type_id != int(document_type_id):
            flash("O modelo original selecionado nao corresponde ao tipo de documento.", "warning")
            return redirect(url_for("documents.new"))
        if reference and institution_id and reference.institution_id != int(institution_id):
            flash("O modelo original selecionado nao pertence a instituicao indicada.", "warning")
            return redirect(url_for("documents.new"))

        reference_fields = (reference.extracted_fields or {}) if reference else {}
        if reference and (
            not reference.normalized_text
            or not reference.visual_signature
            or not reference_fields.get("holder_name")
        ):
            try:
                refresh_reference_profile(reference, current_app.config["UPLOAD_FOLDER"])
            except FileNotFoundError as exc:
                flash(f"{exc} Volte a registar o modelo original para poder compara-lo.", "danger")
                return redirect(url_for("documents.new"))

        safe_name = secure_filename(file.filename)
        stored_name = f"{uuid4().hex}_{safe_name}"
        upload_path = Path(current_app.config["UPLOAD_FOLDER"]) / stored_name
        file.save(upload_path)

        document = Document(
            original_filename=safe_name,
            stored_filename=stored_name,
            mime_type=file.mimetype,
            file_size=upload_path.stat().st_size,
            uploaded_by=current_user,
            document_type_id=int(document_type_id),
        )
        db.session.add(document)
        db.session.flush()

        try:
            analysis = process_document(str(upload_path), reference=reference)
            verification = Verification(
                document=document,
                user=current_user,
                ocr_text=analysis["ocr"]["text"],
                extracted_fields=analysis["fields"],
                validation_summary=analysis["validation"],
                visual_summary=analysis["visual"],
            )
            db.session.add(verification)
            db.session.flush()

            result_data = analysis["risk"]
            result = VerificationResult(
                verification=verification,
                risk_score=result_data["risk_score"],
                risk_level=result_data["risk_level"],
                ai_decision=result_data["ai_decision"],
                reasons=result_data["reasons"] + analysis["ocr"].get("warnings", []),
                recommendations=result_data["recommendations"],
            )
            db.session.add(result)
            document.status = "Analisado"
            db.session.add(
                AuditLog(
                    action="VERIFICACAO",
                    entity="Document",
                    description=f"Documento {document.original_filename} analisado.",
                    user_id=current_user.id,
                )
            )
            db.session.commit()
            flash("Documento analisado com sucesso.", "success")
            return redirect(url_for("documents.result", verification_id=verification.id))
        except Exception as exc:
            document.status = "Erro"
            db.session.commit()
            flash(f"Erro ao processar documento: {exc}", "danger")
            return redirect(url_for("documents.new"))

    return render_template(
        "documents/new.html",
        document_types=types,
        institutions=institutions,
        reference_documents=references,
    )


@documents_bp.route("/history")
@login_required
def history():
    verifications = Verification.query.order_by(Verification.created_at.desc()).all()
    return render_template("documents/history.html", verifications=verifications)


@documents_bp.route("/<int:verification_id>")
@login_required
def detail(verification_id):
    verification = db.get_or_404(Verification, verification_id)
    return render_template("documents/detail.html", verification=verification)


@documents_bp.route("/<int:verification_id>/result")
@login_required
def result(verification_id):
    verification = db.get_or_404(Verification, verification_id)
    references = ReferenceDocument.query.filter_by(active=True).order_by(
        ReferenceDocument.created_at.desc()
    ).all()
    return render_template(
        "documents/result.html",
        verification=verification,
        reference_documents=references,
    )


@documents_bp.route("/<int:verification_id>/reanalyze", methods=["POST"])
@login_required
def reanalyze(verification_id):
    verification = db.get_or_404(Verification, verification_id)
    selected_reference_id = request.form.get("reference_document_id")
    previous_comparison = (verification.validation_summary or {}).get(
        "reference_comparison"
    )
    reference_id = selected_reference_id or (
        previous_comparison.get("reference_id") if previous_comparison else None
    )
    try:
        reference = (
            db.session.get(ReferenceDocument, int(reference_id)) if reference_id else None
        )
    except ValueError:
        flash("O modelo original selecionado e invalido.", "warning")
        return redirect(url_for("documents.result", verification_id=verification.id))
    if reference_id and not reference:
        flash("O modelo original selecionado nao foi encontrado.", "warning")
        return redirect(url_for("documents.result", verification_id=verification.id))

    if reference and reference.document_type_id != verification.document.document_type_id:
        flash("O modelo original selecionado nao corresponde ao tipo de documento.", "warning")
        return redirect(url_for("documents.result", verification_id=verification.id))

    upload_path = Path(current_app.config["UPLOAD_FOLDER"]) / verification.document.stored_filename
    if not upload_path.is_file():
        flash("O ficheiro original nao foi encontrado; nao foi possivel reanalisar.", "danger")
        return redirect(url_for("documents.result", verification_id=verification.id))

    try:
        if reference and (
            not reference.normalized_text
            or not reference.visual_signature
            or not (reference.extracted_fields or {}).get("holder_name")
        ):
            refresh_reference_profile(reference, current_app.config["UPLOAD_FOLDER"])

        analysis = process_document(str(upload_path), reference=reference)
        verification.ocr_text = analysis["ocr"]["text"]
        verification.extracted_fields = analysis["fields"]
        verification.validation_summary = analysis["validation"]
        verification.visual_summary = analysis["visual"]

        result = verification.result
        risk = analysis["risk"]
        result.risk_score = risk["risk_score"]
        result.risk_level = risk["risk_level"]
        result.ai_decision = risk["ai_decision"]
        result.reasons = risk["reasons"] + analysis["ocr"].get("warnings", [])
        result.recommendations = risk["recommendations"]
        db.session.add(
            AuditLog(
                action="REANALISE",
                entity="Document",
                description=f"Documento {verification.document.original_filename} reanalisado.",
                user_id=current_user.id,
            )
        )
        db.session.commit()
        flash("Documento reanalisado com as regras atualizadas.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Nao foi possivel reanalisar o documento: {exc}", "danger")

    return redirect(url_for("documents.result", verification_id=verification.id))


@documents_bp.route("/file/<int:document_id>")
@login_required
def file(document_id):
    document = db.get_or_404(Document, document_id)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        document.stored_filename,
        as_attachment=False,
    )


@documents_bp.route("/<int:verification_id>/report")
@login_required
def report(verification_id):
    verification = db.get_or_404(Verification, verification_id)
    report_buffer = build_verification_report(verification)
    filename = f"relatorio_verificacao_{verification.id}.pdf"
    return send_file(
        report_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
