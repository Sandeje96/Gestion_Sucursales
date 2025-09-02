# app/routes/expenses.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models.branch_expense import BranchExpense, CATEGORIES
from app.models.user import User
from app.forms.expense_forms import ExpenseForm
import calendar
from datetime import datetime, date
import pytz
from app.models.cash_tray import CashTray

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


# -------------------------
# Helpers de rol y tiempo
# -------------------------
def _flag(user, prop_or_method_name: str) -> bool:
    """Devuelve True si el usuario tiene el flag (método o propiedad)."""
    val = getattr(user, prop_or_method_name, None)
    if callable(val):
        try:
            return bool(val())
        except Exception:
            return False
    return bool(val)

def _is_admin() -> bool:
    # Soporta .is_admin_user(), .is_admin, etc.
    return _flag(current_user, "is_admin_user") or _flag(current_user, "is_admin")

def _is_branch() -> bool:
    # Soporta .is_branch_user(), role == 'branch_user', etc.
    return _flag(current_user, "is_branch_user") or getattr(current_user, "role", "") == "branch_user"

def _today_ar() -> date:
    tz = pytz.timezone("America/Argentina/Buenos_Aires")
    return datetime.now(tz).date()

def _months_for_year(year: int, today: date):
    """
    Devuelve meses disponibles para selector:
    - Si es el año actual: 1..mes_actual
    - Si es año pasado: 1..12
    (Nunca meses futuros)
    """
    last = today.month if year >= today.year else 12
    if year > today.year:
        last = today.month
    return [{"value": m, "label": _month_name_spanish(m)} for m in range(1, last + 1)]


def _all_branches():
    """Lista de sucursales conocidas (solo de usuarios branch_user y de gastos)."""
    # Solo usuarios con rol branch_user
    users_branches = {u.branch_name for u in User.query.filter(
        User.branch_name.isnot(None),
        User.role == 'branch_user'
    ).all()}
    
    # Sucursales que tienen gastos registrados
    expenses_branches = {b for (b,) in db.session.query(BranchExpense.branch_name).distinct().all()}
    
    return sorted({b for b in (users_branches | expenses_branches) if b})


# -------------------------
# Vistas
# -------------------------
@expenses_bp.route("/", methods=["GET"])
@login_required
def index():
    """
    Reglas:
    - Admin: debe elegir sucursal para ver/cargar.
    - Usuario de sucursal: sucursal forzada a current_user.branch_name.
    - Por defecto: año/mes actual; no se muestran meses futuros.
    - Se construye SIEMPRE un único periodo (branch + mes) cuando hay sucursal.
    """
    today = _today_ar()
    # Defaults
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))
    branch = request.args.get("branch")

    # Normalizar año/mes para evitar futuro
    if year > today.year:
        year = today.year
        month = today.month
    if year == today.year and month > today.month:
        month = today.month

    # Forzar sucursal para usuarios de sucursal
    if _is_branch():
        branch = getattr(current_user, "branch_name", None)

    branches = _all_branches() if _is_admin() else None
    months = _months_for_year(year, today)

    # Si es admin y no eligió sucursal: mostrar solo selector
    if _is_admin() and not branch:
        return render_template(
            "expenses/index.html",
            title="Gastos Mensuales",
            year=year,
            month=month,
            months=months,
            branch=None,
            branches=branches,
            is_admin=True,
            periods=[],           # nada hasta elegir sucursal
            categories=CATEGORIES
        )

    # Si no hay sucursal (caso borde): también mostramos selector vacío
    if not branch:
        return render_template(
            "expenses/index.html",
            title="Gastos Mensuales",
            year=year,
            month=month,
            months=months,
            branch=None,
            branches=branches,
            is_admin=_is_admin(),
            periods=[],
            categories=CATEGORIES
        )

    # Cargar items SOLO del (branch, year, month) seleccionado
    items = (BranchExpense.query
             .filter_by(branch_name=branch, year=year, month=month)
             .order_by(BranchExpense.category.asc(), BranchExpense.id.asc())
             .all())

    # Estado del periodo
    required = set(BranchExpense.required_categories_for_branch(branch))
    paid_required = {it.category for it in items if it.is_paid and it.category in required}
    is_complete = required.issubset(paid_required)
    total_amount = sum(float(it.amount or 0) for it in items)

    period = {
        "branch_name": branch,
        "month": month,
        "month_label": calendar.month_name[month],
        "items": items,
        "is_complete": is_complete,
        "total_amount": total_amount,
        "required_categories": sorted(list(required)),
    }

    return render_template(
        "expenses/index.html",
        title="Gastos Mensuales",
        year=year,
        month=month,
        months=months,
        branch=branch,
        branches=branches,
        is_admin=_is_admin(),
        periods=[period],      # SIEMPRE un solo periodo
        categories=CATEGORIES
    )


