"""
Formularios WTForms para el manejo de registros diarios de ventas y gastos.

Este módulo contiene:
- DailyRecordForm: Para crear y editar registros diarios
- FilterForm: Para filtrar registros por fecha y sucursal
"""

from flask_wtf import FlaskForm
from wtforms import StringField, DateField, TextAreaField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional, Length, ValidationError
from wtforms.widgets import TextArea
from datetime import date, datetime

def currency_to_decimal(value):
    """
    Convierte un string de moneda en formato argentino a float.
    Ej: "1.234,56" -> 1234.56
    """
    if value is None or value == "":
        return 0.0
    try:
        value = str(value)
        value = value.replace('.', '').replace(',', '.')
        return float(value)
    except Exception:
        raise ValidationError("Formato de moneda inválido.")

class DailyRecordForm(FlaskForm):
    """
    Formulario para crear o editar un registro diario de ventas y gastos.
    
    Campos:
    - record_date: Fecha del registro
    - cash_sales: Ventas en efectivo
    - mercadopago_sales: Ventas por MercadoPago
    - debit_sales: Ventas con tarjeta de débito
    - credit_sales: Ventas con tarjeta de crédito
    - total_expenses: Gastos totales del día
    - notes: Notas adicionales (opcional)
    """
    
    record_date = DateField(
        'Fecha del Registro',
        validators=[
            DataRequired(message='La fecha es obligatoria.')
        ],
        default=date.today,
        render_kw={
            'class': 'form-control',
            'max': date.today().isoformat()  # No permitir fechas futuras
        }
    )
    
    # Ventas por método de pago (CAMBIADO a StringField para permitir texto con formato argentino)
    cash_sales = StringField(
        'Ventas en Efectivo ($)',
        validators=[
            DataRequired(message='Las ventas en efectivo son obligatorias.')
        ],
        default="0,00",
        render_kw={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
            'min': '0'
        }
    )
    
    mercadopago_sales = StringField(
        'Ventas MercadoPago ($)',
        validators=[
            DataRequired(message='Las ventas por MercadoPago son obligatorias.')
        ],
        default="0,00",
        render_kw={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
            'min': '0'
        }
    )
    
    debit_sales = StringField(
        'Ventas con Débito ($)',
        validators=[
            DataRequired(message='Las ventas con débito son obligatorias.')
        ],
        default="0,00",
        render_kw={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
            'min': '0'
        }
    )
    
    credit_sales = StringField(
        'Ventas con Crédito ($)',
        validators=[
            DataRequired(message='Las ventas con crédito son obligatorias.')
        ],
        default="0,00",
        render_kw={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
            'min': '0'
        }
    )
    
    # Gastos del día
    total_expenses = StringField(
        'Gastos Totales del Día ($)',
        validators=[
            DataRequired(message='Los gastos totales son obligatorios.')
        ],
        default="0,00",
        render_kw={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
            'min': '0'
        }
    )
    
    # Notas adicionales
    notes = TextAreaField(
        'Notas Adicionales',
        validators=[
            Optional(),
            Length(max=500, message='Las notas no pueden exceder 500 caracteres.')
        ],
        render_kw={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Información adicional del día (opcional)'
        }
    )
    
    # Campo oculto para el total (se calcula automáticamente)
    total_sales = HiddenField('Total de Ventas')
    
    submit = SubmitField(
        'Guardar Registro',
        render_kw={
            'class': 'btn btn-primary w-100'
        }
    )
    
    def validate(self, extra_validators=None):
        """
        Validación personalizada del formulario.
        """
        if not super().validate(extra_validators):
            return False

        # Parsear los valores de los campos monetarios
        try:
            self.cash_sales_float = currency_to_decimal(self.cash_sales.data)
            self.mercadopago_sales_float = currency_to_decimal(self.mercadopago_sales.data)
            self.debit_sales_float = currency_to_decimal(self.debit_sales.data)
            self.credit_sales_float = currency_to_decimal(self.credit_sales.data)
            self.total_expenses_float = currency_to_decimal(self.total_expenses.data)
        except ValidationError as e:
            msg = str(e)
            if not self.cash_sales.data.replace('.', '').replace(',', '').isdigit():
                self.cash_sales.errors.append(msg)
            if not self.mercadopago_sales.data.replace('.', '').replace(',', '').isdigit():
                self.mercadopago_sales.errors.append(msg)
            if not self.debit_sales.data.replace('.', '').replace(',', '').isdigit():
                self.debit_sales.errors.append(msg)
            if not self.credit_sales.data.replace('.', '').replace(',', '').isdigit():
                self.credit_sales.errors.append(msg)
            if not self.total_expenses.data.replace('.', '').replace(',', '').isdigit():
                self.total_expenses.errors.append(msg)
            return False

        # Validar que los valores no sean negativos
        for field_name in [
            'cash_sales_float', 'mercadopago_sales_float',
            'debit_sales_float', 'credit_sales_float', 'total_expenses_float'
        ]:
            value = getattr(self, field_name)
            if value < 0:
                getattr(self, field_name.replace('_float', '')).errors.append(
                    'El valor no puede ser negativo.'
                )
                return False

        total_sales = (
            self.cash_sales_float +
            self.mercadopago_sales_float +
            self.debit_sales_float +
            self.credit_sales_float
        )
        self.total_sales.data = str(total_sales)

        # Validar que al menos haya alguna venta o gasto
        if total_sales == 0 and self.total_expenses_float == 0:
            self.cash_sales.errors.append(
                'Debe registrar al menos alguna venta o gasto.'
            )
            return False

        return True

