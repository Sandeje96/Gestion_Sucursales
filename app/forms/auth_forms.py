# app/forms/auth_forms.py
"""
Formularios WTForms para autenticación del sistema de control de sucursales.

Este módulo contiene:
- LoginForm: Para el inicio de sesión de usuarios
- RegistrationForm: Para el registro de nuevos usuarios de sucursal
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, ValidationError, EqualTo, Length, Email, Regexp
from app.models.user import User


class LoginForm(FlaskForm):
    """
    Formulario para el inicio de sesión de usuarios.
    
    Campos:
    - username: Nombre de usuario (requerido)
    - password: Contraseña (requerido)
    - remember_me: Mantener sesión iniciada (opcional)
    """
    
    username = StringField(
        'Nombre de Usuario',
        validators=[
            DataRequired(message='El nombre de usuario es obligatorio.'),
            Length(min=3, max=50, message='El nombre de usuario debe tener entre 3 y 50 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ingresa tu nombre de usuario',
            'class': 'form-control',
            'autocomplete': 'username'
        }
    )
    
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es obligatoria.')
        ],
        render_kw={
            'placeholder': 'Ingresa tu contraseña',
            'class': 'form-control',
            'autocomplete': 'current-password'
        }
    )
    
    remember_me = BooleanField(
        'Mantener sesión iniciada',
        render_kw={
            'class': 'form-check-input'
        }
    )
    
    submit = SubmitField(
        'Iniciar Sesión',
        render_kw={
            'class': 'btn btn-primary w-100'
        }
    )


class RegistrationForm(FlaskForm):
    """
    Formulario para el registro de nuevos usuarios de sucursal.
    
    Campos:
    - username: Nombre de usuario (requerido, único)
    - email: Correo electrónico (requerido, único)
    - password: Contraseña (requerido, mínimo 6 caracteres)
    - password2: Confirmación de contraseña (debe coincidir)
    - branch_name: Nombre de la sucursal (requerido, único)
    - role: Rol del usuario (oculto, por defecto 'branch_user')
    """
    
    username = StringField(
        'Nombre de Usuario',
        validators=[
            DataRequired(message='El nombre de usuario es obligatorio.'),
            Length(min=3, max=50, message='El nombre de usuario debe tener entre 3 y 50 caracteres.'),
            Regexp(
                r'^[a-zA-Z0-9_]+$',
                message='El nombre de usuario solo puede contener letras, números y guiones bajos.'
            )
        ],
        render_kw={
            'placeholder': 'Elige un nombre de usuario único',
            'class': 'form-control',
            'autocomplete': 'username'
        }
    )
    
    email = StringField(
        'Correo Electrónico',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Email(message='Ingresa un correo electrónico válido.'),
            Length(max=120, message='El correo electrónico no puede exceder 120 caracteres.')
        ],
        render_kw={
            'placeholder': 'tu@email.com',
            'class': 'form-control',
            'autocomplete': 'email',
            'type': 'email'
        }
    )
    
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es obligatoria.'),
            Length(min=6, max=128, message='La contraseña debe tener entre 6 y 128 caracteres.')
        ],
        render_kw={
            'placeholder': 'Mínimo 6 caracteres',
            'class': 'form-control',
            'autocomplete': 'new-password'
        }
    )
    
    password2 = PasswordField(
        'Confirmar Contraseña',
        validators=[
            DataRequired(message='Debes confirmar tu contraseña.'),
            EqualTo('password', message='Las contraseñas deben coincidir.')
        ],
        render_kw={
            'placeholder': 'Repite tu contraseña',
            'class': 'form-control',
            'autocomplete': 'new-password'
        }
    )
    
    branch_name = StringField(
        'Nombre de la Sucursal',
        validators=[
            DataRequired(message='El nombre de la sucursal es obligatorio.'),
            Length(min=2, max=100, message='El nombre de la sucursal debe tener entre 2 y 100 caracteres.'),
            Regexp(
                r'^[a-zA-Z0-9\s\-_\.]+$',
                message='El nombre de la sucursal contiene caracteres no válidos.'
            )
        ],
        render_kw={
            'placeholder': 'Ej: Sucursal Centro, Sucursal Norte',
            'class': 'form-control'
        }
    )
    
    # Campo oculto para el rol - por defecto será 'branch_user'
    role = HiddenField(
        'Rol',
        default='branch_user'
    )
    
    submit = SubmitField(
        'Registrar Usuario',
        render_kw={
            'class': 'btn btn-success w-100'
        }
    )
    
    def validate_username(self, username):
        """
        Validador personalizado para asegurar que el nombre de usuario sea único.
        
        Args:
            username: Campo del nombre de usuario
            
        Raises:
            ValidationError: Si el nombre de usuario ya existe
        """
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError(
                'Este nombre de usuario ya está registrado. '
                'Por favor, elige uno diferente.'
            )
    
    def validate_email(self, email):
        """
        Validador personalizado para asegurar que el correo electrónico sea único.
        
        Args:
            email: Campo del correo electrónico
            
        Raises:
            ValidationError: Si el correo electrónico ya existe
        """
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError(
                'Este correo electrónico ya está registrado. '
                'Por favor, usa uno diferente.'
            )
    
    def validate_branch_name(self, branch_name):
        """
        Validador personalizado para asegurar que el nombre de la sucursal sea único.
        
        Args:
            branch_name: Campo del nombre de la sucursal
            
        Raises:
            ValidationError: Si el nombre de la sucursal ya existe
        """
        # Normalizar el nombre para la comparación (sin espacios extra, minúsculas)
        normalized_name = ' '.join(branch_name.data.strip().split()).lower()
        
        # Buscar usuarios con nombres de sucursal similares
        existing_user = User.query.filter(
            User.branch_name.ilike(f'%{normalized_name}%')
        ).first()
        
        if existing_user:
            raise ValidationError(
                'Ya existe una sucursal con un nombre similar. '
                'Por favor, elige un nombre diferente.'
            )


class AdminRegistrationForm(RegistrationForm):
    """
    Formulario extendido para que los administradores registren usuarios.
    Incluye campos adicionales y opciones que no están disponibles en el registro público.
    """
    
    # Sobrescribir el campo role para permitir selección
    from wtforms import SelectField
    
    role = SelectField(
        'Rol del Usuario',
        choices=[
            ('branch_user', 'Usuario de Sucursal'),
            ('admin', 'Administrador')
        ],
        default='branch_user',
        validators=[DataRequired(message='Debes seleccionar un rol.')],
        render_kw={
            'class': 'form-select'
        }
    )
    
    notes = TextAreaField(
        'Notas Adicionales',
        validators=[
            Length(max=500, message='Las notas no pueden exceder 500 caracteres.')
        ],
        render_kw={
            'placeholder': 'Información adicional sobre el usuario (opcional)',
            'class': 'form-control',
            'rows': 3
        }
    )
    
    def validate_branch_name(self, branch_name):
        """
        Validador personalizado para administradores.
        Los administradores pueden no tener sucursal asignada.
        """
        # Si es administrador, la sucursal es opcional
        if self.role.data == 'admin':
            return
        
        # Si es usuario de sucursal, aplicar validación normal
        if not branch_name.data or not branch_name.data.strip():
            raise ValidationError(
                'Los usuarios de sucursal deben tener una sucursal asignada.'
            )
        
        # Llamar a la validación padre
        super().validate_branch_name(branch_name)