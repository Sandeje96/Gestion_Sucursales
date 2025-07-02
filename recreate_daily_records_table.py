# recreate_daily_records_table.py
"""
Script para recrear completamente la tabla daily_records con la nueva estructura.
Usar cuando la estructura de la tabla no coincide con el modelo.
"""

import os
import sys
from sqlalchemy import text

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db


def recreate_daily_records_table():
    """
    Eliminar y recrear la tabla daily_records con la estructura correcta.
    """
    app = create_app('production')  # Usar configuración de producción
    
    with app.app_context():
        try:
            print("🔄 Iniciando recreación de tabla daily_records...")
            
            # Paso 1: Verificar tablas existentes
            check_tables = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('daily_records', 'cash_trays')
            """)
            
            existing_tables = db.session.execute(check_tables).fetchall()
            table_names = [row[0] for row in existing_tables]
            print(f"📋 Tablas existentes: {table_names}")
            
            # Paso 2: Eliminar tabla cash_trays si existe (depende de daily_records)
            if 'cash_trays' in table_names:
                print("🗑️  Eliminando tabla cash_trays...")
                db.session.execute(text("DROP TABLE IF EXISTS cash_trays CASCADE"))
                print("✅ Tabla cash_trays eliminada")
            
            # Paso 3: Eliminar tabla daily_records si existe
            if 'daily_records' in table_names:
                print("🗑️  Eliminando tabla daily_records...")
                db.session.execute(text("DROP TABLE IF EXISTS daily_records CASCADE"))
                print("✅ Tabla daily_records eliminada")
            
            # Paso 4: Recrear las tablas usando SQLAlchemy
            print("🔨 Creando nuevas tablas con estructura actualizada...")
            
            # Esto creará todas las tablas que falten según los modelos actuales
            db.create_all()
            
            print("✅ Tablas recreadas exitosamente")
            
            # Paso 5: Verificar la nueva estructura
            verify_structure = text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'daily_records' 
                ORDER BY ordinal_position
            """)
            
            columns = db.session.execute(verify_structure).fetchall()
            print(f"\n📋 Nueva estructura de daily_records:")
            for col in columns:
                nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                print(f"   • {col[0]}: {col[1]} {nullable}")
            
            # Confirmar cambios
            db.session.commit()
            print("\n💾 Recreación completada exitosamente")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en la recreación: {str(e)}")
            raise
        finally:
            db.session.close()


if __name__ == '__main__':
    try:
        recreate_daily_records_table()
        print("\n🎉 Tabla recreada. El sistema debería funcionar correctamente ahora.")
    except Exception as e:
        print(f"\n❌ Error ejecutando recreación: {str(e)}")
        sys.exit(1)