@expenses_bp.route("/save", methods=["POST"])
@login_required
def save():
    """
    Crea/actualiza un gasto. Unicidad:
    - Para categorías != 'OTROS': (branch, year, month, category, description='-')
    - Para 'OTROS': (branch, year, month, category, description)  # permite múltiples
    """
    form = ExpenseForm()

    try:
        # Resolver sucursal según rol
        branch_name = (form.branch_name.data or "").strip() if _is_admin() else getattr(current_user, "branch_name", None)
        if not branch_name:
            raise ValueError("Debe seleccionar una sucursal.")

        year = int(form.year.data)
        month = int(form.month.data)
        category = (form.category.data or "").strip()
        description = (form.description.data or "").strip()
        amount = float(form.amount.data or 0)
        is_paid = bool(form.is_paid.data)

        # Normalizar futuro
        today = _today_ar()
        if year > today.year or (year == today.year and month > today.month):
            year, month = today.year, today.month

        # Validaciones de negocio/permisos
        form.branch_name.data = branch_name
        if hasattr(form, "validate_for_user"):
            form.validate_for_user(current_user)

        # Colapsar descripción para categorías fijas
        if category != "OTROS":
            description = "-"

        row = BranchExpense.query.filter_by(
            branch_name=branch_name, year=year, month=month,
            category=category, description=description
        ).first()

        if not row:
            row = BranchExpense(
                branch_name=branch_name,
                year=year,
                month=month,
                category=category,
                description=description,
                amount=amount,
                is_paid=is_paid,
                created_by=getattr(current_user, "id", None)
            )
            if is_paid and hasattr(row, "mark_paid"):
                row.mark_paid(getattr(current_user, "id", None))
            db.session.add(row)
        else:
            row.amount = amount
            row.is_paid = is_paid
            # usar UTC para evitar problemas de TZ en DB
            row.updated_at = datetime.utcnow()
            if is_paid and not getattr(row, "paid_at", None) and hasattr(row, "mark_paid"):
                row.mark_paid(getattr(current_user, "id", None))
            if (not is_paid) and getattr(row, "paid_at", None) and hasattr(row, "unmark_paid"):
                row.unmark_paid()

        db.session.commit()
        flash("Gasto guardado correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error guardando el gasto: {e}", "error")

    # Volver a la grilla del año/branch actual
    params = {"year": form.year.data, "month": form.month.data}
    if _is_admin() and form.branch_name.data:
        params["branch"] = form.branch_name.data
    return redirect(url_for("expenses.index", **params))

def _month_name_spanish(month_number):
    """Devuelve el nombre del mes en español."""
    months = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    return months.get(month_number, "")


@expenses_bp.route("/toggle/<int:expense_id>", methods=["POST"])
@login_required
def toggle_paid(expense_id: int):
    row = BranchExpense.query.get_or_404(expense_id)

    # Permisos
    if not BranchExpense.can_edit_category(current_user, row.branch_name, row.category):
        abort(403)

    try:
        if row.is_paid:
            row.unmark_paid()
        else:
            row.mark_paid(getattr(current_user, "id", None))

        db.session.commit()
        return jsonify({"status": "ok", "is_paid": row.is_paid})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
