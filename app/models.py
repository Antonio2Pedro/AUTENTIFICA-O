from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(160), nullable=False)

    users = db.relationship("User", back_populates="role")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    role = db.relationship("Role", back_populates="users")

    documents = db.relationship("Document", back_populates="uploaded_by")
    verifications = db.relationship("Verification", back_populates="user")
    reference_documents = db.relationship("ReferenceDocument", back_populates="uploaded_by")

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.role and self.role.name == "Administrador"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Institution(db.Model):
    __tablename__ = "institutions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    code = db.Column(db.String(30), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    records = db.relationship("OfficialRecord", back_populates="institution")
    reference_documents = db.relationship(
        "ReferenceDocument", back_populates="institution", cascade="all, delete-orphan"
    )


class DocumentType(db.Model):
    __tablename__ = "document_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=False)

    documents = db.relationship("Document", back_populates="document_type")
    records = db.relationship("OfficialRecord", back_populates="document_type")
    reference_documents = db.relationship(
        "ReferenceDocument", back_populates="document_type", cascade="all, delete-orphan"
    )


class OfficialRecord(db.Model):
    __tablename__ = "official_records"

    id = db.Column(db.Integer, primary_key=True)
    document_number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    holder_name = db.Column(db.String(160), nullable=False)
    course = db.Column(db.String(160), nullable=True)
    issue_date = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), default="Valido", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=False)
    institution = db.relationship("Institution", back_populates="records")

    document_type_id = db.Column(db.Integer, db.ForeignKey("document_types.id"), nullable=False)
    document_type = db.relationship("DocumentType", back_populates="records")


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(40), default="Carregado", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_by = db.relationship("User", back_populates="documents")

    document_type_id = db.Column(db.Integer, db.ForeignKey("document_types.id"), nullable=False)
    document_type = db.relationship("DocumentType", back_populates="documents")

    verifications = db.relationship(
        "Verification", back_populates="document", cascade="all, delete-orphan"
    )


class ReferenceDocument(db.Model):
    """An approved original used as a structural and visual comparison model."""

    __tablename__ = "reference_documents"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(160), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    normalized_text = db.Column(db.Text, nullable=True)
    extracted_fields = db.Column(db.JSON, nullable=False, default=dict)
    visual_signature = db.Column(db.JSON, nullable=False, default=dict)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=False)
    institution = db.relationship("Institution", back_populates="reference_documents")

    document_type_id = db.Column(db.Integer, db.ForeignKey("document_types.id"), nullable=False)
    document_type = db.relationship("DocumentType", back_populates="reference_documents")

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_by = db.relationship("User", back_populates="reference_documents")


class Verification(db.Model):
    __tablename__ = "verifications"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    ocr_text = db.Column(db.Text, nullable=True)
    extracted_fields = db.Column(db.JSON, nullable=False, default=dict)
    validation_summary = db.Column(db.JSON, nullable=False, default=dict)
    visual_summary = db.Column(db.JSON, nullable=False, default=dict)

    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    document = db.relationship("Document", back_populates="verifications")

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", back_populates="verifications")

    result = db.relationship(
        "VerificationResult",
        back_populates="verification",
        cascade="all, delete-orphan",
        uselist=False,
    )


class VerificationResult(db.Model):
    __tablename__ = "verification_results"

    id = db.Column(db.Integer, primary_key=True)
    risk_score = db.Column(db.Integer, nullable=False)
    risk_level = db.Column(db.String(60), nullable=False)
    ai_decision = db.Column(db.String(120), nullable=False)
    reasons = db.Column(db.JSON, nullable=False, default=list)
    recommendations = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    verification_id = db.Column(db.Integer, db.ForeignKey("verifications.id"), nullable=False)
    verification = db.relationship("Verification", back_populates="result")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(80), nullable=False)
    entity = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def seed_demo_data():
    admin_role = Role.query.filter_by(name="Administrador").first()
    if not admin_role:
        admin_role = Role(name="Administrador", description="Acesso completo ao sistema")
        db.session.add(admin_role)

    verifier_role = Role.query.filter_by(name="Funcionario").first()
    if not verifier_role:
        verifier_role = Role(
            name="Funcionario", description="Realiza verificacoes documentais"
        )
        db.session.add(verifier_role)

    db.session.flush()

    if not User.query.filter_by(email="admin@example.com").first():
        admin = User(name="Administrador", email="admin@example.com", role=admin_role)
        admin.set_password("admin123")
        db.session.add(admin)

    if not User.query.filter_by(email="funcionario@example.com").first():
        funcionario = User(
            name="Funcionario Verificador",
            email="funcionario@example.com",
            role=verifier_role,
        )
        funcionario.set_password("func123")
        db.session.add(funcionario)

    institution = Institution.query.filter_by(code="UNIX").first()
    if not institution:
        institution = Institution(name="Universidade X", code="UNIX")
        db.session.add(institution)

    certificate = DocumentType.query.filter_by(name="Certificado").first()
    if not certificate:
        certificate = DocumentType(
            name="Certificado",
            description="Certificados academicos e institucionais",
        )
        db.session.add(certificate)

    declaration = DocumentType.query.filter_by(name="Declaracao").first()
    if not declaration:
        declaration = DocumentType(
            name="Declaracao",
            description="Declaracoes emitidas por instituicoes",
        )
        db.session.add(declaration)

    diploma = DocumentType.query.filter_by(name="Diploma").first()
    if not diploma:
        diploma = DocumentType(name="Diploma", description="Diplomas academicos")
        db.session.add(diploma)

    db.session.flush()

    demo_records = [
        {
            "document_number": "CERT-2025-00152",
            "holder_name": "Joao Antonio",
            "course": "Engenharia Informatica",
            "issue_date": "15/07/2025",
            "status": "Valido",
            "document_type": certificate,
        },
        {
            "document_number": "DECL-2026-00017",
            "holder_name": "Ana Maria Costa",
            "course": "Gestao Publica",
            "issue_date": "02/02/2026",
            "status": "Valido",
            "document_type": declaration,
        },
        {
            "document_number": "DIP-2024-00991",
            "holder_name": "Carlos Manuel Pedro",
            "course": "Redes de Computadores",
            "issue_date": "18/11/2024",
            "status": "Revogado",
            "document_type": diploma,
        },
    ]

    for item in demo_records:
        if not OfficialRecord.query.filter_by(document_number=item["document_number"]).first():
            db.session.add(
                OfficialRecord(
                    document_number=item["document_number"],
                    holder_name=item["holder_name"],
                    course=item["course"],
                    issue_date=item["issue_date"],
                    status=item["status"],
                    institution=institution,
                    document_type=item["document_type"],
                )
            )

    db.session.commit()

