# migration.py - Crear este archivo en la raíz del proyecto

"""
Script para migrar la base de datos y agregar el sistema de bandejas.
Ejecutar: python migration.py
"""

import os
import sys
from sqlalchemy import text

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def migrate_database():
    """Migrar la base de datos para agregar las nuevas funcionalidades."""
    
    print("🔄 Iniciando migración de base de datos...")
    
    app = create_app('development')
    
    with app.app_context():
        try:
            # 1. Agregar nuevas columnas a daily_records
            print("📋 Agregando campos de retiro a daily_records...")
            
            # Verificar si las columnas ya existen
            result = db.session.execute(text("PRAGMA table_info(daily_records)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'is_withdrawn' not in columns:
                db.session.execute(text("ALTER TABLE daily_records ADD COLUMN is_withdrawn BOOLEAN DEFAULT 0"))
                print("   ✅ Columna is_withdrawn agregada")
            else:
                print("   ⚠️  Columna is_withdrawn ya existe")
                
            if 'withdrawn_at' not in columns:
                db.session.execute(text("ALTER TABLE daily_records ADD COLUMN withdrawn_at DATETIME"))
                print("   ✅ Columna withdrawn_at agregada")
            else:
                print("   ⚠️  Columna withdrawn_at ya existe")
                
            if 'withdrawn_by' not in columns:
                db.session.execute(text("ALTER TABLE daily_records ADD COLUMN withdrawn_by INTEGER"))
                print("   ✅ Columna withdrawn_by agregada")
            else:
                print("   ⚠️  Columna withdrawn_by ya existe")
            
            # 2. Crear tabla cash_trays
            print("💰 Creando tabla de bandejas...")
            db.create_all()
            print("   ✅ Tabla cash_trays creada")
            
            # 3. Poblar las bandejas con datos existentes
            print("📊 Calculando bandejas desde registros existentes...")
            
            from app.models.daily_record import DailyRecord
            from app.models.cash_tray import CashTray
            
            # Limpiar bandejas existentes
            CashTray.query.delete()
            
            # Obtener todas las sucursales que tienen registros
            branches = db.session.query(DailyRecord.branch_name).distinct().all()
            
            for (branch_name,) in branches:
                print(f"   📍 Procesando {branch_name}...")
                
                # Crear bandeja para la sucursal
                tray = CashTray(branch_name=branch_name)
                
                # Sumar todos los registros NO retirados de esa sucursal
                records = DailyRecord.query.filter_by(
                    branch_name=branch_name,
                    is_withdrawn=False
                ).all()
                
                total_cash = sum(float(r.cash_sales or 0) for r in records)
                total_mercadopago = sum(float(r.mercadopago_sales or 0) for r in records)
                total_debit = sum(float(r.debit_sales or 0) for r in records)
                total_credit = sum(float(r.credit_sales or 0) for r in records)
                
                tray.accumulated_cash = total_cash
                tray.accumulated_mercadopago = total_mercadopago
                tray.accumulated_debit = total_debit
                tray.accumulated_credit = total_credit
                
                db.session.add(tray)
                
                print(f"      💵 Total acumulado: ${total_cash + total_mercadopago + total_debit + total_credit:,.2f}")
            
            # Confirmar todos los cambios
            db.session.commit()
            print("✅ Migración completada exitosamente")
            
            # Mostrar resumen
            print("\n" + "="*50)
            print("📊 RESUMEN DE BANDEJAS CREADAS:")
            print("="*50)
            
            trays = CashTray.query.all()
            for tray in trays:
                total = tray.get_total_accumulated()
                print(f"🏪 {tray.branch_name}: ${total:,.2f}")
            
            total_general = sum(tray.get_total_accumulated() for tray in trays)
            print(f"\n💰 TOTAL GENERAL: ${total_general:,.2f}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error durante la migración: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = migrate_database()
    if success:
        print("\n🎉 ¡Migración completada! Ya puedes usar el sistema de bandejas.")
    else:
        print("\n💥 La migración falló. Revisa los errores arriba.")