# app/routes/reports.py
"""
Blueprint para reportes y análisis del sistema.

Este módulo contiene las rutas para:
- Dashboard principal de reportes
- Análisis por sucursal
- Comparativas entre sucursales
- Exportación de datos
- Gráficos y visualizaciones
"""

from flask import Blueprint, render_template, request, jsonify, make_response, abort
from flask_login import login_required, current_user
from sqlalchemy import func, desc, extract, and_
from datetime import date, datetime, timedelta
import calendar
import json
import datetime
import calendar
from datetime import timedelta

from app import db
from app.models.user import User
from app.models.daily_record import DailyRecord
from app.forms.daily_record_forms import FilterForm, QuickStatsForm

# Crear el Blueprint
reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/')
@reports_bp.route('/index')
@login_required
def index():
    """
    Dashboard principal de reportes.
    MEJORADO: Con filtro por sucursal.
    """
    if not current_user.is_admin_user():
        abort(403)
    
    # Obtener parámetros del filtro
    period = request.args.get('period', 'month')
    custom_start = request.args.get('start_date')
    custom_end = request.args.get('end_date')
    branch_filter = request.args.get('branch_filter')  # NUEVO: Filtro por sucursal
    
    # Calcular fechas según el período
    start_date, end_date = get_period_dates(period, custom_start, custom_end)
    
    print(f"🔍 Filtro aplicado en reports index: {period}")
    print(f"📅 Rango de fechas: {start_date} - {end_date}")
    print(f"🏢 Sucursal filtrada: {branch_filter or 'Todas'}")  # NUEVO: Log del filtro
    
    # NUEVO: Aplicar filtro de sucursal a las estadísticas
    general_stats = get_general_statistics(start_date, end_date, branch_filter)
    branch_stats = get_branch_statistics(start_date, end_date, branch_filter)
    
    # Datos para gráficos (también con filtro)
    days_in_period = (end_date - start_date).days + 1
    daily_trends = get_daily_trends(days_in_period, start_date, end_date, branch_filter)
    payment_distribution = get_payment_distribution(start_date, end_date, branch_filter)
    
    return render_template(
        'reports/index.html',
        title='Panel de Reportes',
        general_stats=general_stats,
        branch_stats=branch_stats,
        daily_trends=daily_trends,
        payment_distribution=payment_distribution,
        current_period={'start': start_date, 'end': end_date, 'type': period},
        current_branch_filter=branch_filter  # NUEVO: Pasar filtro al template
    )


@reports_bp.route('/branch/<branch_name>')
@login_required
def branch_detail(branch_name):
    """
    Reporte detallado de una sucursal específica.
    """
    # Verificar que la sucursal existe
    valid_branches = ['Uruguay', 'Villa Cabello', 'Tacuari', 'Candelaria', 'Itaembe Mini']
    if branch_name not in valid_branches:
        abort(404)
    
    # Verificar permisos
    if not current_user.is_admin_user() and current_user.branch_name != branch_name:
        abort(403)
    
    # Fechas por defecto (últimos 30 días)
    end_date = date.today()
    start_date = end_date - timedelta(days=29)
    
    # Si hay filtros en la URL
    if request.args.get('start_date'):
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if request.args.get('end_date'):
        try:
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Obtener datos de la sucursal
    branch_data = get_branch_detailed_stats(branch_name, start_date, end_date)
    
    # Comparativa con otras sucursales (solo para admins)
    comparison_data = None
    if current_user.is_admin_user():
        comparison_data = get_branch_comparison(branch_name, start_date, end_date)
    
    return render_template(
        'reports/branch_detail.html',
        title=f'Reporte - {branch_name}',
        branch_name=branch_name,
        branch_data=branch_data,
        comparison_data=comparison_data,
        start_date=start_date,
        end_date=end_date
    )


