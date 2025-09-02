# railway_fix_cash_trays.py
"""
Script específico para agregar la columna accumulated_cash_expenses en Railway PostgreSQL.
Ejecutar con: railway run python railway_fix_cash_trays.py
"""

import os
import psycopg2
from urllib.parse import urlparse

def fix_cash_trays_table():
    """
    Agregar la columna accumulated_cash_expenses a la tabla cash_trays en Railway.
    """
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ No se encontró DATABASE_URL")
        return False
    
    # Arreglar URL si viene con postgres:// en lugar de postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("🔗 Conectado a PostgreSQL en Railway")
        
        # Verificar si la columna ya existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'cash_trays' 
            AND column_name = 'accumulated_cash_expenses'
        """)
        
        if cursor.fetchone():
            print("ℹ️ La columna accumulated_cash_expenses ya existe")
        else:
            print("➕ Agregando columna accumulated_cash_expenses...")
            
            # Agregar la columna
            cursor.execute("""
                ALTER TABLE cash_trays 
                ADD COLUMN accumulated_cash_expenses NUMERIC(12,2) NOT NULL DEFAULT 0.00
            """)
            
            print("✅ Columna agregada exitosamente")
        
        # Verificar estructura de la tabla
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'cash_trays' 
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print(f"\n📋 Estructura actual de cash_trays:")
        for col in columns:
            nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col[3]}" if col[3] else ""
            print(f"   • {col[0]}: {col[1]} {nullable}{default}")
        
        # Actualizar bandejas existentes para incluir gastos
        print("\n🔄 Recalculando gastos acumulados...")
        
        # Obtener todas las sucursales de cash_trays
        cursor.execute("SELECT DISTINCT branch_name FROM cash_trays")
        branches = cursor.fetchall()
        
        for (branch_name,) in branches:
            print(f"   🔄 Procesando {branch_name}...")
            
            # Calcular gastos acumulados de registros NO retirados
            cursor.execute("""
                SELECT COALESCE(SUM(total_expenses), 0)
                FROM daily_records 
                WHERE branch_name = %s 
                AND is_withdrawn = FALSE
            """, (branch_name,))
            
            total_expenses = cursor.fetchone()[0] or 0
            
            # Actualizar la bandeja
            cursor.execute("""
                UPDATE cash_trays 
                SET accumulated_cash_expenses = %s,
                    last_updated = NOW()
                WHERE branch_name = %s
            """, (total_expenses, branch_name))
            
            print(f"      💰 Gastos acumulados: ${float(total_expenses):,.2f}")
        
        # Confirmar todos los cambios
        conn.commit()
        print("✅ Migración completada exitosamente")
        
        # Mostrar resumen final
        cursor.execute("""
            SELECT 
                branch_name,
                accumulated_cash,
                accumulated_cash_expenses,
                (accumulated_cash - accumulated_cash_expenses) as available_cash,
                (accumulated_cash + accumulated_mercadopago + accumulated_debit + accumulated_credit) as total_accumulated
            FROM cash_trays
            ORDER BY branch_name
        """)
        
        trays = cursor.fetchall()
        print(f"\n📊 RESUMEN DE BANDEJAS:")
        print("="*80)
        
        for tray in trays:
            branch, cash, expenses, available, total = tray
            print(f"🏪 {branch}:")
            print(f"   Ventas efectivo: ${float(cash):,.2f}")
            print(f"   Gastos efectivo: ${float(expenses):,.2f}")
            print(f"   Efectivo disponible: ${float(available):,.2f}")
            print(f"   Total bandeja: ${float(total):,.2f}")
            print("-" * 40)
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fix_cash_trays_table()
    if success:
        print("\n🎉 ¡Tabla corregida! El sistema ahora debería funcionar correctamente.")
    else:
        print("\n❌ Hubo un error. Revisa los logs arriba.")
