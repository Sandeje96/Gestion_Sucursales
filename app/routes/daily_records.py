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
from app.models.cash_tray import CashTray
import time
import traceback

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
    CORREGIDO: Con normalización de nombres de sucursales.
    """
    page = request.args.get('page', 1, type=int)
    
    # Formulario de filtros
    filter_form = FilterForm()
    
    # Debug de parámetros recibidos
    print(f"🔍 Parámetros recibidos:")
    print(f"   start_date: {request.args.get('start_date')}")
    print(f"   end_date: {request.args.get('end_date')}")
    print(f"   branch_filter: '{request.args.get('branch_filter')}'")
    print(f"   page: {page}")
    
    # Construir query base
    if current_user.is_admin_user():
        query = DailyRecord.query
        print(f"👤 Usuario admin: viendo todos los registros")
    else:
        query = current_user.daily_records
        print(f"👤 Usuario sucursal: viendo registros de {current_user.branch_name}")
    
    # Aplicar filtros
    filters_applied = []
    has_explicit_filters = False
    
    # Filtro de fecha desde
    start_date_param = request.args.get('start_date')
    if start_date_param:
        has_explicit_filters = True
        try:
            start_date = datetime.datetime.strptime(start_date_param, '%Y-%m-%d').date()
            query = query.filter(DailyRecord.record_date >= start_date)
            filters_applied.append(f"desde {start_date.strftime('%d/%m/%Y')}")
            print(f"📅 Filtro fecha desde: {start_date}")
        except ValueError as e:
            print(f"❌ Error parseando start_date: {e}")
            flash('Formato de fecha desde inválido', 'warning')

    # Filtro de fecha hasta
    end_date_param = request.args.get('end_date')
    if end_date_param:
        has_explicit_filters = True
        try:
            end_date = datetime.datetime.strptime(end_date_param, '%Y-%m-%d').date()
            query = query.filter(DailyRecord.record_date <= end_date)
            filters_applied.append(f"hasta {end_date.strftime('%d/%m/%Y')}")
            print(f"📅 Filtro fecha hasta: {end_date}")
        except ValueError as e:
            print(f"❌ Error parseando end_date: {e}")
            flash('Formato de fecha hasta inválido', 'warning')

    # CORRECCIÓN: Filtro de sucursal con normalización
    branch_filter_param = request.args.get('branch_filter')
    if branch_filter_param and current_user.is_admin_user():
        branch_name_input = branch_filter_param.strip()
        print(f"🏢 Input original: '{branch_name_input}'")
        
        if branch_name_input:
            has_explicit_filters = True
            
            # Normalizar el nombre de entrada
            normalized_input = normalize_branch_name(branch_name_input)
            print(f"🏢 Nombre normalizado: '{normalized_input}'")
            
            # Buscar registros que coincidan con el nombre normalizado
            # Usar una consulta más flexible que maneje variaciones
            subquery = db.session.query(DailyRecord.branch_name).distinct().all()
            matching_branches = []
            
            for (db_branch_name,) in subquery:
                if db_branch_name and normalize_branch_name(db_branch_name) == normalized_input:
                    matching_branches.append(db_branch_name)
            
            print(f"🏢 Sucursales coincidentes en BD: {matching_branches}")
            
            if matching_branches:
                # Filtrar por cualquiera de las variaciones encontradas
                query = query.filter(DailyRecord.branch_name.in_(matching_branches))
                filters_applied.append(f"sucursal {normalized_input}")
                print(f"✅ Filtro sucursal aplicado para: {matching_branches}")
            else:
                print(f"⚠️ No se encontraron registros para sucursal '{normalized_input}'")
                flash(f'No se encontraron registros para la sucursal "{normalized_input}".', 'info')
    
    # Solo aplicar filtro por defecto si NO hay filtros explícitos
    if not has_explicit_filters:
        today = get_today_arg()
        default_start_date = today.replace(day=1)
        query = query.filter(DailyRecord.record_date >= default_start_date)
        query = query.filter(DailyRecord.record_date <= today)
        print(f"📅 Sin filtros explícitos: mostrando mes actual ({default_start_date} - {today})")
    
    # Ordenar por fecha descendente
    query = query.order_by(desc(DailyRecord.record_date))
    
    # Contar total después de filtros
    total_records = query.count()
    print(f"📊 Total registros después de filtros: {total_records}")
    
    # Paginación
    try:
        records = query.paginate(
            page=page,
            per_page=50,
            error_out=False
        )
        print(f"📄 Página {page}: {len(records.items)} registros mostrados de {total_records} totales")
    except Exception as e:
        print(f"❌ Error en paginación: {e}")
        records = query.paginate(page=1, per_page=50, error_out=False)
    
    # Mensaje informativo
    if filters_applied:
        filter_message = f"Filtros aplicados: {', '.join(filters_applied)}"
        print(f"✅ {filter_message}")
        if not records.items:
            flash(f'No se encontraron registros con los filtros aplicados: {", ".join(filters_applied)}', 'info')
    else:
        if not records.items and not has_explicit_filters:
            flash(f'No hay registros disponibles para el mes actual', 'info')
    
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
        
        trays = CashTray.query.all()
        total_emptied = 0
        branches_emptied = []
        
        for tray in trays:
            if tray.get_total_accumulated() > 0:
                total_emptied += tray.get_total_accumulated()
                branches_emptied.append(tray.branch_name)
                tray.empty_tray()
        
        db.session.commit()
        
        success_message = f'Todas las bandejas han sido vaciadas. Total retirado: ${total_emptied:,.2f}'
        
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
            flash(error_message, 'error')
            return redirect(url_for('daily_records.index'))


@daily_records_bp.route('/empty-branch-tray/<branch_name>', methods=['POST'])
@login_required
def empty_branch_tray(branch_name):
    """
    Vaciar la bandeja de una sucursal específica.
    CORREGIDO: Con normalización de nombres de sucursales.
    """
    # Log para debug
    print(f"🗑️ [DEBUG] Intentando vaciar bandeja de: '{branch_name}'")
    print(f"📧 Usuario actual: {current_user.username}, Admin: {current_user.is_admin_user()}")
    print(f"🏢 Sucursal del usuario: {current_user.branch_name}")
    
    # CORRECCIÓN: Normalizar el nombre de la sucursal recibida
    normalized_branch_name = normalize_branch_name(branch_name)
    print(f"🏢 [DEBUG] Nombre normalizado: '{normalized_branch_name}'")
    
    # Verificar permisos: admins pueden vaciar cualquier bandeja,
    # usuarios de sucursal solo pueden vaciar la suya
    user_branch_normalized = normalize_branch_name(current_user.branch_name) if current_user.branch_name else None
    
    if not current_user.is_admin_user() and user_branch_normalized != normalized_branch_name:
        error_message = 'No tienes permisos para vaciar esa bandeja.'
        print(f"❌ [DEBUG] {error_message}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': error_message
            }), 403
        else:
            flash(error_message, 'error')
            return redirect(url_for('daily_records.index'))
    
    try:
        from app.models.cash_tray import CashTray
        
        # CORRECCIÓN: Buscar registros que coincidan con el nombre normalizado
        all_branches = db.session.query(DailyRecord.branch_name).distinct().all()
        matching_db_branches = []
        
        for (db_branch_name,) in all_branches:
            if db_branch_name and normalize_branch_name(db_branch_name) == normalized_branch_name:
                matching_db_branches.append(db_branch_name)
        
        print(f"🏢 [DEBUG] Sucursales coincidentes en BD: {matching_db_branches}")
        
        if not matching_db_branches:
            error_message = f'No se encontraron registros para la sucursal {normalized_branch_name}.'
            print(f"❌ [DEBUG] {error_message}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'error',
                    'message': error_message
                }), 404
            else:
                flash(error_message, 'warning')
                return redirect(url_for('daily_records.index'))
        
        # CORRECCIÓN: Buscar registros NO retirados de todas las variaciones
        records_to_withdraw = DailyRecord.query.filter(
            DailyRecord.branch_name.in_(matching_db_branches),
            DailyRecord.is_withdrawn == False
        ).all()
        
        print(f"📊 [DEBUG] Registros NO retirados encontrados: {len(records_to_withdraw)}")
        
        if not records_to_withdraw:
            warning_message = f'La bandeja de {normalized_branch_name} ya está vacía.'
            print(f"⚠️ [DEBUG] {warning_message}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'warning',
                    'message': warning_message
                })
            else:
                flash(warning_message, 'warning')
                return redirect(url_for('daily_records.index'))
        
        # CORRECCIÓN: Calcular total antes de vaciar
        total_emptied = 0
        for record in records_to_withdraw:
            total_emptied += (
                float(record.cash_sales or 0) +
                float(record.mercadopago_sales or 0) +
                float(record.debit_sales or 0) +
                float(record.credit_sales or 0)
            )
        
        print(f"💰 [DEBUG] Total a vaciar: ${total_emptied:.2f}")
        
        # PASO CRÍTICO: Marcar registros como retirados
        print(f"🔄 [DEBUG] Marcando {len(records_to_withdraw)} registros como retirados...")
        
        for record in records_to_withdraw:
            record.mark_as_withdrawn(current_user)
            print(f"✅ [DEBUG] Registro {record.id} del {record.record_date} ({record.branch_name}) marcado como retirado")
        
        # CORRECCIÓN: Actualizar bandejas de todas las variaciones encontradas
        for db_branch_name in matching_db_branches:
            tray = CashTray.query.filter_by(branch_name=db_branch_name).first()
            if tray:
                print(f"🔄 [DEBUG] Vaciando bandeja física: {db_branch_name}")
                tray.empty_tray()
        
        # Confirmar cambios
        db.session.commit()
        print(f"✅ [DEBUG] Cambios confirmados en base de datos")
        
        # Formatear total en formato argentino
        total_formatted = f'${total_emptied:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        success_message = f'Bandeja de {normalized_branch_name} vaciada. Total retirado: {total_formatted}'
        print(f"🎉 [DEBUG] {success_message}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': success_message,
                'data': {
                    'branch_name': normalized_branch_name,
                    'total_emptied': total_emptied,
                    'formatted_total': total_formatted,
                    'records_withdrawn': len(records_to_withdraw),
                    'db_branches_affected': matching_db_branches
                }
            })
        else:
            flash(success_message, 'success')
            return redirect(url_for('daily_records.index'))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error vaciando la bandeja de {normalized_branch_name}: {str(e)}'
        print(f"❌ [DEBUG] {error_message}")
        print(f"🐛 [DEBUG] Traceback: {traceback.format_exc()}")
        
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
                credit=record.credit_sales or 0,
                cash_expenses=record.total_expenses or 0  # ✅ AGREGADO: Incluir gastos
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

# FUNCIÓN CORREGIDA: API integrado sin parámetros incorrectos    
@daily_records_bp.route('/api/integrated-dashboard')
@login_required  
def api_integrated_dashboard():
    """
    CORREGIDO: API endpoint optimizado sin errores de funciones inexistentes.
    """
    import time
    start_time = time.time()
    
    try:
        print("🚀 [OPTIMIZED] API integrated dashboard llamado...")
        
        # Parámetros de filtro
        start_date_param = request.args.get('start_date')
        end_date_param = request.args.get('end_date')
        branch_filter = request.args.get('branch_filter')
        
        # Convertir fechas rápidamente
        start_date = None
        end_date = None
        
        if start_date_param:
            try:
                start_date = datetime.datetime.strptime(start_date_param, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if end_date_param:
            try:
                end_date = datetime.datetime.strptime(end_date_param, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Determinar modo (filtrado vs acumulado)
        is_filtered = bool(start_date or end_date or branch_filter)
        
        # CORRECCIÓN: Sin parámetros incorrectos
        if is_filtered:
            dashboard_data = get_filtered_dashboard_data(start_date, end_date, branch_filter)
        else:
            dashboard_data = get_accumulated_dashboard_data()  # SIN parámetros incorrectos
        
        execution_time = time.time() - start_time
        print(f"⚡ Dashboard cargado en {execution_time:.3f} segundos")
        
        # Respuesta optimizada
        response_data = {
            'status': 'success',
            'data': dashboard_data,
            'filters_applied': {
                'start_date': start_date_param,
                'end_date': end_date_param,
                'branch_filter': branch_filter,
                'is_filtered': is_filtered
            },
            'performance': {
                'execution_time': round(execution_time, 3),
                'records_count': len(dashboard_data.get('records', [])),
                'branches_count': len(dashboard_data.get('branch_trays', []))
            },
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"❌ Error después de {execution_time:.3f}s: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'execution_time': round(execution_time, 3),
            'timestamp': datetime.datetime.now().isoformat()
        }), 500
    
@daily_records_bp.route('/debug/branch-names')
@login_required
def debug_branch_names():
    """
    Ruta de debug para ver las inconsistencias en nombres de sucursales.
    """
    if not current_user.is_admin_user():
        abort(403)
    
    try:
        # Obtener todos los nombres únicos en la BD
        raw_branches = db.session.query(DailyRecord.branch_name).distinct().all()
        
        # Crear mapeo de nombres originales a normalizados
        branch_analysis = []
        for (original_name,) in raw_branches:
            if original_name:
                normalized = normalize_branch_name(original_name)
                count = DailyRecord.query.filter_by(branch_name=original_name).count()
                
                branch_analysis.append({
                    'original': original_name,
                    'normalized': normalized,
                    'records_count': count,
                    'needs_fix': original_name != normalized
                })
        
        # Ordenar por nombre normalizado
        branch_analysis.sort(key=lambda x: x['normalized'])
        
        return jsonify({
            'total_variations': len(branch_analysis),
            'branches': branch_analysis,
            'available_normalized': sorted(list(set(b['normalized'] for b in branch_analysis)))
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# FUNCIÓN CORREGIDA: Dashboard acumulado sin errores    
def get_accumulated_dashboard_data():
    """
    CORREGIDO: Sin parámetros incorrectos y manejo de errores robusto.
    """
    try:
        print(f"🚀 [DEBUG] Iniciando get_accumulated_dashboard_data...")
        
        # Consulta básica más simple primero
        try:
            total_records = DailyRecord.query.count()
            print(f"📊 [DEBUG] Total registros en DB: {total_records}")
        except Exception as e:
            print(f"❌ [DEBUG] Error contando registros: {e}")
            raise
        
        # Query para registros NO retirados
        try:
            query = DailyRecord.query.filter(DailyRecord.is_withdrawn == False)
            
            # Aplicar filtros de permisos
            if not current_user.is_admin_user():
                query = query.filter(DailyRecord.user_id == current_user.id)
                print(f"👤 [DEBUG] Filtrado por usuario: {current_user.branch_name}")
            
            # Obtener registros disponibles
            all_available_records = query.all()
            print(f"📊 [DEBUG] Registros NO retirados: {len(all_available_records)}")
            
        except Exception as e:
            print(f"❌ [DEBUG] Error obteniendo registros disponibles: {e}")
            # Fallback: retornar datos vacíos
            return {
                'totals': {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0},
                'branch_trays': [],
                'records': []
            }
        
        # Calcular totales
        try:
            if not all_available_records:
                totals = {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0}
                print(f"💰 [DEBUG] No hay registros disponibles")
            else:
                # NUEVO: Calcular efectivo disponible (ventas - gastos)
                total_cash_sales = sum(float(r.cash_sales or 0) for r in all_available_records)
                total_cash_expenses = sum(float(r.total_expenses or 0) for r in all_available_records)
                available_cash = total_cash_sales - total_cash_expenses
                
                totals = {
                    'cash': available_cash,  # CAMBIADO: Usar efectivo disponible
                    'mercadopago': sum(float(r.mercadopago_sales or 0) for r in all_available_records),
                    'debit': sum(float(r.debit_sales or 0) for r in all_available_records),
                    'credit': sum(float(r.credit_sales or 0) for r in all_available_records),
                }
                totals['total'] = sum(totals.values())
                print(f"💰 [DEBUG] Dinero total: ${totals['total']:,.2f}")
                print(f"💸 [DEBUG] Efectivo disponible: ${available_cash:,.2f} (Ventas: ${total_cash_sales:,.2f} - Gastos: ${total_cash_expenses:,.2f})")
        except Exception as e:
            print(f"❌ [DEBUG] Error calculando totales: {e}")
            totals = {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0}
        
        # CORRECCIÓN: Usar la función correcta
        try:
            branch_trays = get_simple_branch_data(all_available_records)
            print(f"🏪 [DEBUG] Bandejas procesadas: {len(branch_trays)}")
        except Exception as e:
            print(f"❌ [DEBUG] Error procesando bandejas: {e}")
            branch_trays = []
        
        # Lista de registros recientes - versión simplificada
        try:
            recent_query = DailyRecord.query
            if not current_user.is_admin_user():
                recent_query = recent_query.filter(DailyRecord.user_id == current_user.id)
            
            # Solo los últimos 50 registros para evitar problemas
            recent_records = recent_query.order_by(desc(DailyRecord.record_date)).limit(50).all()
            print(f"📋 [DEBUG] Registros recientes: {len(recent_records)}")
            
            records_data = []
            for r in recent_records:
                try:
                    records_data.append({
                        'id': r.id,
                        'date': r.record_date.strftime('%d/%m/%Y'),
                        'branch_name': r.branch_name,
                        'total_sales': float(r.total_sales or 0),
                        'cash_sales': float(r.cash_sales or 0),
                        'mercadopago_sales': float(r.mercadopago_sales or 0),
                        'debit_sales': float(r.debit_sales or 0),
                        'credit_sales': float(r.credit_sales or 0),
                        'total_expenses': float(r.total_expenses or 0),
                        'net_profit': float(r.total_sales or 0) - float(r.total_expenses or 0),
                        'is_verified': r.is_verified,
                        'is_withdrawn': r.is_withdrawn
                    })
                except Exception as e:
                    print(f"❌ [DEBUG] Error procesando registro {r.id}: {e}")
                    continue
            
        except Exception as e:
            print(f"❌ [DEBUG] Error obteniendo registros recientes: {e}")
            records_data = []
        
        result = {
            'totals': totals,
            'branch_trays': branch_trays,
            'records': records_data
        }
        
        print(f"✅ [DEBUG] Dashboard completado exitosamente")
        return result
        
    except Exception as e:
        print(f"❌ [DEBUG] Error crítico en get_accumulated_dashboard_data: {str(e)}")
        import traceback
        traceback.print_exc()
        # Retornar datos vacíos en caso de error crítico
        return {
            'totals': {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0},
            'branch_trays': [],
            'records': []
        }

# FUNCIÓN CORREGIDA: Procesar datos de sucursales simplificado
def get_simple_branch_data(records):
    """
    ACTUALIZADA: Incluye cálculo de gastos en efectivo para efectivo disponible.
    """
    try:
        print(f"🔄 [DEBUG] Procesando {len(records)} registros para bandejas...")
        
        branches = {}
        
        for record in records:
            try:
                # CORRECCIÓN: Normalizar el nombre de la sucursal
                original_branch = record.branch_name
                normalized_branch = normalize_branch_name(original_branch)
                
                if normalized_branch not in branches:
                    branches[normalized_branch] = {
                        'branch_name': normalized_branch,  # Usar nombre normalizado
                        'accumulated_cash': 0,
                        'accumulated_mercadopago': 0,
                        'accumulated_debit': 0,
                        'accumulated_credit': 0,
                        'accumulated_cash_expenses': 0,  # NUEVO: Gastos en efectivo
                        'available_cash': 0,  # NUEVO: Efectivo disponible
                        'total_accumulated': 0,
                        'today_sales': 0,
                        'today_expenses': 0,
                        'can_empty': current_user.is_admin_user() or normalize_branch_name(current_user.branch_name) == normalized_branch
                    }
                
                # Solo registros NO retirados
                if not record.is_withdrawn:
                    branches[normalized_branch]['accumulated_cash'] += float(record.cash_sales or 0)
                    branches[normalized_branch]['accumulated_mercadopago'] += float(record.mercadopago_sales or 0)
                    branches[normalized_branch]['accumulated_debit'] += float(record.debit_sales or 0)
                    branches[normalized_branch]['accumulated_credit'] += float(record.credit_sales or 0)
                    # NUEVO: Acumular gastos en efectivo
                    branches[normalized_branch]['accumulated_cash_expenses'] += float(record.total_expenses or 0)
                
                print(f"🔄 [DEBUG] Registro procesado: {original_branch} -> {normalized_branch}")
                
            except Exception as e:
                print(f"❌ [DEBUG] Error procesando registro {record.id}: {e}")
                continue
        
        # Calcular totales
        for branch_data in branches.values():
            try:
                # NUEVO: Calcular efectivo disponible (ventas - gastos)
                branch_data['available_cash'] = branch_data['accumulated_cash'] - branch_data['accumulated_cash_expenses']
                
                # NUEVO: Total acumulado usa efectivo disponible en lugar de efectivo bruto
                branch_data['total_accumulated'] = (
                    branch_data['available_cash'] +  # Efectivo disponible
                    branch_data['accumulated_mercadopago'] +
                    branch_data['accumulated_debit'] +
                    branch_data['accumulated_credit']
                )
                
                print(f"💰 [DEBUG] {branch_data['branch_name']}: Total ${branch_data['total_accumulated']:,.2f}")
                print(f"💸 [DEBUG] {branch_data['branch_name']}: Efectivo disponible ${branch_data['available_cash']:,.2f}")
            except Exception as e:
                print(f"❌ [DEBUG] Error calculando total para {branch_data['branch_name']}: {e}")
                branch_data['total_accumulated'] = 0
                branch_data['available_cash'] = 0
        
        result = list(branches.values())
        print(f"✅ [DEBUG] {len(result)} bandejas procesadas con gastos incluidos")
        return result
        
    except Exception as e:
        print(f"❌ [DEBUG] Error en get_simple_branch_data: {e}")
        return []
    
# FUNCIÓN CORREGIDA: Dashboard filtrado    
def get_filtered_dashboard_data(start_date, end_date, branch_filter=None):
    """
    CORREGIDO: Con normalización de nombres de sucursales.
    """
    try:
        print(f"🚀 [API] Obteniendo datos filtrados...")
        print(f"📅 [API] Rango: {start_date} - {end_date}")
        print(f"🏢 [API] Sucursal input: '{branch_filter}'")
        
        # Query básica
        query = DailyRecord.query
        
        # Aplicar filtros
        try:
            if start_date:
                query = query.filter(DailyRecord.record_date >= start_date)
            if end_date:
                query = query.filter(DailyRecord.record_date <= end_date)
                
            # CORRECCIÓN: Filtro de sucursal con normalización
            if branch_filter:
                normalized_input = normalize_branch_name(branch_filter)
                print(f"🏢 [API] Sucursal normalizada: '{normalized_input}'")
                
                # Buscar todas las variaciones en la BD que coincidan
                all_branches = db.session.query(DailyRecord.branch_name).distinct().all()
                matching_branches = []
                
                for (db_branch_name,) in all_branches:
                    if db_branch_name and normalize_branch_name(db_branch_name) == normalized_input:
                        matching_branches.append(db_branch_name)
                
                print(f"🏢 [API] Sucursales coincidentes: {matching_branches}")
                
                if matching_branches:
                    query = query.filter(DailyRecord.branch_name.in_(matching_branches))
                else:
                    print(f"⚠️ [API] No hay registros para sucursal '{normalized_input}'")
                    return {
                        'totals': {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0},
                        'branch_trays': [],
                        'records': [],
                        'message': f'No hay registros para la sucursal "{normalized_input}"'
                    }
                    
            if not current_user.is_admin_user():
                query = query.filter(DailyRecord.user_id == current_user.id)
            
            # Obtener todos los registros filtrados
            records = query.order_by(desc(DailyRecord.record_date)).all()
            print(f"📊 [API] Registros obtenidos: {len(records)}")
            
        except Exception as e:
            print(f"❌ [API] Error en query filtrada: {e}")
            return {
                'totals': {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0},
                'branch_trays': [],
                'records': [],
                'error': str(e)
            }
        
        # Calcular totales de disponibles
        available_records = [r for r in records if not r.is_withdrawn]
        
        if not available_records:
            totals = {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0}
        else:
            totals = {
                'cash': sum(float(r.cash_sales or 0) for r in available_records),
                'mercadopago': sum(float(r.mercadopago_sales or 0) for r in available_records),
                'debit': sum(float(r.debit_sales or 0) for r in available_records),
                'credit': sum(float(r.credit_sales or 0) for r in available_records),
            }
            totals['total'] = sum(totals.values())
        
        # Datos de bandejas
        branch_trays = get_simple_branch_data(available_records)
        
        # Datos de registros (limitar para UI)
        display_records = records[:200] if len(records) > 200 else records
        
        records_data = []
        for r in display_records:
            records_data.append({
                'id': r.id,
                'date': r.record_date.strftime('%d/%m/%Y'),
                'branch_name': normalize_branch_name(r.branch_name),  # Normalizar en salida
                'total_sales': float(r.total_sales or 0),
                'cash_sales': float(r.cash_sales or 0),
                'mercadopago_sales': float(r.mercadopago_sales or 0),
                'debit_sales': float(r.debit_sales or 0),
                'credit_sales': float(r.credit_sales or 0),
                'total_expenses': float(r.total_expenses or 0),
                'net_profit': float(r.total_sales or 0) - float(r.total_expenses or 0),
                'is_verified': r.is_verified,
                'is_withdrawn': r.is_withdrawn
            })
        
        return {
            'totals': totals,
            'branch_trays': branch_trays,
            'records': records_data,
            'total_found': len(records)
        }
        
    except Exception as e:
        print(f"❌ [API] Error crítico: {e}")
        import traceback
        traceback.print_exc()
        return {
            'totals': {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0, 'total': 0},
            'branch_trays': [],
            'records': [],
            'error': str(e)
        }

# Funciones auxiliares

def normalize_branch_name(branch_name):
    """
    Normalizar nombres de sucursal para manejar variaciones.
    CORREGIDO para manejar diferencias entre local y Railway.
    """
    if not branch_name:
        return branch_name
    
    # Convertir a string y limpiar espacios
    normalized = str(branch_name).strip()
    
    # Remover espacios múltiples
    import re
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Mapeo exhaustivo para todas las variaciones posibles
    # Esto maneja tanto las versiones en minúsculas (local) como mayúsculas (Railway)
    branch_mapping = {
        # Uruguay - todas las variaciones
        'uruguay': 'Uruguay',
        'Uruguay': 'Uruguay', 
        'URUGUAY': 'Uruguay',
        ' uruguay ': 'Uruguay',
        'uruguay ': 'Uruguay',
        ' uruguay': 'Uruguay',
        
        # Villa Cabello - todas las variaciones
        'villa cabello': 'Villa Cabello',
        'Villa Cabello': 'Villa Cabello',
        'VILLA CABELLO': 'Villa Cabello', 
        'Villa cabello': 'Villa Cabello',
        'villa_cabello': 'Villa Cabello',
        'villacabello': 'Villa Cabello',
        'VillaCabello': 'Villa Cabello',
        
        # Tacuari - todas las variaciones
        'tacuari': 'Tacuari',
        'Tacuari': 'Tacuari',
        'TACUARI': 'Tacuari',
        'tacuarí': 'Tacuari',
        'Tacuarí': 'Tacuari',
        'TACUARÍ': 'Tacuari',
        
        # Candelaria - todas las variaciones
        'candelaria': 'Candelaria',
        'Candelaria': 'Candelaria',
        'CANDELARIA': 'Candelaria',
        
        # Itaembe Mini - todas las variaciones
        'itaembe mini': 'Itaembe Mini',
        'Itaembe Mini': 'Itaembe Mini',
        'ITAEMBE MINI': 'Itaembe Mini',
        'Itaembe mini': 'Itaembe Mini',
        'itaembe_mini': 'Itaembe Mini',
        'itaembemini': 'Itaembe Mini',
        'ItaembeMini': 'Itaembe Mini'
    }
    
    # 1. Buscar coincidencia exacta primero
    if normalized in branch_mapping:
        return branch_mapping[normalized]
    
    # 2. Buscar por coincidencia insensible a mayúsculas
    normalized_lower = normalized.lower()
    for variation, standard in branch_mapping.items():
        if normalized_lower == variation.lower():
            return standard
    
    # 3. Si no encuentra en el mapeo, devolver capitalizado
    return normalized.title()

def get_matching_branches_improved(branch_filter):
    """
    Función mejorada para obtener sucursales que coincidan con el filtro.
    Maneja las diferencias entre local y Railway.
    """
    if not branch_filter:
        return []
    
    try:
        print(f"🔍 [DEBUG] Buscando coincidencias para: '{branch_filter}'")
        
        # Obtener todas las sucursales únicas de la BD
        all_branches_query = db.session.query(DailyRecord.branch_name).distinct().all()
        all_branch_names = [name[0] for name in all_branches_query if name[0]]
        
        print(f"🔍 [DEBUG] Sucursales en BD: {all_branch_names}")
        
        # Normalizar el filtro
        normalized_filter = normalize_branch_name(branch_filter)
        print(f"🔍 [DEBUG] Filtro normalizado: '{normalized_filter}'")
        
        # Buscar coincidencias usando múltiples métodos
        matching_branches = set()  # Usar set para evitar duplicados
        
        for db_branch_name in all_branch_names:
            # Método 1: Coincidencia exacta
            if db_branch_name == branch_filter:
                matching_branches.add(db_branch_name)
                continue
            
            # Método 2: Coincidencia después de normalización
            if normalize_branch_name(db_branch_name) == normalized_filter:
                matching_branches.add(db_branch_name)
                continue
            
            # Método 3: Coincidencia insensible a mayúsculas
            if db_branch_name.lower() == branch_filter.lower():
                matching_branches.add(db_branch_name)
                continue
            
            # Método 4: Coincidencia de normalizados insensible a mayúsculas
            if normalize_branch_name(db_branch_name).lower() == normalized_filter.lower():
                matching_branches.add(db_branch_name)
                continue
        
        matching_list = list(matching_branches)
        print(f"🔍 [DEBUG] Coincidencias encontradas: {matching_list}")
        return matching_list
        
    except Exception as e:
        print(f"❌ [ERROR] Error en get_matching_branches_improved: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_available_branches():
    """
    Obtener todas las sucursales disponibles en la base de datos, normalizadas.
    """
    try:
        # Obtener todas las sucursales únicas
        raw_branches = db.session.query(DailyRecord.branch_name).distinct().all()
        
        # Normalizar y deduplicar
        normalized_branches = set()
        for (branch_name,) in raw_branches:
            if branch_name:
                normalized = normalize_branch_name(branch_name)
                normalized_branches.add(normalized)
        
        # Convertir a lista ordenada
        available_branches = sorted(list(normalized_branches))
        
        print(f"🏢 [DEBUG] Sucursales disponibles normalizadas: {available_branches}")
        return available_branches
        
    except Exception as e:
        print(f"❌ [DEBUG] Error obteniendo sucursales: {e}")
        return []

def update_trays_from_records():
    """
    ACTUALIZADA: Incluye gastos en efectivo en el cálculo de bandejas.
    """
    from app.models.cash_tray import CashTray
    
    try:
        print("🔄 [DEBUG] Iniciando actualización de bandejas desde registros...")
        
        # Obtener todas las sucursales que tienen registros
        branches = db.session.query(DailyRecord.branch_name).distinct().all()
        print(f"🏢 [DEBUG] Sucursales encontradas: {[b[0] for b in branches]}")
        
        for (branch_name,) in branches:
            print(f"🔄 [DEBUG] Procesando sucursal: {branch_name}")
            
            # Obtener o crear bandeja para la sucursal
            tray = CashTray.query.filter_by(branch_name=branch_name).first()
            if not tray:
                print(f"➕ [DEBUG] Creando nueva bandeja para {branch_name}")
                tray = CashTray(branch_name=branch_name)
                db.session.add(tray)
                db.session.flush()  # Para obtener el ID
            
            # Calcular totales de registros NO retirados
            records = DailyRecord.query.filter_by(
                branch_name=branch_name,
                is_withdrawn=False  # Solo registros NO retirados
            ).all()
            
            print(f"📊 [DEBUG] Registros NO retirados para {branch_name}: {len(records)}")
            
            # Resetear y recalcular
            old_total = tray.get_total_accumulated()
            
            # Calcular ventas
            tray.accumulated_cash = sum(float(r.cash_sales or 0) for r in records)
            tray.accumulated_mercadopago = sum(float(r.mercadopago_sales or 0) for r in records)
            tray.accumulated_debit = sum(float(r.debit_sales or 0) for r in records)
            tray.accumulated_credit = sum(float(r.credit_sales or 0) for r in records)
            
            # NUEVO: Calcular gastos en efectivo acumulados
            tray.accumulated_cash_expenses = sum(float(r.total_expenses or 0) for r in records)
            
            tray.last_updated = datetime.datetime.now()
            
            new_total = tray.get_total_accumulated()
            
            print(f"💰 [DEBUG] {branch_name}: ${old_total:.2f} -> ${new_total:.2f}")
            print(f"💸 [DEBUG] {branch_name}: Gastos en efectivo: ${tray.accumulated_cash_expenses:.2f}")
        
        db.session.commit()
        print("✅ [DEBUG] Actualización de bandejas completada")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [DEBUG] Error actualizando bandejas: {e}")
        raise

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