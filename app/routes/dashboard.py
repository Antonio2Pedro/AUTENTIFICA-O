from flask import Blueprint, render_template
from flask_login import login_required

from ..models import Document, Verification, VerificationResult


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    total_documents = Document.query.count()
    total_verifications = Verification.query.count()
    low_risk = VerificationResult.query.filter(
        VerificationResult.risk_level.like("Baixo%")
    ).count()
    medium_risk = VerificationResult.query.filter(
        VerificationResult.risk_level.like("Medio%")
    ).count()
    high_risk = VerificationResult.query.filter(
        VerificationResult.risk_level.like("Alto%")
    ).count()
    manual = VerificationResult.query.filter(
        VerificationResult.risk_level.like("Verificacao%")
    ).count()
    recent = Verification.query.order_by(Verification.created_at.desc()).limit(6).all()

    return render_template(
        "dashboard/index.html",
        total_documents=total_documents,
        total_verifications=total_verifications,
        low_risk=low_risk,
        medium_risk=medium_risk,
        high_risk=high_risk,
        manual=manual,
        recent=recent,
    )


@dashboard_bp.route("/settings")
@login_required
def settings():
    return render_template("dashboard/settings.html")
