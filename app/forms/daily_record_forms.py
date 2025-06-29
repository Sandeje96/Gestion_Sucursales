# app/forms/daily_record_forms.py
"""
Formularios WTForms para el manejo de registros diarios de ventas y gastos.

Este módulo contiene:
- DailyRecordForm: Para crear y editar registros diarios
- FilterForm: Para filtrar registros por fecha y sucursal
"""

from flask_wtf import FlaskForm
from wtforms import DecimalField, DateField, TextAreaField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from wtforms.widgets import TextArea
from datetime import date, datetime
from decimal import Decimal


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
    
    # Ventas por método de pago
    cash_sales = DecimalField(
        'Ventas en Efectivo ($)',
        validators=[
            DataRequired(message='Las ventas en efectivo son obligatorias.'),
            NumberRange(min=0, message='Las ventas no pueden ser negativas.')
        ],
        default=Decimal('0.00'),
        places=2,
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    mercadopago_sales = DecimalField(
        'Ventas MercadoPago ($)',
        validators=[
            DataRequired(message='Las ventas por MercadoPago son obligatorias.'),
            NumberRange(min=0, message='Las ventas no pueden ser negativas.')
        ],
        default=Decimal('0.00'),
        places=2,
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    debit_sales = DecimalField(
        'Ventas con Débito ($)',
        validators=[
            DataRequired(message='Las ventas con débito son obligatorias.'),
            NumberRange(min=0, message='Las ventas no pueden ser negativas.')
        ],
        default=Decimal('0.00'),
        places=2,
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    credit_sales = DecimalField(
        'Ventas con Crédito ($)',
        validators=[
            DataRequired(message='Las ventas con crédito son obligatorias.'),
            NumberRange(min=0, message='Las ventas no pueden ser negativas.')
        ],
        default=Decimal('0.00'),
        places=2,
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    # Gastos del día
    total_expenses = DecimalField(
        'Gastos Totales del Día ($)',
        validators=[
            DataRequired(message='Los gastos totales son obligatorios.'),
            NumberRange(min=0, message='Los gastos no pueden ser negativos.')
        ],
        default=Decimal('0.00'),
        places=2,
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
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
        
        # Calcular y validar el total de ventas
        total_sales = (
            (self.cash_sales.data or 0) +
            (self.mercadopago_sales.data or 0) +
            (self.debit_sales.data or 0) +
            (self.credit_sales.data or 0)
        )
        
        self.total_sales.data = total_sales
        
        # Validar que al menos haya alguna venta o gasto
        if total_sales == 0 and (self.total_expenses.data or 0) == 0:
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