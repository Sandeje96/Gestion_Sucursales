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
import datetime
import calendar
import pytz
from decimal import Decimal

from app import db
from app.models.user import User
from app.models.daily_record import DailyRecord
from app.forms.daily_record_forms import DailyRecordForm, FilterForm, QuickStatsForm, BulkActionForm

# Crear el Blueprint
daily_records_bp = Blueprint('daily_records', __name__)

# Zona horaria fija para toda la app (puedes obtenerla de config si prefieres)
TZ_ARG = pytz.timezone('America/Argentina/Buenos_Aires')

def get_today_arg():
    """
    Obtener la fecha actual en zona horaria argentina.
    
    Returns:
        date: Fecha actual en Argentina (UTC-3)
    """
    tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
    return datetime.datetime.now(tz_arg).date()

def get_yesterday_arg():
    """
    Obtener la fecha de ayer en zona horaria argentina.
    
    Returns:
        date: Fecha de ayer en Argentina (UTC-3)
    """
    today = get_today_arg()
    return today - datetime.timedelta(days=1)

def get_display_date_for_dashboard():
    """
    Determinar qué fecha mostrar en el dashboard según la nueva lógica:
    - Si no hay registros de hoy, mostrar los de ayer
    - Si hay registros de hoy, mostrar los de hoy
    
    Returns:
        tuple: (fecha_a_mostrar, es_dia_anterior, etiqueta_display)
    """
    from app.models.daily_record import DailyRecord
    
    today = get_today_arg()
    yesterday = get_yesterday_arg()
    
    # Verificar si hay registros del día actual
    todays_records_count = DailyRecord.query.filter(
        DailyRecord.record_date == today
    ).count()
    
    if todays_records_count == 0:
        # No hay registros de hoy, mostrar los de ayer
        return yesterday, True, 'AYER'
    else:
        # Hay registros de hoy, mostrar los actuales
        return today, False, 'HOY'

@daily_records_bp.route('/')
@daily_records_bp.route('/index')
@login_required
def index():
    """
    Lista principal de registros diarios.
    Muestra diferentes vistas según el rol del usuario.
    """
    page = request.args.get('page', 1, type=int)
    
    # Formulario de filtros
    filter_form = FilterForm()
    
    # Debug de parámetros recibidos
    print(f"🔍 Parámetros recibidos:")
    print(f"   start_date: {request.args.get('start_date')}")
    print(f"   end_date: {request.args.get('end_date')}")
    print(f"   branch_filter: {request.args.get('branch_filter')}")
    print(f"   page: {page}")
    
    # Construir query base
    if current_user.is_admin_user():
        # Admins ven todos los registros
        query = DailyRecord.query
        print(f"👤 Usuario admin: viendo todos los registros")
    else:
        # Usuarios de sucursal solo ven sus registros
        query = current_user.daily_records
        print(f"👤 Usuario sucursal: viendo registros de {current_user.branch_name}")
    
    # Aplicar filtros si se enviaron
    filters_applied = []
    
    # Filtro de fecha desde
    if request.args.get('start_date'):
        try:
            start_date = datetime.datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            query = query.filter(DailyRecord.record_date >= start_date)
            filters_applied.append(f"desde {start_date.strftime('%d/%m/%Y')}")
            print(f"📅 Filtro fecha desde: {start_date}")
        except ValueError as e:
            print(f"❌ Error parseando start_date: {e}")
            flash('Formato de fecha desde inválido', 'warning')

    # Filtro de fecha hasta
    if request.args.get('end_date'):
        try:
            end_date = datetime.datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            query = query.filter(DailyRecord.record_date <= end_date)
            filters_applied.append(f"hasta {end_date.strftime('%d/%m/%Y')}")
            print(f"📅 Filtro fecha hasta: {end_date}")
        except ValueError as e:
            print(f"❌ Error parseando end_date: {e}")
            flash('Formato de fecha hasta inválido', 'warning')

    # Filtro de sucursal (solo para admins)
    if request.args.get('branch_filter') and current_user.is_admin_user():
        branch_name = request.args.get('branch_filter').strip()
        if branch_name:  # Solo aplicar si no está vacío
            query = query.filter(DailyRecord.branch_name == branch_name)
            filters_applied.append(f"sucursal {branch_name}")
            print(f"🏢 Filtro sucursal: {branch_name}")
    
    # Ordenar por fecha descendente
    query = query.order_by(desc(DailyRecord.record_date))
    
    # Contar total antes de paginación para debug
    total_records = query.count()
    print(f"📊 Total de registros encontrados: {total_records}")
    
    # Paginación
    try:
        records = query.paginate(
            page=page,
            per_page=20,
            error_out=False
        )
        print(f"📄 Página {page}: {len(records.items)} registros mostrados")
    except Exception as e:
        print(f"❌ Error en paginación: {e}")
        records = query.paginate(page=1, per_page=20, error_out=False)
    
    # Mensaje informativo sobre filtros aplicados
    if filters_applied:
        filter_message = f"Filtros aplicados: {', '.join(filters_applied)}"
        print(f"✅ {filter_message}")
        if not records.items:
            flash(f'No se encontraron registros con los filtros aplicados: {", ".join(filters_applied)}', 'info')
    
    # Estadísticas rápidas
    today = get_today_arg()
    stats = get_quick_stats(current_user, today)
    
    return render_template(
        'daily_records/index.html',
        title='Registros Diarios',
        records=records,
        filter_form=filter_form,
        stats=stats,
        filters_applied=filters_applied
    )


