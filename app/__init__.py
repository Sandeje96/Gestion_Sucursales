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
    
    # Función de utilidad para el contexto de plantillas
    @app.context_processor
    def inject_user():
        from flask_login import current_user
        return dict(current_user=current_user)
    
    return app