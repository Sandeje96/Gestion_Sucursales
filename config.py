# config.py
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    Configuración base para la aplicación Flask.
    Contiene configuraciones comunes a todos los entornos.
    """
    
    # Clave secreta de Flask - CRÍTICO para seguridad
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
    
    # Configuración de SQLAlchemy
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 
        'sqlite:///' + os.path.join(basedir, 'app.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # Configuración de sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = True if os.environ.get('FLASK_ENV') == 'production' else False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configuración de Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = True if os.environ.get('FLASK_ENV') == 'production' else False
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Configuración de paginación
    RECORDS_PER_PAGE = 25
    USERS_PER_PAGE = 20
    
    # Configuración de logging
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    
    # Configuración de zona horaria
    TIMEZONE = os.environ.get('TIMEZONE') or 'America/Argentina/Buenos_Aires'
    
    # Configuración de correo (para futuras notificaciones)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Configuración de administrador
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@empresa.local'
    
    @staticmethod
    def init_app(app):
        """
        Método para inicializar configuraciones específicas de la aplicación.
        Se puede sobrescribir en subclases para configuraciones adicionales.
        """
        pass


class DevelopmentConfig(Config):
    """
    Configuración para el entorno de desarrollo.
    """
    
    DEBUG = True
    TESTING = False
    
    # Base de datos SQLite para desarrollo local
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DEV_DATABASE_URL') or 
        'sqlite:///' + os.path.join(basedir, 'app_dev.db')
    )
    
    # Configuración menos estricta para desarrollo
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Logging más detallado en desarrollo
    SQLALCHEMY_ECHO = True
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Configuración adicional para desarrollo
        import logging
        from logging import StreamHandler
        
        if not app.debug and not app.testing:
            stream_handler = StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)


class ProductionConfig(Config):
    """
    Configuración para el entorno de producción.
    """
    
    DEBUG = False
    TESTING = False
    
    # Base de datos PostgreSQL en producción
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 
        os.environ.get('POSTGRES_URL') or
        'postgresql://localhost/sucursales_prod'
    )
    
    # Manejo del problema de Railway con postgresql://
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Arreglar URL de PostgreSQL si viene de Railway
        database_url = app.config['SQLALCHEMY_DATABASE_URI']
        if database_url and database_url.startswith('postgres://'):
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace(
                'postgres://', 'postgresql://'
            )
        
        # Configuración de logging para producción
        import logging
        from logging.handlers import RotatingFileHandler
        import os
        
        if not app.debug and not app.testing:
            if app.config['LOG_TO_STDOUT']:
                stream_handler = logging.StreamHandler()
                stream_handler.setLevel(logging.INFO)
                app.logger.addHandler(stream_handler)
            else:
                if not os.path.exists('logs'):
                    os.mkdir('logs')
                file_handler = RotatingFileHandler(
                    'logs/sucursales.log', maxBytes=10240, backupCount=10
                )
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
                ))
                file_handler.setLevel(logging.INFO)
                app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('Sistema de Sucursales iniciado')


class TestingConfig(Config):
    """
    Configuración para el entorno de pruebas.
    """
    
    TESTING = True
    DEBUG = False
    
    # Base de datos en memoria para pruebas rápidas
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Desactivar CSRF para pruebas
    WTF_CSRF_ENABLED = False
    
    # Configuración de sesiones para pruebas
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Paginación reducida para pruebas
    RECORDS_PER_PAGE = 5
    USERS_PER_PAGE = 5
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Configuración adicional para pruebas
        import logging
        app.logger.setLevel(logging.CRITICAL)


# Diccionario para facilitar la selección de configuración
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}