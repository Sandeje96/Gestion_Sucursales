# app/__init__.py
import os
import datetime
import pytz
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf

# Objetos globales
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()  # ← NEW

def create_app(config_name=None):
    """
    Factory function para crear la aplicación Flask.
    """
    app = Flask(__name__)

    # Configuración
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    # Cargar configuración desde config.py
    if config_name == 'development':
        from config import DevelopmentConfig
        app.config.from_object(DevelopmentConfig)
    elif config_name == 'production':
        from config import ProductionConfig
        app.config.from_object(ProductionConfig)
    elif config_name == 'testing':
        from config import TestingConfig
        app.config.from_object(TestingConfig)
    else:
        from config import Config
        app.config.from_object(Config)

    # Asegurar SECRET_KEY por las dudas (no pisa si ya existe)
    app.config.setdefault('SECRET_KEY', os.environ.get('SECRET_KEY', 'dev-secret-key-change-me'))
    app.config.setdefault('WTF_CSRF_ENABLED', True)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'

    # CSRF
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))

    # Importar modelos y crear tablas
    with app.app_context():
        from app.models.user import User
        from app.models.daily_record import DailyRecord
        from app.models.cash_tray import CashTray
        from app.models.branch_expense import BranchExpense
        db.create_all()

    # Blueprints
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.expenses import expenses_bp
    app.register_blueprint(expenses_bp)

    from app.routes.daily_records import daily_records_bp
    app.register_blueprint(daily_records_bp, url_prefix='/daily-records')

    from app.routes.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    # Filtros personalizados
    register_template_filters(app)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Context processors
    @app.context_processor
    def inject_user():
        from flask_login import current_user
        return dict(current_user=current_user)

    @app.context_processor
    def inject_datetime():
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        now_arg = datetime.datetime.now(tz_arg)
        print(f"🇦🇷 Context processor - Hora Argentina: {now_arg.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        return {
            'now': now_arg,
            'current_year': now_arg.year,
            'current_date': now_arg.date(),
            'current_time': now_arg.time(),
            'datetime': datetime,
            'format_date': lambda d: d.strftime('%d/%m/%Y') if d else '',
            'format_datetime': lambda dt: dt.strftime('%d/%m/%Y %H:%M') if dt else '',
            'format_time': lambda t: t.strftime('%H:%M') if t else ''
        }

    # Hacé disponible csrf_token() en Jinja (como usa tu template)
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=lambda: generate_csrf())

    # Helpers de fecha AR
    def get_argentina_now():
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        return datetime.datetime.now(tz_arg)

    def get_argentina_today():
        return get_argentina_now().date()

    app.get_argentina_now = get_argentina_now
    app.get_argentina_today = get_argentina_today

    return app


def register_template_filters(app):
    import pytz
    from datetime import datetime

    @app.template_filter('currency_ar')
    def currency_ar_filter(amount):
        try:
            if isinstance(amount, str):
                amount = float(amount)
            formatted = "{:,.2f}".format(amount)
            formatted = formatted.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
            return f"${formatted}"
        except (ValueError, TypeError):
            return "$0,00"

    @app.template_filter('number_ar')
    def number_ar_filter(amount, decimals=2):
        try:
            if isinstance(amount, str):
                amount = float(amount)
            format_str = f"{{:,.{decimals}f}}"
            formatted = format_str.format(amount)
            formatted = formatted.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
            return formatted
        except (ValueError, TypeError):
            return "0,00"

    @app.template_filter('percentage_ar')
    def percentage_ar_filter(value, decimals=1):
        try:
            if isinstance(value, str):
                value = float(value)
            format_str = f"{{:.{decimals}f}}"
            formatted = format_str.format(value).replace('.', ',')
            return f"{formatted}%"
        except (ValueError, TypeError):
            return "0,0%"

    @app.template_filter('datetime_ar')
    def datetime_ar_filter(dt, format='%d/%m/%Y %H:%M:%S'):
        if not dt:
            return 'No disponible'
        try:
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            dt_arg = dt.astimezone(tz_arg)
            return dt_arg.strftime(format)
        except Exception as e:
            print(f"Error en datetime_ar_filter: {e}")
            return str(dt)

    @app.template_filter('date_ar')
    def date_ar_filter(dt):
        return datetime_ar_filter(dt, '%d/%m/%Y')

    @app.template_filter('format_ar')
    def format_ar_filter(amount, format_type='currency', decimals=2):
        if format_type == 'currency':
            return currency_ar_filter(amount)
        elif format_type == 'number':
            return number_ar_filter(amount, decimals)
        elif format_type == 'percentage':
            return percentage_ar_filter(amount, decimals)
        else:
            return str(amount)

    @app.template_filter('time_ar')
    def time_ar_filter(dt):
        return datetime_ar_filter(dt, '%H:%M:%S')

    @app.template_global()
    def format_currency_jinja(amount):
        return currency_ar_filter(amount)

    @app.template_global()
    def format_number_jinja(amount, decimals=2):
        return number_ar_filter(amount, decimals)

    @app.context_processor
    def inject_format_helpers():
        return {
            'format_currency_ar': currency_ar_filter,
            'format_number_ar': number_ar_filter,
            'format_percentage_ar': percentage_ar_filter
        }