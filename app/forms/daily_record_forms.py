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
    MEJORADO: Manejo más robusto de diferentes formatos.
    
    Formatos soportados:
    - "1.234,56" -> 1234.56
    - "1234,56" -> 1234.56
    - "1234.56" -> 1234.56
    - "1,234.56" -> 1234.56 (formato US)
    - "0,00" -> 0.0
    - "" -> 0.0
    - None -> 0.0
    """
    if value is None or value == "":
        return 0.0
    
    try:
        # Convertir a string y limpiar espacios
        value_str = str(value).strip()
        
        # Si está vacío después de limpiar
        if not value_str:
            return 0.0
        
        # Remover símbolos de moneda y espacios
        value_str = value_str.replace('$', '').replace(' ', '')
        
        # Si contiene tanto punto como coma, determinar cuál es el separador decimal
        if '.' in value_str and ',' in value_str:
            # Si el punto está después de la coma, es formato argentino: 1.234,56
            if value_str.rindex('.') < value_str.rindex(','):
                value_str = value_str.replace('.', '').replace(',', '.')
            # Si la coma está después del punto, es formato US: 1,234.56
            else:
                value_str = value_str.replace(',', '')
        
        # Si solo tiene coma, es separador decimal argentino
        elif ',' in value_str and '.' not in value_str:
            value_str = value_str.replace(',', '.')
        
        # Si solo tiene punto, ya está en formato correcto
        # (o es separador de miles, pero sin coma asumimos decimal)
        
        # Convertir a float
        result = float(value_str)
        
        # Validar que sea un número positivo o cero
        if result < 0:
            raise ValidationError("El valor no puede ser negativo.")
        
        return result
        
    except ValueError as e:
        print(f"Error convirtiendo '{value}' a decimal: {e}")
        raise ValidationError(f"Formato de moneda inválido: '{value}'. Use formato como 1.234,56 o 1234,56")
    except Exception as e:
        print(f"Error inesperado convirtiendo '{value}': {e}")
        raise ValidationError("Formato de moneda inválido.")


# Agregar este método mejorado a la clase DailyRecordForm
def validate(self, extra_validators=None):
    """
    Validación personalizada del formulario.
    MEJORADO: Mejor manejo de errores y debug.
    """
    if not super().validate(extra_validators):
        return False

    validation_errors = []
    
    # Parsear los valores de los campos monetarios
    try:
        self.cash_sales_float = currency_to_decimal(self.cash_sales.data)
        print(f"✅ cash_sales convertido: '{self.cash_sales.data}' -> {self.cash_sales_float}")
    except ValidationError as e:
        self.cash_sales.errors.append(str(e))
        validation_errors.append(f"Ventas en efectivo: {str(e)}")
    
    try:
        self.mercadopago_sales_float = currency_to_decimal(self.mercadopago_sales.data)
        print(f"✅ mercadopago_sales convertido: '{self.mercadopago_sales.data}' -> {self.mercadopago_sales_float}")
    except ValidationError as e:
        self.mercadopago_sales.errors.append(str(e))
        validation_errors.append(f"Ventas MercadoPago: {str(e)}")
    
    try:
        self.debit_sales_float = currency_to_decimal(self.debit_sales.data)
        print(f"✅ debit_sales convertido: '{self.debit_sales.data}' -> {self.debit_sales_float}")
    except ValidationError as e:
        self.debit_sales.errors.append(str(e))
        validation_errors.append(f"Ventas con débito: {str(e)}")
    
    try:
        self.credit_sales_float = currency_to_decimal(self.credit_sales.data)
        print(f"✅ credit_sales convertido: '{self.credit_sales.data}' -> {self.credit_sales_float}")
    except ValidationError as e:
        self.credit_sales.errors.append(str(e))
        validation_errors.append(f"Ventas con crédito: {str(e)}")
    
    try:
        self.total_expenses_float = currency_to_decimal(self.total_expenses.data)
        print(f"✅ total_expenses convertido: '{self.total_expenses.data}' -> {self.total_expenses_float}")
    except ValidationError as e:
        self.total_expenses.errors.append(str(e))
        validation_errors.append(f"Gastos totales: {str(e)}")
    
    # Si hubo errores de conversión, mostrar resumen
    if validation_errors:
        print(f"❌ Errores de validación:")
        for error in validation_errors:
            print(f"   - {error}")
        return False
    
    # Validación adicional: verificar que al menos uno de los valores sea mayor que 0
    total_sales = (
        self.cash_sales_float + 
        self.mercadopago_sales_float + 
        self.debit_sales_float + 
        self.credit_sales_float
    )
    
    if total_sales == 0 and self.total_expenses_float == 0:
        self.cash_sales.errors.append("Debe ingresar al menos un valor mayor que cero.")
        return False
    
    print(f"✅ Validación exitosa. Total ventas: {total_sales}, Gastos: {self.total_expenses_float}")
    return True

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

    def __init__(self, *args, **kwargs):
        super(DailyRecordForm, self).__init__(*args, **kwargs)
        import pytz
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        today_arg = datetime.now(tz_arg).date()
        self.record_date.render_kw = {
            'class': 'form-control',
            'max': today_arg.isoformat()
        }
    
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
    ACTUALIZADO: Carga sucursales dinámicamente desde la BD.
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
        choices=[],  # Se carga dinámicamente
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
    
    def __init__(self, *args, **kwargs):
        """
        Constructor que carga las sucursales dinámicamente desde la BD.
        """
        super(FilterForm, self).__init__(*args, **kwargs)
        
        # Cargar sucursales dinámicamente
        self.load_branch_choices()
    
    def load_branch_choices(self):
        """
        Cargar las opciones de sucursales desde la base de datos.
        """
        try:
            from app.models.daily_record import DailyRecord
            from app import db
            
            # Función de normalización (copiar aquí o importar)
            def normalize_branch_name(branch_name):
                if not branch_name:
                    return branch_name
                
                normalized = str(branch_name).strip()
                
                branch_mapping = {
                    'uruguay': 'Uruguay',
                    'URUGUAY': 'Uruguay',
                    ' uruguay ': 'Uruguay',
                    'uruguay ': 'Uruguay',
                    ' uruguay': 'Uruguay',
                    'villa cabello': 'Villa Cabello',
                    'VILLA CABELLO': 'Villa Cabello',
                    'Villa cabello': 'Villa Cabello',
                    'villacabello': 'Villa Cabello',
                    'villa_cabello': 'Villa Cabello',
                    'tacuari': 'Tacuari',
                    'TACUARI': 'Tacuari',
                    'tacuarí': 'Tacuari',
                    'Tacuarí': 'Tacuari',
                    'candelaria': 'Candelaria',
                    'CANDELARIA': 'Candelaria',
                    'itaembe mini': 'Itaembe Mini',
                    'ITAEMBE MINI': 'Itaembe Mini',
                    'Itaembe mini': 'Itaembe Mini',
                    'itaembe_mini': 'Itaembe Mini',
                    'itaembemini': 'Itaembe Mini'
                }
                
                normalized_lower = normalized.lower()
                for variation, standard in branch_mapping.items():
                    if normalized_lower == variation.lower():
                        return standard
                
                return normalized.title()
            
            # Obtener sucursales únicas y normalizarlas
            raw_branches = db.session.query(DailyRecord.branch_name).distinct().all()
            
            # Crear set para evitar duplicados
            normalized_branches = set()
            for (branch_name,) in raw_branches:
                if branch_name:
                    normalized = normalize_branch_name(branch_name)
                    normalized_branches.add(normalized)
            
            # Crear lista de opciones ordenada
            branch_choices = [('', 'Todas las sucursales')]
            for branch in sorted(list(normalized_branches)):
                branch_choices.append((branch, branch))
            
            self.branch_filter.choices = branch_choices
            
            print(f"🏢 [FORM] Sucursales cargadas: {[choice[1] for choice in branch_choices[1:]]}")
            
        except Exception as e:
            print(f"❌ [FORM] Error cargando sucursales: {e}")
            # Fallback a opciones estáticas si hay error
            self.branch_filter.choices = [
                ('', 'Todas las sucursales'),
                ('Uruguay', 'Uruguay'),
                ('Villa Cabello', 'Villa Cabello'),
                ('Tacuari', 'Tacuari'),
                ('Candelaria', 'Candelaria'),
                ('Itaembe Mini', 'Itaembe Mini')
            ]
    
    def validate(self, extra_validators=None):
        """
        Validación personalizada para el rango de fechas.
        """
        result = super(FilterForm, self).validate(extra_validators)
        
        # Validar que la fecha de inicio no sea posterior a la fecha de fin
        if self.start_date.data and self.end_date.data:
            if self.start_date.data > self.end_date.data:
                self.end_date.errors.append(
                    'La fecha final debe ser posterior o igual a la fecha inicial.'
                )
                result = False
        
        return result

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