@reports_bp.route('/comparison')
@login_required
def comparison():
    """
    Comparativa entre todas las sucursales.
    Solo para administradores.
    """
    if not current_user.is_admin_user():
        abort(403)
    
    # Obtener parámetros del filtro
    period = request.args.get('period', 'month')
    custom_start = request.args.get('start_date')
    custom_end = request.args.get('end_date')
    
    # Calcular fechas según el período
    start_date, end_date = get_period_dates(period, custom_start, custom_end)
    
    print(f"🔍 Filtro aplicado: {period}")
    print(f"📅 Rango de fechas: {start_date} - {end_date}")
    
    # Obtener datos comparativos para el período seleccionado
    comparison_data = get_comprehensive_comparison(start_date, end_date)
    
    return render_template(
        'reports/comparison.html',
        title='Comparativa de Sucursales',
        comparison_data=comparison_data,
        start_date=start_date,
        end_date=end_date,
        current_period=period
    )


@reports_bp.route('/api/daily-sales-chart')
@login_required
def api_daily_sales_chart():
    """
    API para datos del gráfico de ventas diarias.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    if not current_user.is_admin_user():
        abort(403)
    
    # Obtener parámetros
    days = request.args.get('days', 30, type=int)
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')
    branch_filter = request.args.get('branch_filter')
    
    print(f"🔍 [API] daily-sales-chart - branch_filter: '{branch_filter}'")
    
    # Calcular fechas
    if start_date_param and end_date_param:
        start_date = datetime.datetime.strptime(start_date_param, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_param, '%Y-%m-%d').date()
    else:
        end_date = datetime.date.today()
        start_date = end_date - timedelta(days=days-1)
    
    # Query base
    query = db.session.query(
        DailyRecord.record_date,
        func.sum(DailyRecord.total_sales).label('total_sales'),
        func.sum(DailyRecord.total_expenses).label('total_expenses'),
        func.count(DailyRecord.id).label('records_count')
    ).filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    # ✅ CORRECCIÓN: Filtro directo sin normalización
    if branch_filter:
        query = query.filter(DailyRecord.branch_name == branch_filter)
        print(f"🏢 [API] Filtrado por sucursal: {branch_filter}")
    
    # Agrupar por fecha
    results = query.group_by(DailyRecord.record_date).order_by(DailyRecord.record_date).all()
    
    # Formatear datos para Chart.js
    labels = []
    sales_data = []
    expenses_data = []
    net_data = []
    
    for result in results:
        labels.append(result.record_date.strftime('%d/%m'))
        sales_data.append(float(result.total_sales or 0))
        expenses_data.append(float(result.total_expenses or 0))
        net_data.append(float(result.total_sales or 0) - float(result.total_expenses or 0))
    
    return jsonify({
        'status': 'success',
        'data': {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Ventas',
                    'data': sales_data,
                    'borderColor': 'rgb(34, 197, 94)',
                    'backgroundColor': 'rgba(34, 197, 94, 0.1)',
                    'tension': 0.1
                },
                {
                    'label': 'Gastos',
                    'data': expenses_data,
                    'borderColor': 'rgb(239, 68, 68)',
                    'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                    'tension': 0.1
                },
                {
                    'label': 'Ganancia Neta',
                    'data': net_data,
                    'borderColor': 'rgb(59, 130, 246)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                    'tension': 0.1
                }
            ]
        },
        'meta': {
            'branch_filter': branch_filter,
            'period': f"{start_date} - {end_date}",
            'records_found': len(results)
        }
    })



@reports_bp.route('/api/payment-methods-distribution')
@login_required
def api_payment_distribution():
    """
    API para distribución de métodos de pago con filtros de fecha.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    # Obtener parámetros
    days = request.args.get('days', 30, type=int)
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')
    branch_filter = request.args.get('branch_filter')
    
    print(f"🔍 [API] payment-distribution - branch_filter: '{branch_filter}'")
    
    # Calcular fechas
    if start_date_param and end_date_param:
        start_date = datetime.datetime.strptime(start_date_param, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_param, '%Y-%m-%d').date()
    else:
        end_date = datetime.date.today()
        start_date = end_date - timedelta(days=days-1)
    
    # Query base
    query = db.session.query(
        func.sum(DailyRecord.cash_sales).label('cash'),
        func.sum(DailyRecord.mercadopago_sales).label('mercadopago'),
        func.sum(DailyRecord.debit_sales).label('debit'),
        func.sum(DailyRecord.credit_sales).label('credit')
    ).filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    # ✅ CORRECCIÓN: Filtro directo sin normalización
    if branch_filter:
        query = query.filter(DailyRecord.branch_name == branch_filter)
        print(f"🏢 [API] Filtrado por sucursal: {branch_filter}")
    elif not current_user.is_admin_user():
        # Si no es admin y no hay filtro, usar su sucursal
        query = query.filter(DailyRecord.user_id == current_user.id)
    
    result = query.first()
    
    # Calcular totales y porcentajes
    cash = float(result.cash or 0)
    mercadopago = float(result.mercadopago or 0)
    debit = float(result.debit or 0)
    credit = float(result.credit or 0)
    total = cash + mercadopago + debit + credit
    
    if total > 0:
        percentages = {
            'cash': round((cash / total) * 100, 1),
            'mercadopago': round((mercadopago / total) * 100, 1),
            'debit': round((debit / total) * 100, 1),
            'credit': round((credit / total) * 100, 1)
        }
    else:
        percentages = {'cash': 0, 'mercadopago': 0, 'debit': 0, 'credit': 0}
    
    return jsonify({
        'status': 'success',
        'data': {
            'amounts': {
                'cash': cash,
                'mercadopago': mercadopago,
                'debit': debit,
                'credit': credit,
                'total': total
            },
            'percentages': percentages,
            'chart_data': {
                'labels': ['Efectivo', 'MercadoPago', 'Débito', 'Crédito'],
                'data': [cash, mercadopago, debit, credit],
                'backgroundColor': [
                    '#10b981',  # Verde para efectivo
                    '#3b82f6',  # Azul para MercadoPago
                    '#f59e0b',  # Amarillo para débito
                    '#ef4444'   # Rojo para crédito
                ]
            }
        },
        'meta': {
            'branch_filter': branch_filter,
            'period': f"{start_date} - {end_date}"
        }
    })


