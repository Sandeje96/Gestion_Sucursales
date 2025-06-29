# app/models/user.py
"""Modelo de usuario para el sistema de control de sucursales.
Este modelo maneja la autenticación y autorización de usuarios,
incluyendo administradores y usuarios de sucursal."""

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from app.models.daily_record import DailyRecord # Importación necesaria para relaciones

class User(UserMixin, db.Model):
    """
    Modelo de usuario que extiende UserMixin de Flask-Login.

    Attributes:
        id: Identificador único del usuario
        username: Nombre de usuario único
        email: Correo electrónico único
        password_hash: Hash de la contraseña
        role: Rol del usuario ('admin' o 'branch_user')
        branch_name: Nombre de la sucursal (para usuarios de sucursal)
        is_active: Estado activo del usuario
        is_admin: Indicador de si es administrador
        created_at: Timestamp de creación
        last_login: Timestamp del último login
        daily_records: Relación con registros diarios creados
        verified_records: Relación con registros diarios verificados
    """

    __tablename__ = 'users'

    # Columnas principales
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True
    )
    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )
    password_hash = db.Column(db.String(255), nullable=False)

    # Información del rol y sucursal
    role = db.Column(
        db.String(20),
        nullable=False,
        default='branch_user',
        index=True
    )
    branch_name = db.Column(db.String(100), nullable=True, index=True)

    # Estado del usuario
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(
        db.DateTime,
        default=datetime.datetime.now,
        nullable=False
    )
    last_login = db.Column(db.DateTime, nullable=True)

    # Información adicional
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    # Relación para registros creados por este usuario
    # SQLAlchemy ahora sabe que debe usar DailyRecord.user_id para esta relación
    daily_records = db.relationship(
        'DailyRecord',
        foreign_keys=[DailyRecord.user_id],  # Clave foránea explícita
        backref='creator',                   # Permite acceder al usuario desde DailyRecord.creator
        lazy='dynamic',                      # Permite construir queries sobre la relación
        cascade='all, delete-orphan'         # Elimina los registros diarios si se elimina el usuario creador
    )

    # Nueva relación para registros verificados por este usuario
    # SQLAlchemy ahora sabe que debe usar DailyRecord.verified_by para esta relación
    verified_records = db.relationship(
        'DailyRecord',
        foreign_keys=[DailyRecord.verified_by], # Clave foránea explícita
        backref='verifier',                      # Permite acceder al usuario desde DailyRecord.verifier
        lazy='dynamic'                           # Permite construir queries sobre la relación
    )

    def __init__(self, **kwargs):
        """
        Constructor del modelo User.

        Args:
            **kwargs: Argumentos keyword para inicializar el usuario
        """
        super(User, self).__init__(**kwargs)

        # Auto-detectar si es admin basado en el rol
        if self.role == 'admin':
            self.is_admin = True

        # Si es usuario de sucursal pero no tiene branch_name, usar username como default
        if self.role == 'branch_user' and not self.branch_name:
            self.branch_name = f"Sucursal {self.username}"

    def __repr__(self):
        """
        Representación string del objeto User.

        Returns:
            str: Representación legible del usuario
        """
        return f'<User {self.username} ({self.role})>'

    def __str__(self):
        """
        Representación string amigable del objeto.

        Returns:
            str: Nombre del usuario para mostrar en interfaces
        """
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        return self.username

    def set_password(self, password):
        """
        Establece la contraseña del usuario creando un hash seguro.

        Args:
            password (str): Contraseña en texto plano
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verifica si la contraseña proporcionada coincide con el hash almacenado.

        Args:
            password (str): Contraseña en texto plano a verificar

        Returns:
            bool: True si la contraseña es correcta, False en caso contrario
        """
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """
        Obtiene el ID del usuario como string (requerido por Flask-Login).

        Returns:
            str: ID del usuario como string
        """
        return str(self.id)

    def is_admin_user(self):
        """
        Verifica si el usuario es administrador.

        Returns:
            bool: True si es administrador
        """
        return self.role == 'admin' and self.is_admin

    def is_branch_user(self):
        """
        Verifica si el usuario es de sucursal.

        Returns:
            bool: True si es usuario de sucursal
        """
        return self.role == 'branch_user'

    def can_verify_records(self):
        """
        Verifica si el usuario puede verificar registros.

        Returns:
            bool: True si puede verificar registros
        """
        return self.is_admin_user()

    def can_edit_record(self, daily_record):
        """
        Verifica si el usuario puede editar un registro específico.

        Args:
            daily_record: Instancia de DailyRecord

        Returns:
            bool: True si puede editar el registro
        """
        # Los admins pueden editar cualquier registro
        if self.is_admin_user():
            return True

        # Los usuarios de sucursal solo pueden editar sus propios registros
        if self.is_branch_user():
            return daily_record.user_id == self.id

        return False

    def can_view_record(self, daily_record):
        """
        Verifica si el usuario puede ver un registro específico.

        Args:
            daily_record: Instancia de DailyRecord

        Returns:
            bool: True si puede ver el registro
        """
        # Los admins pueden ver cualquier registro
        if self.is_admin_user():
            return True

        # Los usuarios de sucursal pueden ver registros de su sucursal
        if self.is_branch_user():
            return (daily_record.user_id == self.id or
                    daily_record.branch_name == self.branch_name)

        return False

    def update_last_login(self):
        """
        Actualiza el timestamp del último login.
        """
        self.last_login = datetime.datetime.now()
        db.session.commit()

    def get_full_name(self):
        """
        Obtiene el nombre completo del usuario.

        Returns:
            str: Nombre completo o username si no hay nombre/apellido
        """
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        elif self.first_name:
            return self.first_name
        return self.username

    def get_display_name(self):
        """
        Obtiene el nombre para mostrar en la interfaz.

        Returns:
            str: Nombre para mostrar
        """
        name = self.get_full_name()
        if self.branch_name and not self.is_admin_user():
            return f'{name} - {self.branch_name}'
        return name

    def deactivate(self):
        """
        Desactiva el usuario.
        """
        self.is_active = False

    def activate(self):
        """
        Activa el usuario.
        """
        self.is_active = True

    def promote_to_admin(self):
        """
        Promueve el usuario a administrador.
        """
        self.role = 'admin'
        self.is_admin = True
        self.branch_name = None  # Los admins no tienen sucursal específica

    def demote_to_branch_user(self, branch_name):
        """
        Degrada el usuario a usuario de sucursal.

        Args:
            branch_name (str): Nombre de la sucursal a asignar
        """
        self.role = 'branch_user'
        self.is_admin = False
        self.branch_name = branch_name

    def to_dict(self):
        """
        Convierte el objeto a diccionario para serialización JSON.

        Returns:
            dict: Representación en diccionario del usuario
        """
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'branch_name': self.branch_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'full_name': self.get_full_name(),
            'display_name': self.get_display_name(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'total_records': self.daily_records.count(),
            'verified_records_count': self.verified_records.count() if self.can_verify_records() else 0
        }

    @classmethod
    def get_by_username(cls, username):
        """
        Obtiene un usuario por su nombre de usuario.

        Args:
            username (str): Nombre de usuario

        Returns:
            User: Usuario encontrado o None
        """
        return cls.query.filter_by(username=username).first()

    @classmethod
    def get_by_email(cls, email):
        """
        Obtiene un usuario por su correo electrónico.

        Args:
            email (str): Correo electrónico

        Returns:
            User: Usuario encontrado o None
        """
        return cls.query.filter_by(email=email).first()

    @classmethod
    def get_active_users(cls):
        """
        Obtiene todos los usuarios activos.

        Returns:
            Query: Query con usuarios activos
        """
        return cls.query.filter_by(is_active=True)

    @classmethod
    def get_branch_users(cls):
        """
        Obtiene todos los usuarios de sucursal.

        Returns:
            Query: Query con usuarios de sucursal
        """
        return cls.query.filter_by(role='branch_user')

    @classmethod
    def get_admin_users(cls):
        """
        Obtiene todos los usuarios administradores.

        Returns:
            Query: Query con usuarios administradores
        """
        return cls.query.filter_by(role='admin', is_admin=True)

    @classmethod
    def get_by_branch(cls, branch_name):
        """
        Obtiene usuarios de una sucursal específica.

        Args:
            branch_name (str): Nombre de la sucursal

        Returns:
            Query: Query con usuarios de la sucursal
        """
        return cls.query.filter_by(branch_name=branch_name)

    @classmethod
    def create_admin_user(cls, username, email, password, first_name=None, last_name=None):
        """
        Crea un usuario administrador.

        Args:
            username (str): Nombre de usuario
            email (str): Correo electrónico
            password (str): Contraseña
            first_name (str): Nombre opcional
            last_name (str): Apellido opcional

        Returns:
            User: Usuario administrador creado
        """
        admin = cls(
            username=username,
            email=email,
            role='admin',
            is_admin=True,
            is_active=True,
            first_name=first_name,
            last_name=last_name
        )
        admin.set_password(password)
        return admin

    @classmethod
    def create_branch_user(cls, username, email, password, branch_name, first_name=None, last_name=None):
        """
        Crea un usuario de sucursal.

        Args:
            username (str): Nombre de usuario
            email (str): Correo electrónico
            password (str): Contraseña
            branch_name (str): Nombre de la sucursal
            first_name (str): Nombre opcional
            last_name (str): Apellido opcional

        Returns:
            User: Usuario de sucursal creado
        """
        user = cls(
            username=username,
            email=email,
            role='branch_user',
            branch_name=branch_name,
            is_admin=False,
            is_active=True,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        return user
