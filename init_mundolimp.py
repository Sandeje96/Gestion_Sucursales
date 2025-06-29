# init_mundolimp.py
"""
Script de inicialización para MundoLimp.
Crea las cuentas de usuario para cada sucursal y un administrador principal.

Ejecutar con: python init_mundolimp.py
"""

import os
import sys
from getpass import getpass

# Agregar el directorio actual al path para poder importar la app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User


def create_mundolimp_users():
    """
    Crear usuarios para todas las sucursales de MundoLimp.
    """
    
    print("🏪 Inicializando Sistema MundoLimp")
    print("=" * 50)
    
    # Crear la aplicación
    app = create_app('development')
    
    with app.app_context():
        # Crear todas las tablas si no existen
        db.create_all()
        
        print("✅ Base de datos inicializada")
        
        # Definir las sucursales de MundoLimp
        branches = [
            {
                'name': 'Uruguay',
                'username': 'uruguay',
                'email': 'uruguay@mundolimp.com',
                'default_password': 'uruguay2025'
            },
            {
                'name': 'Villa Cabello',
                'username': 'villacabello',
                'email': 'villacabello@mundolimp.com',
                'default_password': 'cabello2025'
            },
            {
                'name': 'Tacuari',
                'username': 'tacuari',
                'email': 'tacuari@mundolimp.com',
                'default_password': 'tacuari2025'
            },
            {
                'name': 'Candelaria',
                'username': 'candelaria',
                'email': 'candelaria@mundolimp.com',
                'default_password': 'candelaria2025'
            },
            {
                'name': 'Itaembe Mini',
                'username': 'itaembemini',
                'email': 'itaembemini@mundolimp.com',
                'default_password': 'itaembe2025'
            }
        ]
        
        # Crear usuarios de sucursales
        print("\n📍 Creando usuarios de sucursales...")
        created_users = []
        
        for branch in branches:
            # Verificar si el usuario ya existe
            existing_user = User.query.filter_by(username=branch['username']).first()
            if existing_user:
                print(f"⚠️  Usuario '{branch['username']}' ya existe - omitiendo")
                continue
            
            # Crear nuevo usuario de sucursal
            try:
                user = User(
                    username=branch['username'],
                    email=branch['email'],
                    branch_name=branch['name'],
                    role='branch_user',
                    is_admin=False,
                    is_active=True
                )
                user.set_password(branch['default_password'])
                
                db.session.add(user)
                created_users.append({
                    'branch': branch['name'],
                    'username': branch['username'],
                    'password': branch['default_password']
                })
                
                print(f"✅ Creado: {branch['name']} (usuario: {branch['username']})")
                
            except Exception as e:
                print(f"❌ Error creando {branch['name']}: {str(e)}")
        
        # Crear usuario administrador principal
        print("\n👨‍💼 Configurando usuario administrador...")
        
        admin_exists = User.query.filter_by(role='admin').first()
        if admin_exists:
            print(f"⚠️  Ya existe un administrador: {admin_exists.username}")
        else:
            print("Creando usuario administrador principal...")
            
            # Solicitar datos del administrador
            admin_username = input("Nombre de usuario del administrador [admin]: ").strip() or "admin"
            admin_email = input("Email del administrador [admin@mundolimp.com]: ").strip() or "admin@mundolimp.com"
            
            # Verificar si ya existe
            if User.query.filter_by(username=admin_username).first():
                print(f"❌ El usuario '{admin_username}' ya existe")
            elif User.query.filter_by(email=admin_email).first():
                print(f"❌ El email '{admin_email}' ya está registrado")
            else:
                admin_password = getpass("Contraseña del administrador: ")
                confirm_password = getpass("Confirmar contraseña: ")
                
                if admin_password != confirm_password:
                    print("❌ Las contraseñas no coinciden")
                elif len(admin_password) < 6:
                    print("❌ La contraseña debe tener al menos 6 caracteres")
                else:
                    try:
                        admin_user = User(
                            username=admin_username,
                            email=admin_email,
                            role='admin',
                            is_admin=True,
                            is_active=True,
                            branch_name=None  # Los admins no tienen sucursal específica
                        )
                        admin_user.set_password(admin_password)
                        
                        db.session.add(admin_user)
                        
                        print(f"✅ Administrador creado: {admin_username}")
                        
                    except Exception as e:
                        print(f"❌ Error creando administrador: {str(e)}")
        
        # Confirmar cambios
        try:
            db.session.commit()
            print("\n💾 Todos los cambios guardados exitosamente")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error guardando cambios: {str(e)}")
            return
        
        # Mostrar resumen
        print("\n" + "=" * 50)
        print("🎉 INICIALIZACIÓN COMPLETADA")
        print("=" * 50)
        
        if created_users:
            print("\n📋 CREDENCIALES DE SUCURSALES CREADAS:")
            print("-" * 40)
            for user in created_users:
                print(f"🏪 {user['branch']}")
                print(f"   Usuario: {user['username']}")
                print(f"   Contraseña: {user['password']}")
                print(f"   URL: /auth/login")
                print()
        
        print("🔐 CREDENCIALES DEL ADMINISTRADOR:")
        print("-" * 40)
        admin = User.query.filter_by(role='admin').first()
        if admin:
            print(f"👨‍💼 Administrador: {admin.username}")
            print(f"   Email: {admin.email}")
            print(f"   URL: /auth/login")
        
        print("\n📝 PRÓXIMOS PASOS:")
        print("1. Inicia la aplicación: python run.py")
        print("2. Accede a http://localhost:5000")
        print("3. Cada sucursal puede iniciar sesión con sus credenciales")
        print("4. El administrador puede ver reportes y gestionar el sistema")
        print("\n⚠️  IMPORTANTE: Cambia las contraseñas por defecto después del primer login")