@reports_bp.route('/export/csv')
@login_required
def export_csv():
    """
    Exportar datos a CSV.
    """
    # Parámetros de filtro
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    branch = request.args.get('branch', '')
    
    # Fechas por defecto (último mes)
    if not start_date:
        start_date = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = date.today()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Construir query
    if current_user.is_admin_user():
        query = DailyRecord.query
    else:
        query = current_user.daily_records
    
    query = query.filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    if branch and current_user.is_admin_user():
        query = query.filter(DailyRecord.branch_name == branch)
    
    records = query.order_by(DailyRecord.record_date.desc()).all()
    
    # Crear CSV
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    headers = [
        'Fecha', 'Sucursal', 'Ventas Efectivo', 'Ventas MercadoPago',
        'Ventas Débito', 'Ventas Crédito', 'Total Ventas',
        'Gastos', 'Ganancia Neta', 'Verificado', 'Notas'
    ]
    writer.writerow(headers)
    
    # Datos
    for record in records:
        writer.writerow([
            record.record_date.strftime('%d/%m/%Y'),
            record.branch_name,
            f'{record.cash_sales:.2f}',
            f'{record.mercadopago_sales:.2f}',
            f'{record.debit_sales:.2f}',
            f'{record.credit_sales:.2f}',
            f'{record.total_sales:.2f}',
            f'{record.total_expenses:.2f}',
            f'{record.get_net_amount():.2f}',
            'Sí' if record.is_verified else 'No',
            record.notes or ''
        ])
    
    # Preparar respuesta
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=reporte_{start_date}_{end_date}.csv'
    
    return response


# Funciones auxiliares para cálculos estadísticos

def get_period_dates(period, custom_start=None, custom_end=None):
    """
    Calcular fechas de inicio y fin basadas en el período seleccionado.
    """
    import datetime
    from datetime import timedelta
    
    import pytz
    tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
    today = datetime.datetime.now(tz_arg).date()
    
    if period == 'today':
        return today, today
    
    elif period == 'week':
        # Esta semana (lunes a domingo)
        start = today - timedelta(days=today.weekday())
        return start, today
    
    elif period == 'month':
        # Este mes
        start = today.replace(day=1)
        return start, today
    
    elif period == 'quarter':
        # Este trimestre
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        start = datetime.date(today.year, quarter_start_month, 1)
        return start, today
    
    elif period == 'year':
        # Este año
        start = datetime.date(today.year, 1, 1)
        return start, today
    
    elif period == 'custom' and custom_start and custom_end:
        # Período personalizado
        if isinstance(custom_start, str):
            custom_start = datetime.datetime.strptime(custom_start, '%Y-%m-%d').date()
        if isinstance(custom_end, str):
            custom_end = datetime.datetime.strptime(custom_end, '%Y-%m-%d').date()
        return custom_start, custom_end
    
    else:
        # Por defecto: este mes
        start = today.replace(day=1)
        return start, today