class FilterForm(FlaskForm):
    """
    Formulario para filtrar registros por diferentes criterios.
    """
    start_date = DateField(
        'Fecha Desde',
        validators=[Optional()],
        render_kw={
            'class': 'form-control'
        }
    )
    end_date = DateField(
        'Fecha Hasta',
        validators=[Optional()],
        render_kw={
            'class': 'form-control'
        }
    )
    branch_filter = SelectField(
        'Sucursal',
        choices=[
            ('', 'Todas las sucursales'),
            ('Uruguay', 'Uruguay'),
            ('Villa Cabello', 'Villa Cabello'),
            ('Tacuari', 'Tacuari'),
            ('Candelaria', 'Candelaria'),
            ('Itaembe Mini', 'Itaembe Mini')
        ],
        validators=[Optional()],
        render_kw={
            'class': 'form-select'
        }
    )
    submit = SubmitField(
        'Filtrar',
        render_kw={
            'class': 'btn btn-outline-primary'
        }
    )
    def validate(self, extra_validators=None):
        """
        Validación personalizada para el rango de fechas.
        """
        if not super().validate(extra_validators):
            return False
        if self.start_date.data and self.end_date.data:
            if self.start_date.data > self.end_date.data:
                self.end_date.errors.append(
                    'La fecha final debe ser posterior a la fecha inicial.'
                )
                return False
        return True

class QuickStatsForm(FlaskForm):
    """
    Formulario rápido para obtener estadísticas por período.
    """
    period = SelectField(
        'Período',
        choices=[
            ('today', 'Hoy'),
            ('yesterday', 'Ayer'),
            ('this_week', 'Esta Semana'),
            ('last_week', 'Semana Pasada'),
            ('this_month', 'Este Mes'),
            ('last_month', 'Mes Pasado'),
            ('this_year', 'Este Año'),
            ('custom', 'Período Personalizado')
        ],
        default='today',
        validators=[DataRequired()],
        render_kw={
            'class': 'form-select'
        }
    )
    custom_start = DateField(
        'Fecha Inicio (Personalizado)',
        validators=[Optional()],
        render_kw={
            'class': 'form-control'
        }
    )
    custom_end = DateField(
        'Fecha Fin (Personalizado)',
        validators=[Optional()],
        render_kw={
            'class': 'form-control'
        }
    )
    submit = SubmitField(
        'Ver Estadísticas',
        render_kw={
            'class': 'btn btn-info'
        }
    )

class BulkActionForm(FlaskForm):
    """
    Formulario para acciones en lote (solo para administradores).
    """
    action = SelectField(
        'Acción',
        choices=[
            ('verify', 'Verificar Seleccionados'),
            ('unverify', 'Desverificar Seleccionados'),
            ('delete', 'Eliminar Seleccionados')
        ],
        validators=[DataRequired()],
        render_kw={
            'class': 'form-select'
        }
    )
    selected_records = HiddenField('Registros Seleccionados')
    submit = SubmitField(
        'Ejecutar Acción',
        render_kw={
            'class': 'btn btn-warning'
        }
    )