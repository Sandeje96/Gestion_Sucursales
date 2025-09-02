# scripts/seed_demo_expenses.py
import os
from datetime import datetime
import pytz

from app import create_app, db
from app.models.user import User
from app.models.branch_expense import BranchExpense

# Levantamos la app con la config actual
app = create_app(os.environ.get("FLASK_ENV"))

def set_password(user, raw):
    if hasattr(user, "set_password"):
        user.set_password(raw)
    else:
        # fallback
        from werkzeug.security import generate_password_hash
        user.password_hash = generate_password_hash(raw)

with app.app_context():
    # ---------- Parámetros demo ----------
    demo_branch = "Uruguay"       # podés cambiar por otra sucursal
    demo_user   = "demo_uruguay"
    demo_pass   = "1234"

    # Fecha AR (nunca meses futuros)
    tz = pytz.timezone("America/Argentina/Buenos_Aires")
    today = datetime.now(tz).date()
    year, month = today.year, today.month

    # ---------- Usuario de sucursal (si no existe) ----------
    u = User.query.filter_by(username=demo_user).first()
    if not u:
        u = User(
            username=demo_user,
            email=f"{demo_user}@local.test",
            role="branch_user",
            branch_name=demo_branch,
            is_active=True,
            is_admin=False
        )
        set_password(u, demo_pass)
        db.session.add(u)
        db.session.commit()
        print(f"✓ Usuario creado: {demo_user} / {demo_pass}")
    else:
        print(f"• Usuario ya existía: {demo_user}")

    # ---------- Gastos demo del mes actual ----------
    seed_rows = [
        ("ALQUILER",  "-", 250000, True),
        ("LUZ",       "-",  65000, False),
        ("AGUA",      "-",  15000, True),
        ("INTERNET",  "-",  18000, False),
        ("OTROS", "Repuestos", 12000, True),
        ("OTROS", "Flete",     22000, False),
    ]

    for category, description, amount, is_paid in seed_rows:
        desc = "-" if category != "OTROS" else description
        row = BranchExpense.query.filter_by(
            branch_name=demo_branch,
            year=year,
            month=month,
            category=category,
            description=desc
        ).first()

        if not row:
            row = BranchExpense(
                branch_name=demo_branch,
                year=year,
                month=month,
                category=category,
                description=desc,
                amount=amount,
                is_paid=is_paid,
                created_by=getattr(u, "id", None)
            )
            if is_paid and hasattr(row, "mark_paid"):
                row.mark_paid(getattr(u, "id", None))
            db.session.add(row)
        else:
            row.amount = amount
            row.is_paid = is_paid
            row.updated_at = datetime.utcnow()
            if is_paid and not getattr(row, "paid_at", None) and hasattr(row, "mark_paid"):
                row.mark_paid(getattr(u, "id", None))
            if (not is_paid) and getattr(row, "paid_at", None) and hasattr(row, "unmark_paid"):
                row.unmark_paid()

    db.session.commit()
    print(f"✓ Gastos de {demo_branch} {month:02d}/{year} listos.")
