# app/routes/auth.py
"""
Blueprint de autenticación para el sistema de control de sucursales.

Este módulo contiene las rutas para:
- Inicio de sesión (/login)
- Registro de nuevos usuarios (/register)
- Cierre de sesión (/logout)
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from app.models.user import User
from app.forms.auth_forms import LoginForm, RegistrationForm

# Crear el Blueprint de autenticación
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Ruta para el inicio de sesión de usuarios.
    
    GET: Muestra el formulario de inicio de sesión
    POST: Procesa las credenciales y autentica al usuario
    """
    
    # Si el usuario ya está autenticado, redirigir a la página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Instanciar el formulario de inicio de sesión
    form = LoginForm()
    
    # Procesar el formulario si se envió via POST y es válido
    if form.validate_on_submit():
        # Buscar usuario por nombre de usuario
        user = User.query.filter_by(username=form.username.data).first()
        
        # Verificar si el usuario existe y la contraseña es correcta
        if user and user.check_password(form.password.data):
            # Verificar si el usuario está activo
            if not user.is_active:
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
                return render_template('auth/login.html', title='Iniciar Sesión', form=form)
            
            # Iniciar sesión del usuario
            login_user(user, remember=form.remember_me.data)
            
            # Manejar redirección después del login
            next_page = request.args.get('next')
            
            # Validar que la URL 'next' sea segura (mismo dominio)
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            
            # Redirigir según el rol del usuario
            if user.role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            else:
                return redirect(url_for('main.branch_dashboard'))
        
        else:
            # Credenciales incorrectas
            flash('Usuario o contraseña incorrectos.', 'error')
    
    # Renderizar el formulario de login (GET o si hay errores)
    return render_template('auth/login.html', title='Iniciar Sesión', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Ruta para el registro de nuevos usuarios de sucursal.
    
    GET: Muestra el formulario de registro
    POST: Procesa el registro y crea el nuevo usuario
    """
    
    # Si el usuario ya está autenticado, redirigir a la página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Instanciar el formulario de registro
    form = RegistrationForm()
    
    # Procesar el formulario si se envió via POST y es válido
    if form.validate_on_submit():
        try:
            # Crear nueva instancia de Usuario
            user = User(
                username=form.username.data.strip(),
                email=form.email.data.strip().lower(),
                branch_name=form.branch_name.data.strip(),
                role='branch_user',  # Por defecto, usuarios de sucursal
                is_active=True,      # Los nuevos usuarios están activos por defecto
                is_admin=False       # No son administradores por defecto
            )
            
            # Establecer la contraseña (será hasheada automáticamente)
            user.set_password(form.password.data)
            
            # Añadir el usuario a la sesión de la base de datos
            db.session.add(user)
            
            # Confirmar los cambios en la base de datos
            db.session.commit()
            
            # Mostrar mensaje de éxito
            flash(
                f'¡Registro exitoso! Usuario "{user.username}" creado para la sucursal "{user.branch_name}". '
                'Ya puedes iniciar sesión.',
                'success'
            )
            
            # Redirigir al formulario de login
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            # En caso de error, hacer rollback y mostrar mensaje
            db.session.rollback()
            flash(
                'Ocurrió un error al crear el usuario. Por favor, inténtalo de nuevo.',
                'error'
            )
            
            # Log del error para debugging (en producción usar logging apropiado)
            print(f"Error en registro de usuario: {str(e)}")
    
    # Renderizar el formulario de registro (GET o si hay errores)
    return render_template('auth/register.html', title='Registrar Usuario', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Ruta para cerrar la sesión del usuario actual.
    Requiere que el usuario esté autenticado.
    """
    
    # Obtener información del usuario antes de cerrar sesión
    username = current_user.username
    
    # Cerrar la sesión del usuario
    logout_user()
    
    # Mostrar mensaje de despedida
    flash(f'Sesión cerrada correctamente. ¡Hasta luego, {username}!', 'info')
    
    # Redirigir a la página de inicio de sesión
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """
    Ruta para mostrar el perfil del usuario actual.
    """
    return render_template('auth/profile.html', title='Mi Perfil', user=current_user)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Ruta para que los usuarios cambien su contraseña.
    """
    from app.forms.auth_forms import ChangePasswordForm
    
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verificar contraseña actual
        if current_user.check_password(form.current_password.data):
            try:
                # Establecer nueva contraseña
                current_user.set_password(form.new_password.data)
                db.session.commit()
                
                flash('Contraseña actualizada correctamente.', 'success')
                return redirect(url_for('auth.profile'))
                
            except Exception as e:
                db.session.rollback()
                flash('Error al actualizar la contraseña.', 'error')
        else:
            flash('La contraseña actual es incorrecta.', 'error')
    
    return render_template('auth/change_password.html', title='Cambiar Contraseña', form=form)


# Manejadores de errores específicos para el blueprint de autenticación
@auth_bp.errorhandler(404)
def auth_not_found(error):
    """Manejador de error 404 específico para rutas de autenticación."""
    flash('La página que buscas no existe.', 'error')
    return redirect(url_for('auth.login'))


# Context processor para el blueprint de autenticación
@auth_bp.context_processor
def inject_auth_data():
    """
    Inyectar datos útiles en todas las plantillas del blueprint de autenticación.
    """
    return {
        'app_name': 'Sistema de Control de Sucursales',
        'current_year': 2025
    }