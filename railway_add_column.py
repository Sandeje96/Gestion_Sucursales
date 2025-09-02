# railway_add_column.py
"""
Script para agregar la columna accumulated_cash_expenses en Railway usando SQLAlchemy.
Ejecutar con: railway run python railway_add_column.py
"""

import os
import sys
from sqlalchemy import text

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db


def add_cash_expenses_column():
    """
    Agregar la columna accumulated_cash_expenses a cash_trays en Railway.
    """
    # Usar configuración de producción para Railway
    app = create_app('production')
    
    with app.app_context():
        try:
            print("🔗 Conectando a Railway PostgreSQL...")
            
            # Verificar si la columna ya existe
            check_column = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cash_trays' 
                AND column_name = 'accumulated_cash_expenses'
            """)
            
            result = db.session.execute(check_column).fetchone()
            
            if result:
                print("ℹ️ La columna accumulated_cash_expenses ya existe")
            else:
                print("➕ Agregando columna accumulated_cash_expenses...")
                
                # Agregar la columna
                add_column_sql = text("""
                    ALTER TABLE cash_trays 
                    ADD COLUMN accumulated_cash_expenses NUMERIC(12,2) NOT NULL DEFAULT 0.00
                """)
                
                db.session.execute(add_column_sql)
                db.session.commit()
                print("✅ Columna agregada exitosamente")
            
            # Verificar estructura de la tabla
            verify_structure = text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'cash_trays' 
                ORDER BY ordinal_position
            """)
            
            columns = db.session.execute(verify_structure).fetchall()
            print(f"\n📋 Estructura actual de cash_trays:")
            for col in columns:
                nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                print(f"   • {col[0]}: {col[1]} {nullable}{default}")
            
            # Recalcular todas las bandejas para incluir los gastos
            print("\n🔄 Recalculando bandejas con gastos...")
            from app.models.cash_tray import CashTray
            from app.models.daily_record import DailyRecord
            
            # Obtener todas las sucursales
            branches_query = text("SELECT DISTINCT branch_name FROM cash_trays")
            branches = db.session.execute(branches_query).fetchall()
            
            for (branch_name,) in branches:
                print(f"   🔄 Procesando {branch_name}...")
                
                # Obtener bandeja
                tray = CashTray.query.filter_by(branch_name=branch_name).first()
                if not tray:
                    continue
                
                # Calcular gastos acumulados de registros NO retirados
                expenses_query = text("""
                    SELECT COALESCE(SUM(total_expenses), 0)
                    FROM daily_records 
                    WHERE branch_name = :branch_name 
                    AND is_withdrawn = FALSE
                """)
                
                result = db.session.execute(expenses_query, {"branch_name": branch_name}).fetchone()
                total_expenses = float(result[0]) if result[0] else 0.0
                
                # Actualizar la bandeja
                tray.accumulated_cash_expenses = total_expenses
                print(f"      💰 Gastos acumulados: ${total_expenses:,.2f}")
            
            db.session.commit()
            print("✅ Bandejas recalculadas exitosamente")
            
            # Mostrar resumen final
            trays = CashTray.query.all()
            print(f"\n📊 RESUMEN DE BANDEJAS:")
            print("="*80)
            
            for tray in trays:
                available_cash = tray.get_available_cash()
                total_accumulated = tray.get_total_accumulated()
                print(f"🏪 {tray.branch_name}:")
                print(f"   Ventas efectivo: ${tray.accumulated_cash:,.2f}")
                print(f"   Gastos efectivo: ${tray.accumulated_cash_expenses:,.2f}")
                print(f"   Efectivo disponible: ${available_cash:,.2f}")
                print(f"   Total bandeja: ${total_accumulated:,.2f}")
                print("-" * 40)
            
            print("\n✅ Migración completada exitosamente")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            db.session.close()


if __name__ == '__main__':
    success = add_cash_expenses_column()
    if success:
        print("\n🎉 ¡Tabla corregida! El sistema ahora debería funcionar correctamente.")
    else:
        print("\n❌ Hubo un error. Revisa los logs arriba.")