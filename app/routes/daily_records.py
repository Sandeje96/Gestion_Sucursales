# app/routes/daily_records.py
"""
Blueprint para el manejo de registros diarios de ventas y gastos.

Este módulo contiene las rutas para:
- Listar registros diarios
- Crear nuevos registros
- Editar registros existentes
- Eliminar registros
- Verificar registros (solo admins)
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, extract, func
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar

from app import db
from app.models.user import User
from app.models.daily_record import DailyRecord
from app.forms.daily_record_forms import DailyRecordForm, FilterForm, QuickStatsForm, BulkActionForm

# Crear el Blueprint
daily_records_bp = Blueprint('daily_records', __name__)


@daily_records_bp.route('/')
@daily_records_bp.route('/index')
@login_required
def index():
    """
    Página principal de registros diarios.
    Muestra diferentes vistas según el rol del usuario.
    """
    page = request.args.get('page', 1, type=int)
    
    # Formulario de filtros
    filter_form = FilterForm()
    
    # Construir query base
    if current_user.is_admin_user():
        # Admins ven todos los registros
        query = DailyRecord.query
    else:
        # Usuarios de sucursal solo ven sus registros
        query = current_user.daily_records
    
    # Aplicar filtros si se enviaron
    if request.args.get('start_date'):
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            query = query.filter(DailyRecord.record_date >= start_date)
        except ValueError:
            pass
    
    if request.args.get('end_date'):
        try:
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            query = query.filter(DailyRecord.record_date <= end_date)
        except ValueError:
            pass
    
    if request.args.get('branch_filter') and current_user.is_admin_user():
        branch_name = request.args.get('branch_filter')
        query = query.filter(DailyRecord.branch_name == branch_name)
    
    # Ordenar por fecha descendente
    query = query.order_by(desc(DailyRecord.record_date))
    
    # Paginación
    records = query.paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    # Estadísticas rápidas
    today = date.today()
    stats = get_quick_stats(current_user, today)
    
    return render_template(
        'daily_records/index.html',
        title='Registros Diarios',
        records=records,
        filter_form=filter_form,
        stats=stats
    )


@daily_records_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Crear un nuevo registro diario.
    """
    form = DailyRecordForm()
    
    if form.validate_on_submit():
        # Convertir record_date a date si es string
        record_date = form.record_date.data
        if isinstance(record_date, str):
            record_date = datetime.strptime(record_date, "%Y-%m-%d").date()
        
        # Verificar que no exista un registro para esta fecha y sucursal
        existing_record = DailyRecord.get_by_branch_and_date(
            current_user.branch_name,
            record_date
        )
        
        if existing_record:
            flash(
                f'Ya existe un registro para {current_user.branch_name} '
                f'en la fecha {record_date.strftime("%d/%m/%Y")}. '
                'Puedes editarlo desde la lista de registros.',
                'warning'
            )
            return redirect(url_for('daily_records.edit', id=existing_record.id))
        
        try:
            # Crear nuevo registro
            record = DailyRecord(
                user_id=current_user.id,
                branch_name=current_user.branch_name,
                record_date=record_date,
                cash_sales=form.cash_sales.data,
                mercadopago_sales=form.mercadopago_sales.data,
                debit_sales=form.debit_sales.data,
                credit_sales=form.credit_sales.data,
                total_expenses=form.total_expenses.data,
                notes=form.notes.data
            )
            
            # El total de ventas se calcula automáticamente en el modelo
            record.calculate_total_sales()
            
            db.session.add(record)
            db.session.commit()
            
            flash(
                f'Registro del {record.record_date.strftime("%d/%m/%Y")} '
                f'creado exitosamente. Total de ventas: ${record.total_sales:.2f}',
                'success'
            )
            
            return redirect(url_for('main.branch_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el registro: {str(e)}', 'error')
    
    return render_template(
        'daily_records/create.html',
        title='Crear Registro Diario',
        form=form
    )


@daily_records_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """
    Editar un registro diario existente.
    """
    record = DailyRecord.query.get_or_404(id)
    
    # Verificar permisos
    if not current_user.can_edit_record(record):
        abort(403)
    
    form = DailyRecordForm(obj=record)
    
    if form.validate_on_submit():
        try:
            # Actualizar campos
            record.record_date = form.record_date.data
            record.cash_sales = form.cash_sales.data
            record.mercadopago_sales = form.mercadopago_sales.data
            record.debit_sales = form.debit_sales.data
            record.credit_sales = form.credit_sales.data
            record.total_expenses = form.total_expenses.data
            record.notes = form.notes.data
            
            # Recalcular total
            record.calculate_total_sales()
            
            # Si era verificado y se editó, desverificar
            if record.is_verified and not current_user.is_admin_user():
                record.unverify_record()
                flash(
                    'El registro ha sido editado y ya no está verificado. '
                    'Un administrador deberá verificarlo nuevamente.',
                    'info'
                )
            
            db.session.commit()
            
            flash(
                f'Registro del {record.record_date.strftime("%d/%m/%Y")} '
                'actualizado exitosamente.',
                'success'
            )
            
            return redirect(url_for('daily_records.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el registro: {str(e)}', 'error')
    
    return render_template(
        'daily_records/edit.html',
        title='Editar Registro Diario',
        form=form,
        record=record
    )


@daily_records_bp.route('/view/<int:id>')
@login_required
def view(id):
    """
    Ver detalles de un registro diario.
    """
    record = DailyRecord.query.get_or_404(id)
    
    # Verificar permisos
    if not current_user.can_view_record(record):
        abort(403)
    
    return render_template(
        'daily_records/view.html',
        title=f'Registro del {record.record_date.strftime("%d/%m/%Y")}',
        record=record
    )


@daily_records_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """
    Eliminar un registro diario.
    """
    record = DailyRecord.query.get_or_404(id)
    
    # Solo el creador o un admin pueden eliminar
    if not current_user.can_edit_record(record):
        abort(403)
    
    try:
        db.session.delete(record)
        db.session.commit()
        
        flash(
            f'Registro del {record.record_date.strftime("%d/%m/%Y")} '
            'eliminado exitosamente.',
            'success'
        )
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el registro: {str(e)}', 'error')
    
    return redirect(url_for('daily_records.index'))


@daily_records_bp.route('/verify/<int:id>', methods=['POST'])
@login_required
def verify(id):
    """
    Verificar un registro diario (solo administradores).
    """
    if not current_user.is_admin_user():
        abort(403)
    
    record = DailyRecord.query.get_or_404(id)
    
    try:
        if record.is_verified:
            record.unverify_record()
            action = 'desverificado'
        else:
            record.verify_record(current_user)
            action = 'verificado'
        
        db.session.commit()
        
        flash(
            f'Registro del {record.record_date.strftime("%d/%m/%Y")} '
            f'{action} exitosamente.',
            'success'
        )
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al verificar el registro: {str(e)}', 'error')
    
    return redirect(url_for('daily_records.index'))


@daily_records_bp.route('/stats')
@login_required
def stats():
    """
    Página de estadísticas detalladas.
    """
    form = QuickStatsForm()
    
    # Período por defecto: este mes
    today = date.today()
    start_date = today.replace(day=1)
    end_date = today
    
    # Si se envió el formulario, usar esos datos
    if request.args.get('period'):
        period = request.args.get('period')
        start_date, end_date = get_period_dates(period, request.args)
    
    # Obtener estadísticas
    stats_data = get_detailed_stats(current_user, start_date, end_date)
    
    return render_template(
        'daily_records/stats.html',
        title='Estadísticas',
        form=form,
        stats=stats_data,
        start_date=start_date,
        end_date=end_date
    )


@daily_records_bp.route('/api/daily-totals')
@login_required
def api_daily_totals():
    """
    API endpoint para obtener totales diarios (para gráficos).
    """
    days = request.args.get('days', 30, type=int)
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    # Construir query según permisos
    if current_user.is_admin_user():
        query = DailyRecord.query
    else:
        query = current_user.daily_records
    
    # Filtrar por fecha
    records = query.filter(
        DailyRecord.record_date.between(start_date, end_date)
    ).order_by(DailyRecord.record_date).all()
    
    # Agrupar por fecha
    daily_totals = {}
    for record in records:
        date_str = record.record_date.isoformat()
        if date_str not in daily_totals:
            daily_totals[date_str] = {
                'date': date_str,
                'total_sales': 0,
                'total_expenses': 0,
                'net_amount': 0,
                'records_count': 0
            }
        
        daily_totals[date_str]['total_sales'] += float(record.total_sales)
        daily_totals[date_str]['total_expenses'] += float(record.total_expenses)
        daily_totals[date_str]['net_amount'] += record.get_net_amount()
        daily_totals[date_str]['records_count'] += 1
    
    return jsonify({
        'status': 'success',
        'data': list(daily_totals.values())
    })


@daily_records_bp.route('/api/payment-breakdown')
@login_required
def api_payment_breakdown():
    """
    API endpoint para obtener desglose de métodos de pago.
    """
    days = request.args.get('days', 30, type=int)
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    # Construir query según permisos
    if current_user.is_admin_user():
        query = DailyRecord.query
    else:
        query = current_user.daily_records
    
    # Obtener totales por método de pago
    result = query.filter(
        DailyRecord.record_date.between(start_date, end_date)
    ).with_entities(
        func.sum(DailyRecord.cash_sales).label('cash'),
        func.sum(DailyRecord.mercadopago_sales).label('mercadopago'),
        func.sum(DailyRecord.debit_sales).label('debit'),
        func.sum(DailyRecord.credit_sales).label('credit')
    ).first()
    
    breakdown = {
        'cash': float(result.cash or 0),
        'mercadopago': float(result.mercadopago or 0),
        'debit': float(result.debit or 0),
        'credit': float(result.credit or 0)
    }
    
    return jsonify({
        'status': 'success',
        'data': breakdown
    })


# Funciones auxiliares
def get_quick_stats(user, target_date):
    """
    Obtener estadísticas rápidas para el dashboard.
    """
    # Query base según permisos
    if user.is_admin_user():
        base_query = DailyRecord.query
    else:
        base_query = user.daily_records
    
    # Estadísticas del día
    today_records = base_query.filter(
        DailyRecord.record_date == target_date
    ).all()
    
    # Estadísticas del mes
    month_start = target_date.replace(day=1)
    month_records = base_query.filter(
        DailyRecord.record_date >= month_start,
        DailyRecord.record_date <= target_date
    ).all()
    
    return {
        'today': {
            'records_count': len(today_records),
            'total_sales': sum(float(r.total_sales) for r in today_records),
            'total_expenses': sum(float(r.total_expenses) for r in today_records),
            'net_amount': sum(r.get_net_amount() for r in today_records)
        },
        'month': {
            'records_count': len(month_records),
            'total_sales': sum(float(r.total_sales) for r in month_records),
            'total_expenses': sum(float(r.total_expenses) for r in month_records),
            'net_amount': sum(r.get_net_amount() for r in month_records)
        }
    }


def get_detailed_stats(user, start_date, end_date):
    """
    Obtener estadísticas detalladas para un período.
    """
    # Query base según permisos
    if user.is_admin_user():
        base_query = DailyRecord.query
    else:
        base_query = user.daily_records
    
    # Filtrar por período
    records = base_query.filter(
        DailyRecord.record_date.between(start_date, end_date)
    ).all()
    
    if not records:
        return None
    
    # Calcular totales
    total_sales = sum(float(r.total_sales) for r in records)
    total_expenses = sum(float(r.total_expenses) for r in records)
    
    # Desglose por método de pago
    payment_breakdown = {
        'cash': sum(float(r.cash_sales) for r in records),
        'mercadopago': sum(float(r.mercadopago_sales) for r in records),
        'debit': sum(float(r.debit_sales) for r in records),
        'credit': sum(float(r.credit_sales) for r in records)
    }
    
    # Estadísticas por sucursal (solo para admins)
    branch_stats = {}
    if user.is_admin_user():
        for record in records:
            branch = record.branch_name
            if branch not in branch_stats:
                branch_stats[branch] = {
                    'records_count': 0,
                    'total_sales': 0,
                    'total_expenses': 0,
                    'net_amount': 0
                }
            
            branch_stats[branch]['records_count'] += 1
            branch_stats[branch]['total_sales'] += float(record.total_sales)
            branch_stats[branch]['total_expenses'] += float(record.total_expenses)
            branch_stats[branch]['net_amount'] += record.get_net_amount()
    
    return {
        'period': {
            'start_date': start_date,
            'end_date': end_date,
            'days_count': (end_date - start_date).days + 1
        },
        'totals': {
            'records_count': len(records),
            'total_sales': total_sales,
            'total_expenses': total_expenses,
            'net_amount': total_sales - total_expenses,
            'avg_daily_sales': total_sales / len(set(r.record_date for r in records))
        },
        'payment_breakdown': payment_breakdown,
        'branch_stats': branch_stats
    }


def get_period_dates(period, args):
    """
    Convertir un período seleccionado a fechas de inicio y fin.
    """
    today = date.today()
    
    if period == 'today':
        return today, today
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == 'last_week':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    elif period == 'this_month':
        start = today.replace(day=1)
        return start, today
    elif period == 'last_month':
        if today.month == 1:
            start = date(today.year - 1, 12, 1)
            end = date(today.year - 1, 12, 31)
        else:
            start = date(today.year, today.month - 1, 1)
            _, last_day = calendar.monthrange(today.year, today.month - 1)
            end = date(today.year, today.month - 1, last_day)
        return start, end
    elif period == 'this_year':
        start = date(today.year, 1, 1)
        return start, today
    elif period == 'custom':
        start = datetime.strptime(args.get('custom_start'), '%Y-%m-%d').date()
        end = datetime.strptime(args.get('custom_end'), '%Y-%m-%d').date()
        return start, end
    else:
        return today, today