def get_general_statistics(start_date, end_date, branch_filter=None):
    """
    Obtener estadísticas generales del sistema.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    query = DailyRecord.query.filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    # ✅ CORRECCIÓN: Filtro directo sin normalización
    if branch_filter:
        query = query.filter(DailyRecord.branch_name == branch_filter)
        print(f"📊 Aplicando filtro de sucursal en general_stats: {branch_filter}")
    
    records = query.all()
    
    if not records:
        return None
    
    total_sales = sum(float(r.total_sales) for r in records)
    total_expenses = sum(float(r.total_expenses) for r in records)
    
    return {
        'total_records': len(records),
        'total_sales': total_sales,
        'total_expenses': total_expenses,
        'net_profit': total_sales - total_expenses,
        'avg_daily_sales': total_sales / ((end_date - start_date).days + 1),
        'active_branches': len(set(r.branch_name for r in records)),
        'verified_records': len([r for r in records if r.is_verified]),
        'verification_rate': len([r for r in records if r.is_verified]) / len(records) * 100 if records else 0,
        'is_filtered_by_branch': bool(branch_filter),
        'filtered_branch': branch_filter
    }


def get_branch_statistics(start_date, end_date, branch_filter=None):
    """
    Obtener estadísticas por sucursal.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    query = db.session.query(
        DailyRecord.branch_name,
        func.count(DailyRecord.id).label('records_count'),
        func.sum(DailyRecord.total_sales).label('total_sales'),
        func.sum(DailyRecord.total_expenses).label('total_expenses'),
        func.avg(DailyRecord.total_sales).label('avg_sales'),
        func.sum(DailyRecord.cash_sales).label('cash_sales'),
        func.sum(DailyRecord.mercadopago_sales).label('mercadopago_sales'),
        func.sum(DailyRecord.debit_sales).label('debit_sales'),
        func.sum(DailyRecord.credit_sales).label('credit_sales')
    ).filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    # ✅ CORRECCIÓN: Filtro directo sin normalización
    if branch_filter:
        query = query.filter(DailyRecord.branch_name == branch_filter)
        print(f"📊 Aplicando filtro de sucursal en branch_stats: {branch_filter}")
    
    branch_stats = query.group_by(DailyRecord.branch_name).all()
    
    result = {}
    for stat in branch_stats:
        result[stat.branch_name] = {
            'records_count': stat.records_count,
            'total_sales': float(stat.total_sales or 0),
            'total_expenses': float(stat.total_expenses or 0),
            'net_profit': float(stat.total_sales or 0) - float(stat.total_expenses or 0),
            'avg_sales': float(stat.avg_sales or 0),
            'payment_breakdown': {
                'cash': float(stat.cash_sales or 0),
                'mercadopago': float(stat.mercadopago_sales or 0),
                'debit': float(stat.debit_sales or 0),
                'credit': float(stat.credit_sales or 0)
            }
        }
    
    return result


