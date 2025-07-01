# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Inicialización de objetos globales
db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name=None):
    """
    Factory function para crear la aplicación Flask.
    
    Args:
        config_name (str): Nombre de la configuración a usar ('development', 'production', etc.)
                          Si es None, se usa la variable de entorno FLASK_ENV
    
    Returns:
        Flask: Instancia de la aplicación Flask configurada
    """
    
    # Crear instancia de Flask
    app = Flask(__name__)
    
    # Configuración de la aplicación
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
    
    # Inicializar SQLAlchemy con la aplicación
    db.init_app(app)
    
    # Configurar Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """
        Callback para cargar un usuario desde la base de datos.
        
        Args:
            user_id (str): ID del usuario a cargar
            
        Returns:
            User: Objeto User o None si no existe
        """
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Importar modelos para que SQLAlchemy los detecte
    with app.app_context():
        from app.models.user import User
        from app.models.daily_record import DailyRecord
        
        # Crear todas las tablas si no existen
        db.create_all()

    # Registro de Blueprints - UNA SOLA VEZ
    # Blueprint de autenticación
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Blueprint principal
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    # Blueprint de registros diarios
    from app.routes.daily_records import daily_records_bp
    app.register_blueprint(daily_records_bp, url_prefix='/daily-records')
    
    # Blueprint de reportes
    from app.routes.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    # Registrar filtros personalizados para formato argentino
    register_template_filters(app)
    
    # Manejadores de errores globales
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Context processors para inyectar datos en todas las plantillas
    @app.context_processor
    def inject_user():
        from flask_login import current_user
        return dict(current_user=current_user)
    
    @app.context_processor
    def inject_datetime():
        """
        Inyectar funciones de fecha y hora en todas las plantillas.
        """
        import datetime
        import pytz
        
        # Zona horaria argentina
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        now_arg = datetime.datetime.now(tz_arg)
        
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
    
    return app


def register_template_filters(app):
    """
    Registrar filtros personalizados para formato argentino en las plantillas.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    
    @app.template_filter('currency_ar')
    def currency_ar_filter(amount):
        """
        Filtro para formatear moneda en formato argentino.
        Ejemplo: 1234567.89 -> $1.234.567,89
        """
        try:
            # Convertir a float si es necesario
            if isinstance(amount, str):
                amount = float(amount)
            
            # Formatear el número
            # Separar parte entera y decimal
            formatted = "{:,.2f}".format(amount)
            
            # Cambiar separadores: . por , y , por .
            # Primero cambiar , por un marcador temporal
            formatted = formatted.replace(',', 'TEMP')
            # Cambiar . por ,
            formatted = formatted.replace('.', ',')
            # Cambiar marcador temporal por .
            formatted = formatted.replace('TEMP', '.')
            
            return f"${formatted}"
        except (ValueError, TypeError):
            return "$0,00"
    
    @app.template_filter('number_ar')
    def number_ar_filter(amount, decimals=2):
        """
        Filtro para formatear número con separadores argentinos sin símbolo de moneda.
        Ejemplo: 1234567.89 -> 1.234.567,89
        """
        try:
            if isinstance(amount, str):
                amount = float(amount)
            
            format_str = f"{{:,.{decimals}f}}"
            formatted = format_str.format(amount)
            
            # Cambiar separadores
            formatted = formatted.replace(',', 'TEMP')
            formatted = formatted.replace('.', ',')
            formatted = formatted.replace('TEMP', '.')
            
            return formatted
        except (ValueError, TypeError):
            return "0,00"
    
    @app.template_filter('percentage_ar')
    def percentage_ar_filter(value, decimals=1):
        """
        Filtro para formatear porcentaje en formato argentino.
        Ejemplo: 15.5 -> 15,5%
        """
        try:
            if isinstance(value, str):
                value = float(value)
            
            format_str = f"{{:.{decimals}f}}"
            formatted = format_str.format(value)
            
            # Cambiar punto por coma
            formatted = formatted.replace('.', ',')
            
            return f"{formatted}%"
        except (ValueError, TypeError):
            return "0,0%"
    
    @app.template_filter('format_ar')
    def format_ar_filter(amount, format_type='currency', decimals=2):
        """
        Filtro universal para formateo argentino.
        
        Args:
            amount: Cantidad a formatear
            format_type: Tipo de formato ('currency', 'number', 'percentage')
            decimals: Número de decimales
        
        Returns:
            str: Cantidad formateada
        """
        if format_type == 'currency':
            return currency_ar_filter(amount)
        elif format_type == 'number':
            return number_ar_filter(amount, decimals)
        elif format_type == 'percentage':
            return percentage_ar_filter(amount, decimals)
        else:
            return str(amount)
    
    # Función auxiliar disponible en todas las plantillas
    @app.template_global()
    def format_currency_jinja(amount):
        """
        Función global disponible en plantillas para formatear moneda.
        """
        return currency_ar_filter(amount)
    
    @app.template_global()
    def format_number_jinja(amount, decimals=2):
        """
        Función global disponible en plantillas para formatear números.
        """
        return number_ar_filter(amount, decimals)
    
    # Contexto processor adicional para datos de formato
    @app.context_processor
    def inject_format_helpers():
        """
        Inyectar funciones de formato en el contexto de todas las plantillas.
        """
        return {
            'format_currency_ar': currency_ar_filter,
            'format_number_ar': number_ar_filter,
            'format_percentage_ar': percentage_ar_filter
        }