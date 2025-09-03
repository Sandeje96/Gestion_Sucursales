# app/forms/expense_forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SelectField
from wtforms.validators import DataRequired, NumberRange, Optional
from app.models.branch_expense import CATEGORIES, BranchExpense

class ExpenseForm(FlaskForm):
    branch_name = StringField('Sucursal', validators=[Optional()])  # admin la envía; sucursal se infiere
    year = IntegerField('Año', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    month = IntegerField('Mes', validators=[DataRequired(), NumberRange(min=1, max=12)])
    category = SelectField('Categoría', choices=[(c, c.title()) for c in CATEGORIES], validators=[DataRequired()])
    description = StringField('Descripción (solo OTROS)', validators=[Optional()])
    amount = DecimalField('Monto', places=2, rounding=None, validators=[DataRequired(), NumberRange(min=0)])

    def validate_for_user(self, user):
        # Permisos y reglas de negocio
        bname = (self.branch_name.data or '').strip() or getattr(user, 'branch_name', None)
        cat = self.category.data

        if not BranchExpense.can_edit_category(user, bname, cat):
            raise ValueError('No tenés permiso para editar esa categoría')

        if cat == 'SERENO' and (bname or '').strip().lower() != 'tacuari':
            raise ValueError('SERENO solo aplica a la sucursal Tacuari')

        if cat == 'OTROS' and not (self.description.data or '').strip():
            raise ValueError('Descripción es obligatoria para OTROS')