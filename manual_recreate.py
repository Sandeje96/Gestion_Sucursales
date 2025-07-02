# manual_recreate.py
"""
Script manual para recrear tabla en Railway.
"""

import os
import psycopg2
from urllib.parse import urlparse

def manual_recreate():
    """
    Recrear tabla manualmente usando psycopg2.
    """
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ No se encontró DATABASE_URL")
        return
    
    # Arreglar URL si viene con postgres:// en lugar de postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    parsed = urlparse(database_url)
    
    try:
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:]
        )
        
        cursor = conn.cursor()
        print("🔗 Conectado a PostgreSQL")
        
        # Eliminar tablas existentes
        print("🗑️  Eliminando tablas existentes...")
        cursor.execute("DROP TABLE IF EXISTS cash_trays CASCADE")
        cursor.execute("DROP TABLE IF EXISTS daily_records CASCADE")
        
        # Crear tabla daily_records con estructura completa
        print("🔨 Creando tabla daily_records...")
        cursor.execute("""
            CREATE TABLE daily_records (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                branch_name VARCHAR(100) NOT NULL,
                record_date DATE NOT NULL,
                total_sales NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                cash_sales NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                mercadopago_sales NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                debit_sales NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                credit_sales NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                total_expenses NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                verified_by INTEGER REFERENCES users(id),
                verified_at TIMESTAMP,
                is_withdrawn BOOLEAN NOT NULL DEFAULT FALSE,
                withdrawn_at TIMESTAMP,
                withdrawn_by INTEGER REFERENCES users(id),
                UNIQUE(branch_name, record_date)
            )
        """)
        
        # Crear índices
        cursor.execute("CREATE INDEX idx_daily_records_branch_date ON daily_records(branch_name, record_date)")
        cursor.execute("CREATE INDEX idx_daily_records_user_date ON daily_records(user_id, record_date)")
        
        # Crear tabla cash_trays
        print("🔨 Creando tabla cash_trays...")
        cursor.execute("""
            CREATE TABLE cash_trays (
                id SERIAL PRIMARY KEY,
                branch_name VARCHAR(100) NOT NULL UNIQUE,
                accumulated_cash NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                accumulated_mercadopago NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                accumulated_debit NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                accumulated_credit NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("✅ Tablas recreadas exitosamente")
        
        # Verificar estructura
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'daily_records' 
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print("\n📋 Estructura de daily_records:")
        for col in columns:
            print(f"   • {col[0]}: {col[1]} {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    manual_recreate()