def get_daily_trends(days, start_date=None, end_date=None, branch_filter=None):
    """
    Obtener tendencias diarias para gráficos con fechas específicas.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    if start_date is None or end_date is None:
        end_date = datetime.date.today()
        start_date = end_date - timedelta(days=days-1)
    
    query = db.session.query(
        DailyRecord.record_date,
        func.sum(DailyRecord.total_sales).label('sales'),
        func.sum(DailyRecord.total_expenses).label('expenses')
    ).filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    # ✅ CORRECCIÓN: Filtro directo sin normalización
    if branch_filter:
        query = query.filter(DailyRecord.branch_name == branch_filter)
        print(f"📊 Aplicando filtro de sucursal en daily_trends: {branch_filter}")
    
    daily_data = query.group_by(DailyRecord.record_date).order_by(DailyRecord.record_date).all()
    
    return [
        {
            'date': data.record_date.isoformat(),
            'sales': float(data.sales or 0),
            'expenses': float(data.expenses or 0),
            'net': float(data.sales or 0) - float(data.expenses or 0)
        }
        for data in daily_data
    ]


def get_payment_distribution(start_date, end_date, branch_filter=None):
    """
    Obtener distribución de métodos de pago.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    query = db.session.query(
        func.sum(DailyRecord.cash_sales).label('cash'),
        func.sum(DailyRecord.mercadopago_sales).label('mercadopago'),
        func.sum(DailyRecord.debit_sales).label('debit'),
        func.sum(DailyRecord.credit_sales).label('credit')
    ).filter(
        DailyRecord.record_date.between(start_date, end_date)
    )
    
    # ✅ CORRECCIÓN: Filtro directo sin normalización
    if branch_filter:
        query = query.filter(DailyRecord.branch_name == branch_filter)
        print(f"📊 Aplicando filtro de sucursal en payment_distribution: {branch_filter}")
    
    result = query.first()
    
    return {
        'cash': float(result.cash or 0),
        'mercadopago': float(result.mercadopago or 0),
        'debit': float(result.debit or 0),
        'credit': float(result.credit or 0)
    }


def get_branch_detailed_stats(branch_name, start_date, end_date):
    """
    Obtener estadísticas detalladas de una sucursal.
    """
    records = DailyRecord.query.filter(
        DailyRecord.branch_name == branch_name,
        DailyRecord.record_date.between(start_date, end_date)
    ).order_by(DailyRecord.record_date.desc()).all()
    
    if not records:
        return None
    
    # Calcular totales
    total_sales = sum(float(r.total_sales) for r in records)
    total_expenses = sum(float(r.total_expenses) for r in records)
    
    # Tendencias diarias
    daily_trends = []
    for record in reversed(records):
        daily_trends.append({
            'date': record.record_date.isoformat(),
            'sales': float(record.total_sales),
            'expenses': float(record.total_expenses),
            'net': record.get_net_amount()
        })
    
    return {
        'records_count': len(records),
        'total_sales': total_sales,
        'total_expenses': total_expenses,
        'net_profit': total_sales - total_expenses,
        'avg_daily_sales': total_sales / len(records),
        'best_day': max(records, key=lambda r: r.total_sales),
        'worst_day': min(records, key=lambda r: r.total_sales),
        'daily_trends': daily_trends,
        'payment_breakdown': {
            'cash': sum(float(r.cash_sales) for r in records),
            'mercadopago': sum(float(r.mercadopago_sales) for r in records),
            'debit': sum(float(r.debit_sales) for r in records),
            'credit': sum(float(r.credit_sales) for r in records)
        }
    }


def get_branch_comparison(target_branch, start_date, end_date):
    """
    Comparar una sucursal con las demás.
    """
    all_branches = ['Uruguay', 'Villa Cabello', 'Tacuari', 'Candelaria', 'Itaembe Mini']
    comparison = {}
    
    for branch in all_branches:
        if branch == target_branch:
            continue
        
        records = DailyRecord.query.filter(
            DailyRecord.branch_name == branch,
            DailyRecord.record_date.between(start_date, end_date)
        ).all()
        
        if records:
            total_sales = sum(float(r.total_sales) for r in records)
            total_expenses = sum(float(r.total_expenses) for r in records)
            
            comparison[branch] = {
                'total_sales': total_sales,
                'total_expenses': total_expenses,
                'net_profit': total_sales - total_expenses,
                'avg_daily_sales': total_sales / len(records) if records else 0,
                'records_count': len(records)
            }
    
    return comparison


def get_comprehensive_comparison(start_date, end_date):
    """
    Obtener comparativa completa entre todas las sucursales.
    """
    return get_branch_statistics(start_date, end_date)