def reset_database():
    """
    Reiniciar completamente la base de datos.
    """
    print("⚠️  ADVERTENCIA: Esto eliminará TODOS los datos existentes")
    confirm = input("¿Estás seguro? Escribe 'CONFIRMAR' para continuar: ")
    
    if confirm != 'CONFIRMAR':
        print("❌ Operación cancelada")
        return
    
    app = create_app('development')
    
    with app.app_context():
        print("🗑️  Eliminando tablas existentes...")
        db.drop_all()
        
        print("🔨 Creando nuevas tablas...")
        db.create_all()
        
        print("✅ Base de datos reiniciada")


def show_existing_users():
    """
    Mostrar usuarios existentes en el sistema.
    """
    app = create_app('development')
    
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("📭 No hay usuarios en el sistema")
            return
        
        print(f"\n👥 USUARIOS EXISTENTES ({len(users)} total):")
        print("=" * 50)
        
        # Agrupar por rol
        admins = [u for u in users if u.is_admin_user()]
        branch_users = [u for u in users if u.is_branch_user()]
        
        if admins:
            print("\n👨‍💼 ADMINISTRADORES:")
            for user in admins:
                status = "🟢 Activo" if user.is_active else "🔴 Inactivo"
                print(f"   • {user.username} ({user.email}) - {status}")
        
        if branch_users:
            print("\n🏪 USUARIOS DE SUCURSALES:")
            for user in branch_users:
                status = "🟢 Activo" if user.is_active else "🔴 Inactivo"
                print(f"   • {user.branch_name}: {user.username} ({user.email}) - {status}")


def main():
    """
    Función principal del script.
    """
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'reset':
            reset_database()
        elif command == 'users':
            show_existing_users()
        elif command == 'help':
            print("Uso: python init_mundolimp.py [comando]")
            print("\nComandos disponibles:")
            print("  (sin comando) - Inicializar usuarios de MundoLimp")
            print("  reset         - Reiniciar base de datos (ELIMINA TODO)")
            print("  users         - Mostrar usuarios existentes")
            print("  help          - Mostrar esta ayuda")
        else:
            print(f"❌ Comando desconocido: {command}")
            print("Usa 'python init_mundolimp.py help' para ver comandos disponibles")
    else:
        create_mundolimp_users()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()