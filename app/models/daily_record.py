# app/models/daily_record.py
"""
Modelo de base de datos para los registros diarios de ventas y gastos.

Este modelo almacena la información diaria de cada sucursal incluyendo:
- Ventas totales desglosadas por método de pago
- Gastos totales del día
- Información de auditoría y trazabilidad
"""

from app import db
import datetime
from sqlalchemy import event
from sqlalchemy.orm import validates


class DailyRecord(db.Model):
    """
    Modelo para almacenar los registros diarios de ventas y gastos de cada sucursal.
    
    Attributes:
        id: Identificador único del registro
        user_id: ID del usuario que creó el registro
        branch_name: Nombre de la sucursal
        record_date: Fecha del registro
        total_sales: Ventas totales del día
        cash_sales: Ventas en efectivo
        mercadopago_sales: Ventas por MercadoPago
        debit_sales: Ventas con tarjeta de débito
        credit_sales: Ventas con tarjeta de crédito
        total_expenses: Gastos totales del día
        created_at: Timestamp de creación del registro
        updated_at: Timestamp de última actualización
        user: Relación con el modelo User
    """
    
    __tablename__ = 'daily_records'
    
    # Columnas principales
    id = db.Column(db.Integer, primary_key=True)
    
    # Relación con usuario
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Información de la sucursal
    branch_name = db.Column(db.String(100), nullable=False, index=True)
    
    # Fecha del registro
    record_date = db.Column(
        db.Date,
        nullable=False,
        default=datetime.date.today,
        index=True
    )
    
    # Ventas desglosadas por método de pago
    total_sales = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0.00
    )
    
    cash_sales = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0.00
    )
    
    mercadopago_sales = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0.00
    )
    
    debit_sales = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0.00
    )
    
    credit_sales = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0.00
    )
    
    # Gastos del día
    total_expenses = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0.00
    )
    
    # Campos de auditoría
    created_at = db.Column(
        db.DateTime,
        default=datetime.datetime.now,
        nullable=False
    )
    
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        nullable=False
    )
    
    # Campos adicionales opcionales
    notes = db.Column(db.Text, nullable=True)
    
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    
    verified_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True
    )
    
    verified_at = db.Column(db.DateTime, nullable=True)
    
    # Restricción de unicidad: una sucursal solo puede tener un registro por día
    __table_args__ = (
        db.UniqueConstraint(
            'branch_name', 
            'record_date', 
            name='_branch_date_uc'
        ),
        db.Index('idx_branch_date', 'branch_name', 'record_date'),
        db.Index('idx_user_date', 'user_id', 'record_date'),
        db.CheckConstraint('total_sales >= 0', name='check_total_sales_positive'),
        db.CheckConstraint('cash_sales >= 0', name='check_cash_sales_positive'),
        db.CheckConstraint('mercadopago_sales >= 0', name='check_mercadopago_sales_positive'),
        db.CheckConstraint('debit_sales >= 0', name='check_debit_sales_positive'),
        db.CheckConstraint('credit_sales >= 0', name='check_credit_sales_positive'),
        db.CheckConstraint('total_expenses >= 0', name='check_total_expenses_positive')
    )
    
    # Las relaciones inversas se gestionan mediante 'backref' en el modelo User
    # No definimos db.relationship aquí para evitar conflictos
    
    def __init__(self, **kwargs):
        """
        Constructor del modelo DailyRecord.
        
        Args:
            **kwargs: Argumentos keyword para inicializar el modelo
        """
        super(DailyRecord, self).__init__(**kwargs)
        
        # Auto-calcular total_sales si no se proporciona
        if not kwargs.get('total_sales'):
            self.calculate_total_sales()
    
    def __repr__(self):
        """
        Representación string del objeto DailyRecord.
        
        Returns:
            str: Representación legible del registro diario
        """
        return (
            f'<DailyRecord {self.id}: {self.branch_name} - '
            f'{self.record_date} - Ventas: ${self.total_sales:.2f}>'
        )
    
    def __str__(self):
        """
        Representación string amigable del objeto.
        
        Returns:
            str: Descripción del registro para mostrar al usuario
        """
        return f'{self.branch_name} - {self.record_date.strftime("%d/%m/%Y")}'
    
    @validates('total_sales', 'cash_sales', 'mercadopago_sales', 'debit_sales', 'credit_sales', 'total_expenses')
    def validate_positive_amounts(self, key, value):
        """
        Validador para asegurar que los montos sean positivos.
        
        Args:
            key: Nombre del campo
            value: Valor a validar
            
        Returns:
            float: Valor validado
            
        Raises:
            ValueError: Si el valor es negativo
        """
        if value is not None and float(value) < 0:
            raise ValueError(f'{key} debe ser un valor positivo')
        return float(value) if value is not None else 0.00
    
    @validates('record_date')
    def validate_record_date(self, key, value):
        """
        Validador para la fecha del registro.
        
        Args:
            key: Nombre del campo
            value: Fecha a validar
            
        Returns:
            date: Fecha validada
            
        Raises:
            ValueError: Si la fecha es futura
        """
        if value and value > datetime.date.today():
            raise ValueError('La fecha del registro no puede ser futura')
        return value
    
    def calculate_total_sales(self):
        """
        Calcula el total de ventas sumando todos los métodos de pago.
        
        Returns:
            float: Total calculado de ventas
        """
        self.total_sales = (
            (self.cash_sales or 0) +
            (self.mercadopago_sales or 0) +
            (self.debit_sales or 0) +
            (self.credit_sales or 0)
        )
        return self.total_sales
    
    def get_net_amount(self):
        """
        Calcula el monto neto (ventas - gastos).
        
        Returns:
            float: Monto neto del día
        """
        return float(self.total_sales) - float(self.total_expenses)
    
    def get_payment_breakdown(self):
        """
        Obtiene el desglose de métodos de pago.
        
        Returns:
            dict: Diccionario con el desglose de pagos
        """
        return {
            'cash': float(self.cash_sales),
            'mercadopago': float(self.mercadopago_sales),
            'debit': float(self.debit_sales),
            'credit': float(self.credit_sales),
            'total': float(self.total_sales)
        }
    
    def get_payment_percentages(self):
        """
        Obtiene los porcentajes de cada método de pago.
        
        Returns:
            dict: Diccionario con porcentajes de cada método
        """
        if float(self.total_sales) == 0:
            return {
                'cash': 0, 'mercadopago': 0, 
                'debit': 0, 'credit': 0
            }
        
        total = float(self.total_sales)
        return {
            'cash': round((float(self.cash_sales) / total) * 100, 2),
            'mercadopago': round((float(self.mercadopago_sales) / total) * 100, 2),
            'debit': round((float(self.debit_sales) / total) * 100, 2),
            'credit': round((float(self.credit_sales) / total) * 100, 2)
        }
    
    def verify_record(self, verifier_user):
        """
        Verifica el registro diario.
        
        Args:
            verifier_user: Usuario que verifica el registro
        """
        self.is_verified = True
        self.verified_by = verifier_user.id
        self.verified_at = datetime.datetime.now()
    
    def unverify_record(self):
        """
        Desmarca el registro como verificado.
        """
        self.is_verified = False
        self.verified_by = None
        self.verified_at = None
    
    def to_dict(self):
        """
        Convierte el objeto a diccionario para serialización JSON.
        
        Returns:
            dict: Representación en diccionario del objeto
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'branch_name': self.branch_name,
            'record_date': self.record_date.isoformat() if self.record_date else None,
            'total_sales': float(self.total_sales),
            'cash_sales': float(self.cash_sales),
            'mercadopago_sales': float(self.mercadopago_sales),
            'debit_sales': float(self.debit_sales),
            'credit_sales': float(self.credit_sales),
            'total_expenses': float(self.total_expenses),
            'net_amount': self.get_net_amount(),
            'notes': self.notes,
            'is_verified': self.is_verified,
            'verified_by': self.verified_by,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'creator': {
                'id': self.creator.id,
                'username': self.creator.username,
                'branch_name': self.creator.branch_name
            } if hasattr(self, 'creator') and self.creator else None,
            'verifier_info': {
                'id': self.verifier.id,
                'username': self.verifier.username
            } if hasattr(self, 'verifier') and self.verifier else None
        }
    
    @classmethod
    def get_by_branch_and_date(cls, branch_name, record_date):
        """
        Obtiene un registro por sucursal y fecha.
        
        Args:
            branch_name: Nombre de la sucursal
            record_date: Fecha del registro
            
        Returns:
            DailyRecord: Registro encontrado o None
        """
        return cls.query.filter_by(
            branch_name=branch_name,
            record_date=record_date
        ).first()
    
    @classmethod
    def get_by_user_and_date_range(cls, user_id, start_date, end_date):
        """
        Obtiene registros de un usuario en un rango de fechas.
        
        Args:
            user_id: ID del usuario
            start_date: Fecha de inicio
            end_date: Fecha de fin
            
        Returns:
            Query: Query con los registros filtrados
        """
        return cls.query.filter(
            cls.user_id == user_id,
            cls.record_date >= start_date,
            cls.record_date <= end_date
        ).order_by(cls.record_date.desc())
    
    @classmethod
    def get_monthly_summary(cls, branch_name, year, month):
        """
        Obtiene resumen mensual de una sucursal.
        
        Args:
            branch_name: Nombre de la sucursal
            year: Año
            month: Mes
            
        Returns:
            dict: Resumen con totales del mes
        """
        from sqlalchemy import func, extract
        
        records = cls.query.filter(
            cls.branch_name == branch_name,
            extract('year', cls.record_date) == year,
            extract('month', cls.record_date) == month
        ).all()
        
        if not records:
            return None
        
        total_sales = sum(float(r.total_sales) for r in records)
        total_expenses = sum(float(r.total_expenses) for r in records)
        
        return {
            'branch_name': branch_name,
            'year': year,
            'month': month,
            'total_records': len(records),
            'total_sales': total_sales,
            'total_expenses': total_expenses,
            'net_amount': total_sales - total_expenses,
            'avg_daily_sales': total_sales / len(records) if records else 0,
            'payment_breakdown': {
                'cash': sum(float(r.cash_sales) for r in records),
                'mercadopago': sum(float(r.mercadopago_sales) for r in records),
                'debit': sum(float(r.debit_sales) for r in records),
                'credit': sum(float(r.credit_sales) for r in records)
            }
        }
    
    # Campo para trackear si el registro fue retirado de la bandeja
    is_withdrawn = db.Column(db.Boolean, default=False, nullable=False)
    
    withdrawn_at = db.Column(db.DateTime, nullable=True)
    
    withdrawn_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True
    )

    def mark_as_withdrawn(self, user):
        """Marcar el registro como retirado de la bandeja."""
        self.is_withdrawn = True
        self.withdrawn_at = datetime.datetime.now()
        self.withdrawn_by = user.id

    def unmark_withdrawn(self):
        """Desmarcar el registro como retirado (para correcciones)."""
        self.is_withdrawn = False
        self.withdrawn_at = None
        self.withdrawn_by = None


# Event listeners para automatización
@event.listens_for(DailyRecord, 'before_insert')
@event.listens_for(DailyRecord, 'before_update')
def auto_calculate_totals(mapper, connection, target):
    """
    Event listener para calcular automáticamente los totales antes de guardar.
    
    Args:
        mapper: Mapper de SQLAlchemy
        connection: Conexión de base de datos
        target: Instancia del modelo DailyRecord
    """
    target.calculate_total_sales()


@event.listens_for(DailyRecord, 'before_update')
def update_timestamp(mapper, connection, target):
    """
    Event listener para actualizar el timestamp de modificación.
    
    Args:
        mapper: Mapper de SQLAlchemy
        connection: Conexión de base de datos
        target: Instancia del modelo DailyRecord
    """
    target.updated_at = datetime.datetime.now()