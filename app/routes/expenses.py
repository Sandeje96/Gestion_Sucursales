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

def _months_from_current_to_year_end(today: date):
    """Lista de meses SOLO desde el mes actual hasta diciembre del año en curso."""
    return [{"value": m, "label": _month_name_spanish(m)} for m in range(today.month, 13)]

def _all_branches():
    """Lista de sucursales conocidas (solo de usuarios branch_user y de gastos)."""
    users_branches = {u.branch_name for u in User.query.filter(
        User.branch_name.isnot(None),
        User.role == 'branch_user'
    ).all()}
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
    - Puede ver todos los meses del año seleccionado.
    - Un único periodo (branch + mes) cuando hay sucursal.
    - month_status colorea el desplegable (verde completo / rojo pendiente).
    """
    today = _today_ar()

    # Permitir seleccionar año (por defecto el actual)
    year_arg = request.args.get("year", type=int)
    year = year_arg if year_arg else today.year

    # Si estamos en el año actual, mes mínimo es el actual
    # Si es un año anterior, podemos ver todos los meses
    month_arg = request.args.get("month", type=int)
    
    if year == today.year:
        # Año actual: solo desde mes actual en adelante
        month = month_arg if month_arg and month_arg >= today.month else today.month
        months = _months_from_current_to_year_end(today)
    else:
        # Año diferente: todos los meses del año
        month = month_arg if month_arg and 1 <= month_arg <= 12 else 1
        months = [{"value": m, "label": _month_name_spanish(m)} for m in range(1, 13)]
    
    # clamp por si pasaran valores inválidos
    if month > 12:
        month = 12
    if month < 1:
        month = 1

    # Sucursal
    branch = request.args.get("branch")
    if _is_branch():
        branch = getattr(current_user, "branch_name", None)

    branches = _all_branches() if _is_admin() else None

    # -------- Estado por mes (para colorear opciones) --------
    month_status = {}  # {mes:int -> 'ok'|'pending'}
    if branch:
        # Si es año actual, solo desde mes actual en adelante
        # Si es año anterior, todos los meses
        if year == today.year:
            all_items_year = (BranchExpense.query
                              .filter_by(branch_name=branch, year=year)
                              .filter(BranchExpense.month >= today.month)
                              .all())
        else:
            all_items_year = (BranchExpense.query
                              .filter_by(branch_name=branch, year=year)
                              .all())
        
        by_month = {}
        for it in all_items_year:
            by_month.setdefault(int(it.month), []).append(it)

        required = set(BranchExpense.required_categories_for_branch(branch))
        for m in [d["value"] for d in months]:
            items_m = by_month.get(m, [])
            # Nueva regla: si NO hay ítems, igual es PENDIENTE (son gastos obligatorios todos los meses)
            if not items_m:
                month_status[m] = "pending"
                continue
            any_unpaid = any(not it.is_paid for it in items_m)
            cats_paid = {it.category for it in items_m if it.is_paid}
            required_ok = required.issubset(cats_paid)
            month_status[m] = "ok" if (not any_unpaid) and required_ok else "pending"
    # ----------------------------------------------------------

    # Si es admin y no eligió sucursal: selector solo
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
            periods=[],
            categories=CATEGORIES,
            month_status=month_status,
            today=today  # Pasar today al template
        )

    # Sin sucursal (borde)
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
            categories=CATEGORIES,
            month_status=month_status,
            today=today  # Pasar today al template
        )

    # Cargar items del (branch, year, month) seleccionado
    items = (BranchExpense.query
             .filter_by(branch_name=branch, year=year, month=month)
             .order_by(BranchExpense.category.asc(), BranchExpense.id.asc())
             .all())

    # Completo solo si TODAS las requeridas están pagadas y no hay ningún ítem impago
    required = set(BranchExpense.required_categories_for_branch(branch))
    paid_required = {it.category for it in items if it.is_paid and it.category in required}
    any_unpaid = any(not it.is_paid for it in items)
    # Además, si no hay ítems en el mes, NO está completo (arranca en rojo)
    is_complete = (required.issubset(paid_required)) and (not any_unpaid) and bool(items)

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
        periods=[period],
        categories=CATEGORIES,
        month_status=month_status,
        today=today  # Pasar today al template
    )


@expenses_bp.route("/save", methods=["POST"])
@login_required
def save():
    """
    Crea/actualiza un gasto. Unicidad:
    - Para categorías != 'OTROS': (branch, year, month, category, description='-')
    - Para 'OTROS': (branch, year, month, category, description)
    Importante:
    - NO se permite setear 'pagado' desde el form.
    - Si el gasto ya está pagado, NO se permite modificar.
    - Permite guardar en cualquier año y mes (respetando reglas de año actual).
    """
    form = ExpenseForm()

    try:
        today = _today_ar()
        branch_name = (form.branch_name.data or "").strip() if _is_admin() else getattr(current_user, "branch_name", None)
        if not branch_name:
            raise ValueError("Debe seleccionar una sucursal.")

        # Permitir guardar en el año seleccionado del formulario
        year = int(request.form.get('year', today.year))
        
        # Si es año actual, mes mínimo es el actual
        # Si es año anterior, permitir cualquier mes
        month_input = int(form.month.data)
        if year == today.year:
            month = max(month_input, today.month)
        elif year > today.year:
            # Años futuros: usar el mes ingresado (validar que sea válido)
            month = month_input if 1 <= month_input <= 12 else 1
        else:
            # Años anteriores: permitir cualquier mes válido
            month = month_input if 1 <= month_input <= 12 else 1
        
        category = (form.category.data or "").strip()
        description = (form.description.data or "").strip()
        amount = float(form.amount.data or 0)

        # Validaciones
        form.branch_name.data = branch_name
        if hasattr(form, "validate_for_user"):
            form.validate_for_user(current_user)

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
                is_paid=False,
                created_by=getattr(current_user, "id", None)
            )
            db.session.add(row)
        else:
            if row.is_paid:
                raise ValueError("Este gasto ya fue marcado como pagado y no puede modificarse.")
            row.amount = amount
            row.updated_at = datetime.utcnow()

        db.session.commit()
        flash("Gasto guardado correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error guardando el gasto: {e}", "error")
        # En caso de error, volver al mismo contexto
        year = int(request.form.get('year', today.year))
        month = int(form.month.data) if form.month.data else today.month

    # Redirigir al mismo año y mes donde se estaba trabajando
    params = {"year": year, "month": month}
    if _is_admin() and form.branch_name.data:
        params["branch"] = form.branch_name.data
    return redirect(url_for("expenses.index", **params))


def _month_name_spanish(month_number):
    months = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    return months.get(month_number, "")


@expenses_bp.post('/<int:expense_id>/mark-paid')
@login_required
def mark_paid(expense_id):
    """
    Marcar un gasto como pagado.
    VERSIÓN MEJORADA: Requiere que exista el registro diario primero.
    """
    from app.models.daily_record import DailyRecord
    from datetime import date
    
    row = BranchExpense.query.get_or_404(expense_id)

    # Verificar permisos
    if _is_admin():
        can = True
    elif _is_branch() and getattr(current_user, "branch_name", None) == row.branch_name:
        can = BranchExpense.can_edit_category(current_user, row.branch_name, row.category)
    else:
        can = False

    if not can:
        abort(403)

    if row.is_paid:
        return jsonify({"status": "error", "message": "El gasto ya está pagado."}), 400

    # NUEVA VALIDACIÓN: Verificar si existe el registro diario de hoy
    if _is_branch():  # Solo aplicar esta validación a usuarios de sucursal
        today = date.today()
        daily_record_exists = DailyRecord.query.filter_by(
            branch_name=current_user.branch_name,
            record_date=today
        ).first()
        
        if not daily_record_exists:
            return jsonify({
                "status": "error", 
                "message": "⚠️ Debes crear el registro diario de hoy antes de marcar gastos como pagados. Por favor, carga primero las ventas del día.",
                "redirect": "/daily-records/create"  # Opcional: para redirigir
            }), 400

    try:
        row.mark_paid_for_today(getattr(current_user, "id", None))
        db.session.commit()
        return jsonify({
            "status": "ok",
            "is_paid": True,
            "paid_at": row.paid_at.isoformat() if row.paid_at else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@expenses_bp.route("/toggle/<int:expense_id>", methods=["POST"])
@login_required
def toggle_paid(expense_id: int):
    """
    Toggle del estado pagado de un gasto.
    VERSIÓN MEJORADA: Requiere que exista el registro diario primero.
    """
    from app.models.daily_record import DailyRecord
    from datetime import date
    
    row = BranchExpense.query.get_or_404(expense_id)

    # Verificar permisos
    if _is_admin():
        can = True
    elif _is_branch() and getattr(current_user, "branch_name", None) == row.branch_name:
        can = BranchExpense.can_edit_category(current_user, row.branch_name, row.category)
    else:
        can = False

    if not can:
        abort(403)

    try:
        if row.is_paid:
            return jsonify({"status": "error", "message": "El gasto ya está pagado y no se puede desmarcar."}), 400
        else:
            # NUEVA VALIDACIÓN: Verificar si existe el registro diario de hoy
            if _is_branch():  # Solo aplicar esta validación a usuarios de sucursal
                today = date.today()
                daily_record_exists = DailyRecord.query.filter_by(
                    branch_name=current_user.branch_name,
                    record_date=today
                ).first()
                
                if not daily_record_exists:
                    return jsonify({
                        "status": "error", 
                        "message": "⚠️ Debes crear el registro diario de hoy antes de marcar gastos como pagados. Por favor, carga primero las ventas del día.",
                        "redirect": "/daily-records/create"
                    }), 400
            
            row.mark_paid_for_today(getattr(current_user, "id", None))
            db.session.commit()
            return jsonify({"status": "ok", "is_paid": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400