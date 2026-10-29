from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import DocumentType, Institution, ReferenceDocument, Role, User
from ..services.document_processor import build_reference_profile


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config[
        "ALLOWED_EXTENSIONS"
    ]


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
def users():
    require_admin()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role_id = request.form.get("role_id")

        if not name or not email or not password or not role_id:
            flash("Preencha todos os campos.", "warning")
        elif User.query.filter_by(email=email).first():
            flash("Ja existe um utilizador com esse email.", "warning")
        else:
            role = db.session.get(Role, int(role_id))
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Utilizador criado com sucesso.", "success")
            return redirect(url_for("admin.users"))

    return render_template(
        "admin/users.html",
        users=User.query.order_by(User.created_at.desc()).all(),
        roles=Role.query.order_by(Role.name).all(),
    )


@admin_bp.route("/references", methods=["GET", "POST"])
@login_required
def references():
    require_admin()

    if request.method == "POST":
        form_action = request.form.get("form_action")
        if form_action == "institution":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip().upper()
            if not name or not code:
                flash("Indique nome e codigo da instituicao.", "warning")
            elif Institution.query.filter(
                (Institution.name == name) | (Institution.code == code)
            ).first():
                flash("Ja existe uma instituicao com esse nome ou codigo.", "warning")
            else:
                db.session.add(Institution(name=name, code=code))
                db.session.commit()
                flash("Instituicao criada com sucesso.", "success")
            return redirect(url_for("admin.references"))

        label = request.form.get("label", "").strip()
        institution_id = request.form.get("institution_id")
        document_type_id = request.form.get("document_type_id")
        file = request.files.get("document")

        if not label or not institution_id or not document_type_id or not file:
            flash("Preencha todos os dados do modelo original.", "warning")
        elif not allowed_file(file.filename):
            flash("Formato invalido. Use PDF, PNG, JPG ou JPEG.", "danger")
        else:
            filename = secure_filename(file.filename)
            stored_filename = f"reference_{uuid4().hex}_{filename}"
            reference_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "references"
            reference_dir.mkdir(parents=True, exist_ok=True)
            file_path = reference_dir / stored_filename
            file.save(file_path)

            try:
                profile = build_reference_profile(str(file_path))
                missing_comparison_data = []
                if not profile["normalized_text"]:
                    missing_comparison_data.append("texto OCR")
                if not profile["visual"].get("signature"):
                    missing_comparison_data.append("assinatura visual")
                if missing_comparison_data:
                    raise ValueError(
                        "O modelo original nao tem dados suficientes para comparacao: "
                        + " e ".join(missing_comparison_data)
                        + "."
                    )

                reference = ReferenceDocument(
                    label=label,
                    original_filename=filename,
                    stored_filename=str(Path("references") / stored_filename),
                    mime_type=file.mimetype,
                    file_size=file_path.stat().st_size,
                    normalized_text=profile["normalized_text"],
                    extracted_fields=profile["fields"],
                    visual_signature=profile["visual"].get("signature", {}),
                    institution_id=int(institution_id),
                    document_type_id=int(document_type_id),
                    uploaded_by=current_user,
                )
                db.session.add(reference)
                db.session.commit()
                flash("Modelo original registado e processado com sucesso.", "success")
            except Exception as exc:
                db.session.rollback()
                if file_path.exists():
                    file_path.unlink()
                flash(f"Nao foi possivel processar o modelo original: {exc}", "danger")

        return redirect(url_for("admin.references"))

    return render_template(
        "admin/references.html",
        institutions=Institution.query.order_by(Institution.name).all(),
        document_types=DocumentType.query.order_by(DocumentType.name).all(),
        references=ReferenceDocument.query.order_by(ReferenceDocument.created_at.desc()).all(),
    )
