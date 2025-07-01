"""
Blueprint principal para el sistema de control de sucursales.

Este módulo contiene las rutas principales de la aplicación:
- Página de inicio con redirección basada en roles
- Dashboard de administrador
- Dashboard de sucursal
- Páginas informativas
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
import datetime
import pytz
from app import db
from app.models.user import User
from app.models.daily_record import DailyRecord

# Crear el Blueprint principal
main_bp = Blueprint('main', __name__)


def admin_required(f):
    """
    Decorador para requerir permisos de administrador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'error')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin_user():
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def branch_user_required(f):
    """
    Decorador para requerir que el usuario sea de sucursal.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'error')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_branch_user():
            flash('Esta página es solo para usuarios de sucursal.', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


@main_bp.route('/')
@main_bp.route('/index')
@login_required
def index():
    """
    Página de inicio principal.
    Redirige a los usuarios según su rol.
    """
    # Actualizar último login
    current_user.update_last_login()
    
    # Redirigir según el rol del usuario
    if current_user.is_admin_user():
        return redirect(url_for('main.admin_dashboard'))
    elif current_user.is_branch_user():
        return redirect(url_for('main.branch_dashboard'))
    else:
        # Caso de error: usuario sin rol definido
        flash(
            'Tu cuenta no tiene un rol válido asignado. '
            'Contacta al administrador del sistema.',
            'error'
        )
        return redirect(url_for('auth.logout'))


@main_bp.route('/admin-dashboard')
@login_required
@admin_required
def admin_dashboard():
    """
    Dashboard principal para administradores.
    Muestra estadísticas generales del sistema.
    """
    try:
        # Obtener estadísticas generales
        total_users = User.query.count()
        active_users = User.get_active_users().count()
        branch_users = User.get_branch_users().count()
        admin_users = User.get_admin_users().count()
        
        # Estadísticas de registros diarios (últimos 30 días)
        thirty_days_ago = datetime.date.today() - datetime.timedelta(days=30)
        recent_records = DailyRecord.query.filter(
            DailyRecord.record_date >= thirty_days_ago
        ).count()
        
        # Registros pendientes de verificación
        unverified_records = DailyRecord.query.filter_by(is_verified=False).count()
        
        # Últimos registros creados
        latest_records = DailyRecord.query.order_by(
            DailyRecord.created_at.desc()
        ).limit(5).all()
        
        # Sucursales activas (que han registrado en los últimos 7 días)
        week_ago = datetime.date.today() - datetime.timedelta(days=7)
        active_branches = db.session.query(DailyRecord.branch_name).filter(
            DailyRecord.record_date >= week_ago
        ).distinct().count()
        
        stats = {
            'users': {
                'total': total_users,
                'active': active_users,
                'branch_users': branch_users,
                'admin_users': admin_users
            },
            'records': {
                'recent_total': recent_records,
                'unverified': unverified_records,
                'latest': [record.to_dict() for record in latest_records]
            },
            'branches': {
                'active': active_branches
            }
        }
        
        # === AGREGADO PARA FECHA Y HORA ARGENTINA EN DASHBOARD ADMIN ===
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        now_arg = datetime.datetime.now(tz)
        # ==============================================================
        
        return render_template(
            'main/admin_dashboard.html',
            title='Panel de Administración',
            stats=stats,
            moment=now_arg  # <- para template
        )
        
    except Exception as e:
        flash(f'Error al cargar el dashboard: {str(e)}', 'error')
        return render_template(
            'main/admin_dashboard.html',
            title='Panel de Administración',
            stats=None
        )


@main_bp.route('/branch-dashboard')
@main_bp.route('/my-branch')
@login_required
@branch_user_required
def branch_dashboard():
    """
    Dashboard para usuarios de sucursal.
    Muestra información específica de la sucursal del usuario.
    """
    try:
        # Obtener registros de la sucursal del usuario
        user_records = current_user.daily_records.order_by(
            DailyRecord.record_date.desc()
        ).limit(10).all()
        
        # Estadísticas del mes actual
        today = datetime.date.today()
        first_day_month = today.replace(day=1)
        
        monthly_records = current_user.daily_records.filter(
            DailyRecord.record_date >= first_day_month
        ).all()
        
        # Calcular totales del mes
        monthly_sales = sum(float(record.total_sales) for record in monthly_records)
        monthly_expenses = sum(float(record.total_expenses) for record in monthly_records)
        monthly_net = monthly_sales - monthly_expenses
        
        # Registro de hoy
        today_record = DailyRecord.get_by_branch_and_date(
            current_user.branch_name, 
            today
        )
        
        # Últimos 7 días de actividad
        week_ago = today - datetime.timedelta(days=6)
        weekly_records = current_user.daily_records.filter(
            DailyRecord.record_date >= week_ago,
            DailyRecord.record_date <= today
        ).order_by(DailyRecord.record_date.asc()).all()
        
        stats = {
            'branch_name': current_user.branch_name,
            'recent_records': [record.to_dict() for record in user_records],
            'today_record': today_record.to_dict() if today_record else None,
            'monthly': {
                'records_count': len(monthly_records),
                'total_sales': monthly_sales,
                'total_expenses': monthly_expenses,
                'net_amount': monthly_net
            },
            'weekly_records': [record.to_dict() for record in weekly_records]
        }

        # ==== AGREGADO PARA LA PLANTILLA: FECHA Y HORA EN ARGENTINA ====
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        now_arg = datetime.datetime.now(tz)
        today_date = now_arg.date().isoformat()
        yesterday_date = (now_arg.date() - datetime.timedelta(days=1)).isoformat()
        # ===============================================================

        return render_template(
            'main/branch_dashboard.html',
            title=f'Panel de {current_user.branch_name}',
            stats=stats,
            today_date=today_date,
            yesterday_date=yesterday_date,
            moment=now_arg     # <- para template
        )
        
    except Exception as e:
        flash(f'Error al cargar el dashboard: {str(e)}', 'error')
        return render_template(
            'main/branch_dashboard.html',
            title=f'Panel de {current_user.branch_name}',
            stats=None
        )


@main_bp.route('/welcome')
def welcome():
    """
    Página de bienvenida para usuarios no autenticados.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    return render_template(
        'main/welcome.html',
        title='Bienvenido al Sistema de Control de Sucursales'
    )