@reports_bp.route('/api/branch-performance')
@login_required
def api_branch_performance():
    """
    API para datos de rendimiento por sucursal con soporte para períodos.
    CORREGIDO: Sin normalize_branch_name que no existe.
    """
    try:
        if not current_user.is_admin_user():
            return jsonify({
                'status': 'error',
                'message': 'Acceso denegado',
                'data': {
                    'branches': [],
                    'sales': [],
                    'expenses': [],
                    'net_profits': [],
                    'avg_sales': []
                }
            }), 403
        
        # Obtener parámetros
        period = request.args.get('period', 'month')
        custom_start = request.args.get('start_date')
        custom_end = request.args.get('end_date')
        branch_filter = request.args.get('branch_filter')
        
        print(f"🔍 API branch-performance - branch_filter: '{branch_filter}'")
        
        # Calcular fechas según el período
        start_date, end_date = get_period_dates(period, custom_start, custom_end)
        
        # Query base para obtener datos por sucursal
        query = db.session.query(
            DailyRecord.branch_name,
            func.sum(DailyRecord.total_sales).label('total_sales'),
            func.sum(DailyRecord.total_expenses).label('total_expenses'),
            func.count(DailyRecord.id).label('records_count'),
            func.avg(DailyRecord.total_sales).label('avg_sales')
        ).filter(
            DailyRecord.record_date.between(start_date, end_date)
        )
        
        # ✅ CORRECCIÓN: Filtro directo sin normalización
        if branch_filter:
            query = query.filter(DailyRecord.branch_name == branch_filter)
            print(f"🏢 Filtrado por sucursal: {branch_filter}")
        
        branch_data = query.group_by(DailyRecord.branch_name).all()
        
        # Formatear datos para gráficos
        branches = []
        sales = []
        expenses = []
        net_profits = []
        avg_sales = []
        
        for data in branch_data:
            branches.append(data.branch_name)
            sales.append(float(data.total_sales or 0))
            expenses.append(float(data.total_expenses or 0))
            net_profits.append(float(data.total_sales or 0) - float(data.total_expenses or 0))
            avg_sales.append(float(data.avg_sales or 0))
        
        return jsonify({
            'status': 'success',
            'data': {
                'branches': branches,
                'sales': sales,
                'expenses': expenses,
                'net_profits': net_profits,
                'avg_sales': avg_sales,
                'branch_filter': branch_filter
            }
        })
        
    except Exception as e:
        print(f"❌ Error en API branch-performance: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': {
                'branches': [],
                'sales': [],
                'expenses': [],
                'net_profits': [],
                'avg_sales': [],
                'branch_filter': branch_filter
            }
        }), 500

# También agregar esta función auxiliar mejorada al final del archivo:

def get_comprehensive_comparison(start_date, end_date):
    """
    Obtener comparativa completa entre todas las sucursales para un período específico.
    """
    # Obtener datos agrupados por sucursal
    branch_stats = db.session.query(
        DailyRecord.branch_name,
        func.count(DailyRecord.id).label('records_count'),
        func.sum(DailyRecord.total_sales).label('total_sales'),
        func.sum(DailyRecord.total_expenses).label('total_expenses'),
        func.avg(DailyRecord.total_sales).label('avg_sales'),
        func.sum(DailyRecord.cash_sales).label('cash_sales'),
        func.sum(DailyRecord.mercadopago_sales).label('mercadopago_sales'),
        func.sum(DailyRecord.debit_sales).label('debit_sales'),
        func.sum(DailyRecord.credit_sales).label('credit_sales')
    ).filter(
        DailyRecord.record_date.between(start_date, end_date)
    ).group_by(DailyRecord.branch_name).all()
    
    result = {}
    for stat in branch_stats:
        result[stat.branch_name] = {
            'records_count': stat.records_count,
            'total_sales': float(stat.total_sales or 0),
            'total_expenses': float(stat.total_expenses or 0),
            'net_profit': float(stat.total_sales or 0) - float(stat.total_expenses or 0),
            'avg_sales': float(stat.avg_sales or 0),
            'payment_breakdown': {
                'cash': float(stat.cash_sales or 0),
                'mercadopago': float(stat.mercadopago_sales or 0),
                'debit': float(stat.debit_sales or 0),
                'credit': float(stat.credit_sales or 0)
            }
        }
    
    return result