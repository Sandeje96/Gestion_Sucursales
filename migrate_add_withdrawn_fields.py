# migrate_add_withdrawn_fields.py
"""
Script de migración para agregar campos de retiro a daily_records.
Ejecutar una sola vez en producción para agregar las nuevas columnas.
"""

import os
import sys
from sqlalchemy import text

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db


def migrate_add_withdrawn_fields():
    """
    Agregar las nuevas columnas relacionadas con retiros a daily_records.
    """
    app = create_app('production')  # Usar configuración de producción
    
    with app.app_context():
        try:
            print("🔄 Iniciando migración: Agregando campos de retiro...")
            
            # Verificar si las columnas ya existen
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'daily_records' 
                AND column_name IN ('is_withdrawn', 'withdrawn_at', 'withdrawn_by')
            """)
            
            existing_columns = db.session.execute(check_query).fetchall()
            existing_column_names = [row[0] for row in existing_columns]
            
            print(f"📋 Columnas existentes: {existing_column_names}")
            
            # Agregar is_withdrawn si no existe
            if 'is_withdrawn' not in existing_column_names:
                print("➕ Agregando columna is_withdrawn...")
                db.session.execute(text("""
                    ALTER TABLE daily_records 
                    ADD COLUMN is_withdrawn BOOLEAN NOT NULL DEFAULT FALSE
                """))
                print("✅ Columna is_withdrawn agregada")
            else:
                print("⚠️  Columna is_withdrawn ya existe")
            
            # Agregar withdrawn_at si no existe
            if 'withdrawn_at' not in existing_column_names:
                print("➕ Agregando columna withdrawn_at...")
                db.session.execute(text("""
                    ALTER TABLE daily_records 
                    ADD COLUMN withdrawn_at TIMESTAMP
                """))
                print("✅ Columna withdrawn_at agregada")
            else:
                print("⚠️  Columna withdrawn_at ya existe")
            
            # Agregar withdrawn_by si no existe
            if 'withdrawn_by' not in existing_column_names:
                print("➕ Agregando columna withdrawn_by...")
                db.session.execute(text("""
                    ALTER TABLE daily_records 
                    ADD COLUMN withdrawn_by INTEGER REFERENCES users(id)
                """))
                print("✅ Columna withdrawn_by agregada")
            else:
                print("⚠️  Columna withdrawn_by ya existe")
            
            # Confirmar cambios
            db.session.commit()
            print("💾 Migración completada exitosamente")
            
            # Verificar que las columnas fueron agregadas
            final_check = db.session.execute(check_query).fetchall()
            final_columns = [row[0] for row in final_check]
            print(f"✅ Columnas finales: {final_columns}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error en la migración: {str(e)}")
            raise
        finally:
            db.session.close()


if __name__ == '__main__':
    try:
        migrate_add_withdrawn_fields()
        print("\n🎉 Migración completada. El sistema debería funcionar correctamente ahora.")
    except Exception as e:
        print(f"\n❌ Error ejecutando migración: {str(e)}")
        sys.exit(1)