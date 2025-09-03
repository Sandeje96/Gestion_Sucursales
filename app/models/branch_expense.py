# app/models/branch_expense.py
from app import db
import datetime
from sqlalchemy.orm import validates
from sqlalchemy import event

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
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now
    )

    __table_args__ = (
        # Para únicas: una fila por (sucursal, año, mes, categoría, descripción)
        # Para categorías fijas usamos description='-' (ver ensure_fixed_desc) así queda 1 solo registro por mes.
        db.UniqueConstraint(
            'branch_name', 'year', 'month', 'category', 'description',
            name='uq_branch_month_cat_desc'
        ),
        db.CheckConstraint('month BETWEEN 1 AND 12', name='check_month_valid'),
        db.CheckConstraint('amount >= 0', name='check_amount_nonnegative'),
    )

    @validates('category', 'description')
    def _normalize(self, key, value):
        if key == 'category':
            if value not in CATEGORIES:
                raise ValueError('Categoría inválida')
        # La normalización de description para categorías fijas se hace en ensure_fixed_desc
        return value

    @validates('month')
    def _check_month(self, key, value):
        if value is None or int(value) < 1 or int(value) > 12:
            raise ValueError('Mes inválido')
        return int(value)

    def ensure_fixed_desc(self):
        """
        - Para categorías fijas (!= OTROS): si no hay descripción, forzamos '-'
        - Para OTROS: la descripción es obligatoria y no puede ser vacía
        """
        if self.category != 'OTROS' and not self.description:
            self.description = '-'
        if self.category == 'OTROS' and (self.description is None or not self.description.strip()):
            raise ValueError('Descripción requerida para OTROS')

    # -----------------------------
    # Reglas de pago / gasto del día
    # -----------------------------

    def mark_paid_for_today(self, user_id):
        """
        Marcar como pagado y registrar el gasto como GASTO DEL DÍA (hoy) de la sucursal,
        descontándolo del efectivo (bandeja) de esa sucursal.
        """
        from datetime import date
        from app.models.user import User
        from app.models.daily_record import DailyRecord
        from app.models.cash_tray import CashTray

        self.is_paid = True
        self.paid_at = datetime.datetime.now()
        self.paid_by = user_id

        amount_float = float(self.amount or 0)

        # Solo crear registro diario y descontar efectivo si lo paga un usuario de sucursal de la misma sucursal
        if user_id:
            user = User.query.get(user_id)
            if user and getattr(user, 'is_branch_user', lambda: False)() and user.branch_name == self.branch_name:
                today = date.today()

                # Buscar/crear el registro diario por (sucursal, fecha) — NO filtrar por user_id
                daily_record = DailyRecord.get_by_branch_and_date(self.branch_name, today)

                if daily_record:
                    current_expense = float(daily_record.total_expenses or 0)
                    daily_record.total_expenses = current_expense + amount_float
                else:
                    daily_record = DailyRecord(
                        branch_name=self.branch_name,
                        record_date=today,
                        user_id=user_id,  # quien lo crea
                        cash_sales=0,
                        mercadopago_sales=0,
                        debit_sales=0,
                        credit_sales=0,
                        total_expenses=amount_float
                    )
                    db.session.add(daily_record)

                # Recalcular totales del registro diario (método existente)
                daily_record.calculate_total_sales()

                # Impactar la bandeja de efectivo inmediatamente (gasto en EFECTIVO)
                tray = CashTray.get_or_create_for_branch(self.branch_name)
                tray.add_expense_amount(amount_float)

        # Persistir en la transacción actual (el commit lo hace la vista/controlador)
        db.session.flush()

    # Alias si alguna parte del código llama a mark_paid
    def mark_paid(self, user_id):
        return self.mark_paid_for_today(user_id)

    def unmark_paid(self):
        """
        Desmarcar como pagado y revertir el descuento de efectivo (si correspondía a usuario de sucursal).
        NOTA: No deducimos automáticamente del DailyRecord aquí porque puede requerir lógica de auditoría
        (quién y cuándo eliminó). La bandeja sí se revierte para mantener disponibilidad correcta.
        """
        from app.models.user import User
        from app.models.cash_tray import CashTray

        # Si lo había pagado un usuario de sucursal de la misma sucursal, revertimos el descuento en bandeja
        if self.paid_by:
            user = User.query.get(self.paid_by)
            if user and getattr(user, 'is_branch_user', lambda: False)() and user.branch_name == self.branch_name:
                tray = CashTray.get_or_create_for_branch(self.branch_name)
                tray.subtract_expense_amount(float(self.amount or 0))

        self.is_paid = False
        self.paid_at = None
        self.paid_by = None
        db.session.flush()

    # -----------------------------
    # Utilidades / permisos
    # -----------------------------

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
@event.listens_for(BranchExpense, 'before_insert')
@event.listens_for(BranchExpense, 'before_update')
def _before_save(mapper, connection, target: BranchExpense):
    target.ensure_fixed_desc()