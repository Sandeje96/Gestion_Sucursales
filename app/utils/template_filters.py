# Agregar a tu app/__init__.py o crear un archivo separado para filtros

import locale
from flask import current_app

def format_currency_argentino(amount):
    """
    Formatear cantidad como moneda argentina.
    Ejemplo: 1234567.89 -> $1.234.567,89
    """
    try:
        # Convertir a float si es necesario
        if isinstance(amount, str):
            amount = float(amount)
        
        # Formatear el número
        # Separar parte entera y decimal
        formatted = "{:,.2f}".format(amount)
        
        # Cambiar separadores: . por , y , por .
        # Primero cambiar , por un marcador temporal
        formatted = formatted.replace(',', 'TEMP')
        # Cambiar . por ,
        formatted = formatted.replace('.', ',')
        # Cambiar marcador temporal por .
        formatted = formatted.replace('TEMP', '.')
        
        return f"${formatted}"
    except (ValueError, TypeError):
        return "$0,00"

def format_number_argentino(amount, decimals=2):
    """
    Formatear número con separadores argentinos sin símbolo de moneda.
    """
    try:
        if isinstance(amount, str):
            amount = float(amount)
        
        format_str = f"{{:,.{decimals}f}}"
        formatted = format_str.format(amount)
        
        # Cambiar separadores
        formatted = formatted.replace(',', 'TEMP')
        formatted = formatted.replace('.', ',')
        formatted = formatted.replace('TEMP', '.')
        
        return formatted
    except (ValueError, TypeError):
        return "0,00"

def format_percentage_argentino(value, decimals=1):
    """
    Formatear porcentaje en formato argentino.
    """
    try:
        if isinstance(value, str):
            value = float(value)
        
        format_str = f"{{:.{decimals}f}}"
        formatted = format_str.format(value)
        
        # Cambiar punto por coma
        formatted = formatted.replace('.', ',')
        
        return f"{formatted}%"
    except (ValueError, TypeError):
        return "0,0%"

# Función para registrar los filtros en la app
def register_template_filters(app):
    """Registrar filtros personalizados en la aplicación Flask."""
    
    @app.template_filter('currency_ar')
    def currency_ar_filter(amount):
        return format_currency_argentino(amount)
    
    @app.template_filter('number_ar')
    def number_ar_filter(amount, decimals=2):
        return format_number_argentino(amount, decimals)
    
    @app.template_filter('percentage_ar')
    def percentage_ar_filter(value, decimals=1):
        return format_percentage_argentino(value, decimals)

# En tu app/__init__.py, agregar después de crear la app:
# register_template_filters(app)