@daily_records_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Crear un nuevo registro diario.
    """
    form = DailyRecordForm()

    # Siempre fijar la fecha de Argentina para nuevos registros en GET
    if request.method == 'GET':
        form.record_date.data = get_today_arg()
    
    if form.validate_on_submit():
        # Convertir record_date a date si es string
        record_date = form.record_date.data
        if isinstance(record_date, str):
            record_date = datetime.datetime.strptime(record_date, "%Y-%m-%d").date()
        
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
    today = get_today_arg()
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
    end_date = get_today_arg()
    start_date = end_date - datetime.timedelta(days=days-1)
    
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
    end_date = get_today_arg()
    start_date = end_date - datetime.timedelta(days=days-1)
    
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

@daily_records_bp.route('/api/cash-trays')
@login_required
def api_cash_trays():
    """
    API para obtener el estado actual de todas las bandejas.
    """
    try:
        from app.models.cash_tray import CashTray
        
        # Recalcular bandejas en tiempo real basándose en registros NO retirados
        update_trays_from_records()
        
        summary = CashTray.get_all_trays_summary()
        
        return jsonify({
            'status': 'success',
            'data': summary
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@daily_records_bp.route('/empty-all-trays', methods=['POST'])
@login_required
def empty_all_trays():
    """
    Vaciar todas las bandejas de efectivo.
    Solo administradores pueden hacer esto.
    MEJORADO: Devuelve JSON para mejor manejo en JavaScript.
    """
    if not current_user.is_admin_user():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'Solo los administradores pueden vaciar todas las bandejas.'
            }), 403
        else:
            flash('Solo los administradores pueden vaciar todas las bandejas.', 'error')
            return redirect(url_for('daily_records.index'))
    
    try:
        from app.models.cash_tray import CashTray
        
        # Vaciar todas las bandejas
        trays = CashTray.query.all()
        total_emptied = 0
        branches_emptied = []
        
        for tray in trays:
            if tray.get_total_accumulated() > 0:
                total_emptied += tray.get_total_accumulated()
                branches_emptied.append(tray.branch_name)
                tray.empty_tray()
        
        db.session.commit()
        
        # Formatear total en formato argentino
        total_formatted = f'${total_emptied:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        success_message = f'Todas las bandejas han sido vaciadas. Total retirado: {total_formatted}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': success_message,
                'data': {
                    'total_emptied': total_emptied,
                    'branches_count': len(branches_emptied),
                    'branches_emptied': branches_emptied
                }
            })
        else:
            flash(success_message, 'success')
            return redirect(url_for('daily_records.index'))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error vaciando las bandejas: {str(e)}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 500
        else:
            return redirect(url_for('daily_records.index'))


@daily_records_bp.route('/empty-branch-tray/<branch_name>', methods=['POST'])
@login_required
def empty_branch_tray(branch_name):
    """
    Vaciar la bandeja de una sucursal específica.
    MEJORADO: Devuelve JSON para mejor manejo en JavaScript.
    """
    # Verificar permisos: admins pueden vaciar cualquier bandeja,
    # usuarios de sucursal solo pueden vaciar la suya
    if not current_user.is_admin_user() and current_user.branch_name != branch_name:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'No tienes permisos para vaciar esa bandeja.'
            }), 403
        else:
            flash('No tienes permisos para vaciar esa bandeja.', 'error')
            return redirect(url_for('daily_records.index'))
    
    try:
        from app.models.cash_tray import CashTray
        
        tray = CashTray.query.filter_by(branch_name=branch_name).first()
        if not tray:
            error_message = f'No se encontró la bandeja para {branch_name}.'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 404
            else:
                flash(error_message, 'warning')
                return redirect(url_for('daily_records.index'))
        
        total_emptied = tray.get_total_accumulated()
        
        if total_emptied == 0:
            warning_message = f'La bandeja de {branch_name} ya está vacía.'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'warning',
                    'message': warning_message
                })
            else:
                flash(warning_message, 'warning')
                return redirect(url_for('daily_records.index'))
        
        tray.empty_tray()
        db.session.commit()
        
        # Formatear total en formato argentino
        total_formatted = f'${total_emptied:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        success_message = f'Bandeja de {branch_name} vaciada. Total retirado: {total_formatted}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': success_message,
                'data': {
                    'branch_name': branch_name,
                    'total_emptied': total_emptied,
                    'formatted_total': total_formatted
                }
            })
        else:
            flash(success_message, 'success')
            return redirect(url_for('daily_records.index'))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error vaciando la bandeja de {branch_name}: {str(e)}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 500
        else:
            flash(error_message, 'error')
            return redirect(url_for('daily_records.index'))


@daily_records_bp.route('/empty-record/<int:record_id>', methods=['POST'])
@login_required
def empty_record(record_id):
    """
    "Vaciar" un registro específico (marcarlo como retirado).
    MEJORADO: Devuelve JSON para mejor manejo en JavaScript.
    """
    record = DailyRecord.query.get_or_404(record_id)
    
    # Verificar permisos
    if not current_user.can_edit_record(record):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'No tienes permisos para modificar este registro.'
            }), 403
        else:
            flash('No tienes permisos para modificar este registro.', 'error')
            return redirect(url_for('daily_records.index'))
    
    # Verificar que no esté ya retirado
    if record.is_withdrawn:
        warning_message = f'El registro del {record.record_date.strftime("%d/%m/%Y")} ya fue retirado anteriormente.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'warning',
                'message': warning_message
            })
        else:
            flash(warning_message, 'warning')
            return redirect(url_for('daily_records.index'))
    
    try:
        from app.models.cash_tray import CashTray
        
        # Marcar el registro como retirado
        record.mark_as_withdrawn(current_user)
        
        # Actualizar la bandeja correspondiente
        tray = CashTray.query.filter_by(branch_name=record.branch_name).first()
        if tray:
            tray.subtract_amounts(
                cash=record.cash_sales or 0,
                mercadopago=record.mercadopago_sales or 0,
                debit=record.debit_sales or 0,
                credit=record.credit_sales or 0
            )
        
        db.session.commit()
        
        total_removed = (
            float(record.cash_sales or 0) +
            float(record.mercadopago_sales or 0) +
            float(record.debit_sales or 0) +
            float(record.credit_sales or 0)
        )
        
        # Formatear total en formato argentino
        total_formatted = f'${total_removed:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        success_message = f'Registro del {record.record_date.strftime("%d/%m/%Y")} retirado de la bandeja. Total: {total_formatted}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': success_message,
                'data': {
                    'record_id': record_id,
                    'record_date': record.record_date.strftime("%d/%m/%Y"),
                    'branch_name': record.branch_name,
                    'total_removed': total_removed,
                    'formatted_total': total_formatted
                }
            })
        else:
            flash(success_message, 'success')
            return redirect(url_for('daily_records.index'))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error procesando el retiro: {str(e)}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 500
        else:
            flash(error_message, 'error')


@daily_records_bp.route('/recalculate-trays', methods=['POST'])
@login_required
def recalculate_trays():
    """
    Recalcular todas las bandejas desde cero.
    MEJORADO: Devuelve JSON para mejor manejo en JavaScript.
    """
    if not current_user.is_admin_user():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'Solo los administradores pueden recalcular las bandejas.'
            }), 403
        else:
            flash('Solo los administradores pueden recalcular las bandejas.', 'error')
            return redirect(url_for('daily_records.index'))
    
    try:
        update_trays_from_records()
        success_message = 'Todas las bandejas han sido recalculadas correctamente.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': success_message
            })
        else:
            flash(success_message, 'success')
            return redirect(url_for('daily_records.index'))
        
    except Exception as e:
        error_message = f'Error recalculando las bandejas: {str(e)}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 500
        else:
            flash(error_message, 'error')
            return redirect(url_for('daily_records.index'))
        
# NUEVA FUNCIÓN: API para verificar estado de bandeja específica
@daily_records_bp.route('/api/branch-tray-status/<branch_name>')
@login_required
def api_branch_tray_status(branch_name):
    """
    API para obtener el estado actual de una bandeja específica.
    Útil para actualizaciones en tiempo real.
    """
    try:
        from app.models.cash_tray import CashTray
        
        # Verificar permisos
        if not current_user.is_admin_user() and current_user.branch_name != branch_name:
            return jsonify({
                'status': 'error',
                'message': 'No tienes permisos para consultar esa bandeja.'
            }), 403
        
        tray = CashTray.query.filter_by(branch_name=branch_name).first()
        
        if not tray:
            return jsonify({
                'status': 'error',
                'message': f'No se encontró la bandeja para {branch_name}.'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': {
                'branch_name': tray.branch_name,
                'accumulated_cash': float(tray.accumulated_cash or 0),
                'accumulated_mercadopago': float(tray.accumulated_mercadopago or 0),
                'accumulated_debit': float(tray.accumulated_debit or 0),
                'accumulated_credit': float(tray.accumulated_credit or 0),
                'total_accumulated': tray.get_total_accumulated(),
                'last_updated': tray.last_updated.isoformat() if tray.last_updated else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        

# Funciones auxiliares

def update_trays_from_records():
    """
    Actualizar todas las bandejas basándose en los registros NO retirados.
    """
    from app.models.cash_tray import CashTray
    
    try:
        # Obtener todas las sucursales que tienen registros
        branches = db.session.query(DailyRecord.branch_name).distinct().all()
        
        for (branch_name,) in branches:
            # Obtener o crear bandeja para la sucursal
            tray = CashTray.query.filter_by(branch_name=branch_name).first()
            if not tray:
                tray = CashTray(branch_name=branch_name)
                db.session.add(tray)
            
            # Calcular totales de registros NO retirados
            records = DailyRecord.query.filter_by(
                branch_name=branch_name,
                is_withdrawn=False
            ).all()
            
            # Resetear y recalcular
            tray.accumulated_cash = sum(float(r.cash_sales or 0) for r in records)
            tray.accumulated_mercadopago = sum(float(r.mercadopago_sales or 0) for r in records)
            tray.accumulated_debit = sum(float(r.debit_sales or 0) for r in records)
            tray.accumulated_credit = sum(float(r.credit_sales or 0) for r in records)
            tray.last_updated = datetime.datetime.now()
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Error actualizando bandejas: {e}")

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
            'avg_daily_sales': total_sales / len(set(r.record_date for r in records)) if records else 0
        },
        'payment_breakdown': payment_breakdown,
        'branch_stats': branch_stats
    }


def get_period_dates(period, args):
    """
    Convertir un período seleccionado a fechas de inicio y fin.
    """
    today = get_today_arg()
    
    if period == 'today':
        return today, today
    elif period == 'yesterday':
        yesterday = today - datetime.timedelta(days=1)
        return yesterday, yesterday
    elif period == 'this_week':
        start = today - datetime.timedelta(days=today.weekday())
        return start, today
    elif period == 'last_week':
        start = today - datetime.timedelta(days=today.weekday() + 7)
        end = start + datetime.timedelta(days=6)
        return start, end
    elif period == 'this_month':
        start = today.replace(day=1)
        return start, today
    elif period == 'last_month':
        if today.month == 1:
            start = datetime.date(today.year - 1, 12, 1)
            end = datetime.date(today.year - 1, 12, 31)
        else:
            start = datetime.date(today.year, today.month - 1, 1)
            _, last_day = calendar.monthrange(today.year, today.month - 1)
            end = datetime.date(today.year, today.month - 1, last_day)
        return start, end
    elif period == 'this_year':
        start = datetime.date(today.year, 1, 1)
        return start, today
    elif period == 'custom':
        start = datetime.datetime.strptime(args.get('custom_start'), '%Y-%m-%d').date()
        end = datetime.datetime.strptime(args.get('custom_end'), '%Y-%m-%d').date()
        return start, end
    else:
        return today, today