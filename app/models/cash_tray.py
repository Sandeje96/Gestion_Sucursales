# app/models/cash_tray.py
"""
Modelo para el manejo de bandejas de efectivo por sucursal.
Trackea el dinero acumulado que está pendiente de retiro.
"""

from app import db
import datetime
from sqlalchemy import event


class CashTray(db.Model):
    """
    Modelo para almacenar el efectivo acumulado por sucursal y método de pago.
    Se actualiza automáticamente cuando se crean/modifican registros diarios.
    """
    
    __tablename__ = 'cash_trays'
    
    # Columnas principales
    id = db.Column(db.Integer, primary_key=True)
    
    # Información de la sucursal
    branch_name = db.Column(db.String(100), nullable=False, index=True)
    
    # Acumulados por método de pago
    accumulated_cash = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0.00
    )
    
    accumulated_mercadopago = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0.00
    )
    
    accumulated_debit = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0.00
    )
    
    accumulated_credit = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0.00
    )

    # Gastos en efectivo acumulados (a descontar del efectivo disponible)
    accumulated_cash_expenses = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0.00
    )
    
    # Metadatos
    last_updated = db.Column(
        db.DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        nullable=False
    )
    
    created_at = db.Column(
        db.DateTime,
        default=datetime.datetime.now,
        nullable=False
    )
    
    # Restricción de unicidad: una fila por sucursal
    __table_args__ = (
        db.UniqueConstraint('branch_name', name='_branch_tray_uc'),
        db.CheckConstraint('accumulated_cash >= 0', name='check_accumulated_cash_positive'),
        db.CheckConstraint('accumulated_mercadopago >= 0', name='check_accumulated_mercadopago_positive'),
        db.CheckConstraint('accumulated_debit >= 0', name='check_accumulated_debit_positive'),
        db.CheckConstraint('accumulated_credit >= 0', name='check_accumulated_credit_positive'),
        db.CheckConstraint('accumulated_cash_expenses >= 0', name='check_accumulated_cash_expenses_positive')
    )
    
    def __repr__(self):
        return f'<CashTray {self.branch_name}: ${self.get_total_accumulated():.2f}>'
    
    def get_total_accumulated(self):
        """Obtener el total acumulado en la bandeja."""
        return float(
            (self.get_available_cash() or 0) +
            (self.accumulated_mercadopago or 0) +
            (self.accumulated_debit or 0) +
            (self.accumulated_credit or 0)
        )

    def get_available_cash(self):
        """Obtener el efectivo disponible (ventas en efectivo - gastos en efectivo)."""
        return float((self.accumulated_cash or 0) - (self.accumulated_cash_expenses or 0))
    
    def add_amounts(self, cash=0, mercadopago=0, debit=0, credit=0):
        """Agregar montos a la bandeja."""
        self.accumulated_cash = float(self.accumulated_cash or 0) + float(cash)
        self.accumulated_mercadopago = float(self.accumulated_mercadopago or 0) + float(mercadopago)
        self.accumulated_debit = float(self.accumulated_debit or 0) + float(debit)
        self.accumulated_credit = float(self.accumulated_credit or 0) + float(credit)
        self.last_updated = datetime.datetime.now()
    
    def subtract_amounts(self, cash=0, mercadopago=0, debit=0, credit=0):
        """Restar montos de la bandeja (para cuando se modifica/elimina un registro)."""
        self.accumulated_cash = max(0, float(self.accumulated_cash or 0) - float(cash))
        self.accumulated_mercadopago = max(0, float(self.accumulated_mercadopago or 0) - float(mercadopago))
        self.accumulated_debit = max(0, float(self.accumulated_debit or 0) - float(debit))
        self.accumulated_credit = max(0, float(self.accumulated_credit or 0) - float(credit))
        self.last_updated = datetime.datetime.now()
    
    def empty_tray(self):
        """Vaciar completamente la bandeja."""
        self.accumulated_cash = 0.00
        self.accumulated_mercadopago = 0.00
        self.accumulated_debit = 0.00
        self.accumulated_credit = 0.00
        self.accumulated_cash_expenses = 0.00
        self.last_updated = datetime.datetime.now()
    
    def to_dict(self):
        """Convertir a diccionario para serialización JSON."""
        return {
            'id': self.id,
            'branch_name': self.branch_name,
            'accumulated_cash': float(self.accumulated_cash or 0),
            'accumulated_mercadopago': float(self.accumulated_mercadopago or 0),
            'accumulated_debit': float(self.accumulated_debit or 0),
            'accumulated_credit': float(self.accumulated_credit or 0),
            'accumulated_cash_expenses': float(self.accumulated_cash_expenses or 0),
            'available_cash': self.get_available_cash(),
            'total_accumulated': self.get_total_accumulated(),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def get_or_create_for_branch(cls, branch_name):
        """Obtener o crear una bandeja para una sucursal."""
        tray = cls.query.filter_by(branch_name=branch_name).first()
        if not tray:
            tray = cls(branch_name=branch_name)
            db.session.add(tray)
            db.session.flush()  # Para obtener el ID sin commit
        return tray
    
    @classmethod
    def get_all_trays_summary(cls):
        """Obtener resumen de todas las bandejas."""
        trays = cls.query.all()
        
        total_available_cash = sum(t.get_available_cash() for t in trays)
        total_mercadopago = sum(float(t.accumulated_mercadopago or 0) for t in trays)
        total_debit = sum(float(t.accumulated_debit or 0) for t in trays)
        total_credit = sum(float(t.accumulated_credit or 0) for t in trays)
        
        return {
            'trays': [tray.to_dict() for tray in trays],
            'totals': {
                'cash': total_available_cash,  # Ahora usa efectivo disponible
                'mercadopago': total_mercadopago,
                'debit': total_debit,
                'credit': total_credit,
                'total': total_available_cash + total_mercadopago + total_debit + total_credit
            },
            'branches_count': len(trays),
            'last_updated': max([t.last_updated for t in trays]) if trays else None
        }
    
    @classmethod
    def recalculate_all_trays(cls):
        """Recalcular todas las bandejas basándose en los registros diarios."""
        from app.models.daily_record import DailyRecord
        
        # Limpiar todas las bandejas existentes
        cls.query.delete()
        
        # Obtener todas las sucursales que tienen registros
        branches = db.session.query(DailyRecord.branch_name).distinct().all()
        
        for (branch_name,) in branches:
            # Crear nueva bandeja para la sucursal
            tray = cls(branch_name=branch_name)
            
            # Sumar todos los registros de esa sucursal que NO están retirados
            records = DailyRecord.query.filter_by(
                branch_name=branch_name,
                is_withdrawn=False  # Solo registros NO retirados
            ).all()
            
            for record in records:
                # Agregar ventas
                tray.add_amounts(
                    cash=record.cash_sales or 0,
                    mercadopago=record.mercadopago_sales or 0,
                    debit=record.debit_sales or 0,
                    credit=record.credit_sales or 0
                )
                # Agregar gastos en efectivo
                tray.add_expense_amount(record.total_expenses or 0)
            
            db.session.add(tray)
        
        db.session.commit()

    def add_expense_amount(self, expense_amount=0):
        """Agregar monto de gastos en efectivo a la bandeja."""
        if expense_amount > 0:
            from decimal import Decimal
            if self.accumulated_cash_expenses is None:
                self.accumulated_cash_expenses = Decimal('0.00')
            # Convertir a Decimal antes de sumar
            self.accumulated_cash_expenses += Decimal(str(expense_amount))
            self.last_updated = datetime.datetime.now()

    def subtract_expense_amount(self, expense_amount=0):
        """Restar monto de gastos en efectivo de la bandeja (para reversiones)."""
        if expense_amount > 0:
            from decimal import Decimal
            if self.accumulated_cash_expenses is None:
                self.accumulated_cash_expenses = Decimal('0.00')
            # Convertir a Decimal y usar max para evitar negativos
            self.accumulated_cash_expenses = max(
                Decimal('0.00'), 
                self.accumulated_cash_expenses - Decimal(str(expense_amount))
            )
            self.last_updated = datetime.datetime.now()


# Event listeners para mantener las bandejas actualizadas automáticamente
@event.listens_for(db.session, 'after_commit')
def update_cash_trays_on_commit(session):
    """Actualizar bandejas después de cada commit."""
    # Solo procesar si hay cambios en DailyRecord
    from app.models.daily_record import DailyRecord
    
    has_daily_record_changes = False
    
    for obj in session.new:
        if isinstance(obj, DailyRecord):
            has_daily_record_changes = True
            # Agregar a la bandeja
            tray = CashTray.get_or_create_for_branch(obj.branch_name)
            tray.add_amounts(
                cash=obj.cash_sales or 0,
                mercadopago=obj.mercadopago_sales or 0,
                debit=obj.debit_sales or 0,
                credit=obj.credit_sales or 0
            )
            # Agregar gastos en efectivo
            tray.add_expense_amount(obj.total_expenses or 0)
    
    for obj in session.dirty:
        if isinstance(obj, DailyRecord):
            has_daily_record_changes = True
            # Esto es más complejo porque necesitamos los valores anteriores
            # Por simplicidad, recalcularemos la bandeja específica
            tray = CashTray.get_or_create_for_branch(obj.branch_name)
            tray.empty_tray()
            
            # Recalcular basándose en todos los registros NO retirados de esa sucursal
            records = DailyRecord.query.filter_by(
                branch_name=obj.branch_name,
                is_withdrawn=False
            ).all()
            for record in records:
                tray.add_amounts(
                    cash=record.cash_sales or 0,
                    mercadopago=record.mercadopago_sales or 0,
                    debit=record.debit_sales or 0,
                    credit=record.credit_sales or 0
                )
                # Agregar gastos en efectivo
                tray.add_expense_amount(record.total_expenses or 0)
    
    for obj in session.deleted:
        if isinstance(obj, DailyRecord):
            has_daily_record_changes = True
            # Restar de la bandeja
            tray = CashTray.get_or_create_for_branch(obj.branch_name)
            tray.subtract_amounts(
                cash=obj.cash_sales or 0,
                mercadopago=obj.mercadopago_sales or 0,
                debit=obj.debit_sales or 0,
                credit=obj.credit_sales or 0
            )
            # Restar gastos en efectivo
            tray.subtract_expense_amount(obj.total_expenses or 0)
    
    if has_daily_record_changes:
        db.session.commit()