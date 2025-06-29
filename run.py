# run.py
"""
Punto de entrada principal para la aplicación del Sistema de Control de Sucursales.

Este archivo es responsable de:
- Cargar las variables de entorno
- Determinar la configuración a usar
- Crear la instancia de la aplicación Flask
- Ejecutar la aplicación en modo desarrollo
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
# Esto debe hacerse antes de importar la aplicación
load_dotenv()

from app import create_app

# Determinar el entorno de la aplicación
# Prioridad: variable de entorno FLASK_ENV, luego FLASK_CONFIG, luego 'development'
config_name = (
    os.environ.get('FLASK_ENV') or 
    os.environ.get('FLASK_CONFIG') or 
    'development'
)

# Crear la instancia de la aplicación Flask
app = create_app(config_name)

# Comandos CLI personalizados para la aplicación
@app.cli.command()
def init_db():
    """Inicializar la base de datos con tablas vacías."""
    from app import db
    
    print("Creando tablas de la base de datos...")
    db.create_all()
    print("✅ Base de datos inicializada correctamente.")


@app.cli.command()
def create_admin():
    """Crear un usuario administrador."""
    from app import db
    from app.models.user import User
    from werkzeug.security import generate_password_hash
    import getpass
    
    print("Creando usuario administrador...")
    
    # Solicitar datos del administrador
    username = input("Nombre de usuario: ").strip()
    if not username:
        print("❌ El nombre de usuario es obligatorio.")
        return
    
    # Verificar si el usuario ya existe
    if User.query.filter_by(username=username).first():
        print(f"❌ El usuario '{username}' ya existe.")
        return
    
    email = input("Email: ").strip()
    if not email:
        print("❌ El email es obligatorio.")
        return
    
    # Verificar si el email ya existe
    if User.query.filter_by(email=email).first():
        print(f"❌ El email '{email}' ya está registrado.")
        return
    
    # Solicitar contraseña de forma segura
    password = getpass.getpass("Contraseña: ")
    if len(password) < 6:
        print("❌ La contraseña debe tener al menos 6 caracteres.")
        return
    
    confirm_password = getpass.getpass("Confirmar contraseña: ")
    if password != confirm_password:
        print("❌ Las contraseñas no coinciden.")
        return
    
    try:
        # Crear el usuario administrador
        admin_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True,
            is_active=True
        )
        
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"✅ Usuario administrador '{username}' creado correctamente.")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error al crear el usuario: {str(e)}")


@app.cli.command()
def reset_db():
    """Eliminar y recrear todas las tablas de la base de datos."""
    from app import db
    
    confirm = input("⚠️  Esto eliminará todos los datos. ¿Continuar? (y/N): ")
    if confirm.lower() != 'y':
        print("Operación cancelada.")
        return
    
    print("Eliminando tablas existentes...")
    db.drop_all()
    
    print("Creando nuevas tablas...")
    db.create_all()
    
    print("✅ Base de datos reinicializada correctamente.")


@app.shell_context_processor
def make_shell_context():
    """
    Registrar objetos para que estén disponibles automáticamente 
    en el shell de Flask (flask shell).
    """
    from app import db
    from app.models.user import User
    from app.models.daily_record import DailyRecord
    
    return {
        'db': db,
        'User': User,
        'DailyRecord': DailyRecord
    }


# Configuración adicional para desarrollo
if config_name == 'development':
    # Habilitar el modo debug si no está explícitamente deshabilitado
    if os.environ.get('FLASK_DEBUG') != '0':
        app.config['DEBUG'] = True


# Punto de entrada principal
if __name__ == '__main__':
    # Configuración para el servidor de desarrollo
    debug_mode = app.config.get('DEBUG', False)
    
    # Puerto y host configurables por variables de entorno
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    
    # Información de inicio
    print(f"""
🚀 Iniciando Sistema de Control de Sucursales
📊 Entorno: {config_name}
🐛 Debug: {debug_mode}
🌐 Servidor: http://{host}:{port}
""")
    
    # Ejecutar la aplicación
    try:
        app.run(
            host=host,
            port=port,
            debug=debug_mode,
            use_reloader=debug_mode,
            use_debugger=debug_mode
        )
    except KeyboardInterrupt:
        print("\n👋 Aplicación detenida por el usuario.")
    except Exception as e:
        print(f"\n❌ Error al iniciar la aplicación: {str(e)}")
        exit(1)