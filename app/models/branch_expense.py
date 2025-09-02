# app/models/branch_expense.py
from app import db
import datetime
from sqlalchemy.orm import validates

CATEGORIES = ('ALQUILER', 'SUELDO', 'LUZ', 'AGUA', 'INTERNET', 'SERENO', 'OTROS')

class BranchExpense(db.Model):
    __tablename__ = 'branch_expenses'

    id = db.Column(db.Integer, primary_key=True)
    branch_name = db.Column(db.String(100), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)  # 1..12

    # Categoría + descripción: para “OTROS” permitimos múltiples ítems por mes diferenciados por descripción
    category = db.Column(db.String(20), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)  # requerido si category == OTROS

    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    paid_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    __table_args__ = (
        # Para únicas: una fila por (sucursal, año, mes, categoría, descripción)
        # Para categorías fijas usamos description='-' (ver @validates) así queda 1 solo registro por mes.
        db.UniqueConstraint('branch_name', 'year', 'month', 'category', 'description', name='uq_branch_month_cat_desc'),
        db.CheckConstraint('month BETWEEN 1 AND 12', name='check_month_valid'),
        db.CheckConstraint('amount >= 0', name='check_amount_nonnegative'),
    )

    @validates('category', 'description')
    def _normalize(self, key, value):
        if key == 'category':
            if value not in CATEGORIES:
                raise ValueError('Categoría inválida')
        if key == 'description':
            # Para categorías fijas, forzamos '-' para cumplir unicidad
            pass
        return value

    @validates('month')
    def _check_month(self, key, value):
        if value is None or int(value) < 1 or int(value) > 12:
            raise ValueError('Mes inválido')
        return int(value)

    def ensure_fixed_desc(self):
        if self.category != 'OTROS' and not self.description:
            self.description = '-'
        if self.category == 'OTROS' and (self.description is None or not self.description.strip()):
            raise ValueError('Descripción requerida para OTROS')

    def mark_paid(self, user_id):
        """Marcar como pagado y actualizar bandeja si es usuario de sucursal."""
        from app.models.user import User
        from app.models.cash_tray import CashTray
        
        self.is_paid = True
        self.paid_at = datetime.datetime.now()
        self.paid_by = user_id
        
        # Solo descontar del efectivo si es un usuario de sucursal quien lo pagó
        if user_id:
            user = User.query.get(user_id)
            if user and user.is_branch_user() and user.branch_name == self.branch_name:
                # Es usuario de sucursal pagando un gasto de su propia sucursal
                tray = CashTray.get_or_create_for_branch(self.branch_name)
                # Convertir amount a float antes de pasarlo
                amount_float = float(self.amount or 0)
                tray.add_expense_amount(amount_float)

    def unmark_paid(self):
        """Desmarcar como pagado y revertir efectivo si corresponde."""
        from app.models.user import User
        from app.models.cash_tray import CashTray
        
        # Verificar si hay que revertir el descuento de efectivo
        if self.paid_by:
            user = User.query.get(self.paid_by)
            if user and user.is_branch_user() and user.branch_name == self.branch_name:
                # Era usuario de sucursal, revertir descuento
                tray = CashTray.get_or_create_for_branch(self.branch_name)
                # Convertir amount a float antes de pasarlo
                amount_float = float(self.amount or 0)
                tray.subtract_expense_amount(amount_float)
        
        self.is_paid = False
        self.paid_at = None
        self.paid_by = None

    @staticmethod
    def required_categories_for_branch(branch_name: str):
        base = ['ALQUILER', 'SUELDO', 'LUZ', 'AGUA', 'INTERNET']
        if branch_name and branch_name.strip().lower() == 'tacuari':
            base.append('SERENO')
        return base

    @staticmethod
    def can_edit_category(user, branch_name: str, category: str):
        if getattr(user, 'is_admin_user', lambda: False)():
            return True
        # Sucursal: solo su propia sucursal y categorías habilitadas
        if getattr(user, 'is_branch_user', lambda: False)() and user.branch_name == branch_name:
            return category in ('LUZ', 'AGUA', 'INTERNET', 'OTROS') or (
                category == 'SERENO' and branch_name.strip().lower() == 'tacuari'
            )
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'branch_name': self.branch_name,
            'year': self.year,
            'month': self.month,
            'category': self.category,
            'description': self.description,
            'amount': float(self.amount or 0),
            'is_paid': self.is_paid,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
        }

    def __repr__(self):
        return f'<BranchExpense {self.branch_name} {self.year}-{self.month:02d} {self.category} ${self.amount}>'

# Hook simple para asegurar description en insert/update
from sqlalchemy import event

@event.listens_for(BranchExpense, 'before_insert')
@event.listens_for(BranchExpense, 'before_update')
def _before_save(mapper, connection, target: BranchExpense):
    target.ensure_fixed_desc()