@main_bp.route('/about')
def about():
    """
    Página informativa sobre el sistema.
    """
    return render_template(
        'main/about.html',
        title='Acerca del Sistema'
    )


@main_bp.route('/help')
@login_required
def help():
    """
    Página de ayuda para usuarios autenticados.
    """
    return render_template(
        'main/help.html',
        title='Ayuda y Soporte'
    )


@main_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """
    API endpoint para obtener estadísticas en formato JSON.
    Solo para administradores.
    """
    try:
        # Estadísticas de usuarios
        users_stats = {
            'total': User.query.count(),
            'active': User.get_active_users().count(),
            'branch_users': User.get_branch_users().count(),
            'admin_users': User.get_admin_users().count()
        }
        
        # Estadísticas de registros (últimos 30 días)
        thirty_days_ago = datetime.date.today() - datetime.timedelta(days=30)
        records_stats = {
            'total_last_30_days': DailyRecord.query.filter(
                DailyRecord.record_date >= thirty_days_ago
            ).count(),
            'unverified': DailyRecord.query.filter_by(is_verified=False).count(),
            'verified': DailyRecord.query.filter_by(is_verified=True).count()
        }
        
        # Ventas totales del mes actual
        today = datetime.date.today()
        first_day_month = today.replace(day=1)
        
        monthly_records = DailyRecord.query.filter(
            DailyRecord.record_date >= first_day_month
        ).all()
        
        monthly_sales = sum(float(record.total_sales) for record in monthly_records)
        monthly_expenses = sum(float(record.total_expenses) for record in monthly_records)
        
        sales_stats = {
            'monthly_sales': monthly_sales,
            'monthly_expenses': monthly_expenses,
            'monthly_net': monthly_sales - monthly_expenses
        }
        
        return jsonify({
            'status': 'success',
            'data': {
                'users': users_stats,
                'records': records_stats,
                'sales': sales_stats,
                'timestamp': datetime.datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@main_bp.route('/api/branch-stats')
@login_required
@branch_user_required
def api_branch_stats():
    """
    API endpoint para obtener estadísticas de la sucursal del usuario.
    """
    try:
        # Estadísticas del mes actual
        today = datetime.date.today()
        first_day_month = today.replace(day=1)
        
        monthly_records = current_user.daily_records.filter(
            DailyRecord.record_date >= first_day_month
        ).all()
        
        monthly_sales = sum(float(record.total_sales) for record in monthly_records)
        monthly_expenses = sum(float(record.total_expenses) for record in monthly_records)
        
        # Últimos 7 días
        week_ago = today - datetime.timedelta(days=6)
        weekly_records = current_user.daily_records.filter(
            DailyRecord.record_date >= week_ago
        ).all()
        
        weekly_sales = sum(float(record.total_sales) for record in weekly_records)
        
        return jsonify({
            'status': 'success',
            'data': {
                'branch_name': current_user.branch_name,
                'monthly': {
                    'records_count': len(monthly_records),
                    'total_sales': monthly_sales,
                    'total_expenses': monthly_expenses,
                    'net_amount': monthly_sales - monthly_expenses
                },
                'weekly': {
                    'records_count': len(weekly_records),
                    'total_sales': weekly_sales
                },
                'timestamp': datetime.datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# Manejadores de errores específicos del blueprint
@main_bp.errorhandler(403)
def forbidden(error):
    """Manejador de error 403 (Forbidden) para el blueprint main."""
    flash('No tienes permisos para acceder a esta página.', 'error')
    return redirect(url_for('main.index'))


@main_bp.errorhandler(500)
def internal_error(error):
    """Manejador de error 500 para el blueprint main."""
    db.session.rollback()
    flash('Ha ocurrido un error interno. Por favor, inténtalo de nuevo.', 'error')
    return redirect(url_for('main.index'))


# Context processor para el blueprint principal
@main_bp.context_processor
def inject_main_data():
    """
    Inyecta datos útiles en todas las plantillas del blueprint main.
    """
    data = {
        'current_year': datetime.date.today().year,
        'app_name': 'Sistema de Control de Sucursales'
    }
    
    # Agregar datos específicos para usuarios autenticados
    if current_user.is_authenticated:
        data.update({
            'user_display_name': current_user.get_display_name(),
            'user_role': current_user.role,
            'is_admin': current_user.is_admin_user(),
            'is_branch_user': current_user.is_branch_user()
        })
    
    return data

@main_bp.route('/api/daily-stats')
@login_required
@admin_required
def api_daily_stats():
    """
    API endpoint para obtener estadísticas del día actual.
    Solo para administradores.
    """
    try:
        today = datetime.date.today()
        print(f"🔍 Buscando registros para {today}")  # Debug
        
        # Obtener registros del día actual
        todays_records = DailyRecord.query.filter(
            DailyRecord.record_date == today
        ).all()
        
        print(f"📊 Encontrados {len(todays_records)} registros")  # Debug
        
        # Inicializar totales
        total_cash = 0.0
        total_mercadopago = 0.0
        total_debit = 0.0
        total_credit = 0.0
        total_sales = 0.0
        total_expenses = 0.0
        branches_reported = []
        pending_verification = 0
        records_data = []
        
        # Procesar cada registro
        for record in todays_records:
            print(f"  📋 {record.branch_name}: ${record.total_sales}")  # Debug
            
            # Sumar totales
            total_cash += float(record.cash_sales or 0)
            total_mercadopago += float(record.mercadopago_sales or 0)
            total_debit += float(record.debit_sales or 0)
            total_credit += float(record.credit_sales or 0)
            total_sales += float(record.total_sales or 0)
            total_expenses += float(record.total_expenses or 0)
            
            # Agregar sucursal si no está
            if record.branch_name not in branches_reported:
                branches_reported.append(record.branch_name)
            
            # Contar pendientes de verificación
            if not record.is_verified:
                pending_verification += 1
            
            # Datos para la tabla
            net_profit = float(record.total_sales or 0) - float(record.total_expenses or 0)
            records_data.append({
                'id': record.id,
                'sucursal': record.branch_name,
                'ventas': float(record.total_sales or 0),
                'gastos': float(record.total_expenses or 0),
                'ganancia': net_profit,
                'verificado': record.is_verified,
                'creator': record.creator.username if record.creator else 'N/A'
            })
        
        # Calcular ganancia total
        total_profit = total_sales - total_expenses
        
        print(f"💰 Totales calculados:")  # Debug
        print(f"   Efectivo: ${total_cash}")
        print(f"   MercadoPago: ${total_mercadopago}")
        print(f"   Débito: ${total_debit}")
        print(f"   Crédito: ${total_credit}")
        print(f"   Total Ventas: ${total_sales}")
        print(f"   Total Gastos: ${total_expenses}")
        print(f"   Ganancia: ${total_profit}")
        
        response_data = {
            'status': 'success',
            'data': {
                'payment_methods': {
                    'efectivo': round(total_cash, 2),
                    'mercadopago': round(total_mercadopago, 2),
                    'debito': round(total_debit, 2),
                    'credito': round(total_credit, 2)
                },
                'totals': {
                    'ventas': round(total_sales, 2),
                    'gastos': round(total_expenses, 2),
                    'ganancia': round(total_profit, 2),
                    'records_count': len(todays_records)
                },
                'records': records_data,
                'branches_reported': branches_reported,
                'pending_verification': pending_verification,
                'date': today.isoformat()
            }
        }
        
        print(f"✅ Enviando respuesta con {len(todays_records)} registros")  # Debug
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error en api_daily_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': {
                'payment_methods': {
                    'efectivo': 0,
                    'mercadopago': 0,
                    'debito': 0,
                    'credito': 0
                },
                'totals': {
                    'ventas': 0,
                    'gastos': 0,
                    'ganancia': 0,
                    'records_count': 0
                },
                'records': [],
                'branches_reported': [],
                'pending_verification': 0,
                'date': datetime.date.today().isoformat()
            }
        }), 500


@main_bp.route('/api/branch-status')
@login_required 
@admin_required
def api_branch_status():
    """
    API endpoint para obtener el estado de todas las sucursales.
    """
    try:
        today = datetime.date.today()
        all_branches = ['Uruguay', 'Villa Cabello', 'Tacuari', 'Candelaria', 'Itaembe Mini']
        
        # Obtener sucursales que han reportado hoy
        todays_records = DailyRecord.query.filter(
            DailyRecord.record_date == today
        ).all()
        
        reported_branches = list(set([record.branch_name for record in todays_records]))
        
        branch_status = {}
        for branch in all_branches:
            branch_status[branch] = {
                'name': branch,
                'has_reported': branch in reported_branches,
                'status': 'reported' if branch in reported_branches else 'pending'
            }
        
        return jsonify({
            'status': 'success',
            'data': {
                'branches': branch_status,
                'total_reported': len(reported_branches),
                'total_branches': len(all_branches),
                'date': today.isoformat()
            }
        })
        
    except Exception as e:
        print(f"Error en api_branch_status: {str(e)}")  # Para debugging
        return jsonify({
            'status': 'error',
            'message': f'Error interno del servidor: {str(e)}'
        }), 500