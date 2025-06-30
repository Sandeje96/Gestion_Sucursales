# check_database.py - Guardar en la raíz del proyecto y ejecutar
import os
import sys
from datetime import date

# Configurar path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Flask
os.environ['FLASK_ENV'] = 'development'

from app import create_app, db
from app.models.user import User
from app.models.daily_record import DailyRecord

def check_data():
    app = create_app()
    
    with app.app_context():
        print("🔍 VERIFICANDO DATOS EN LA BASE DE DATOS")
        print("=" * 50)
        
        # Verificar usuarios
        users = User.query.all()
        print(f"\n👥 USUARIOS: {len(users)}")
        for user in users:
            print(f"   • {user.username} - {user.branch_name} ({user.role})")
        
        # Verificar registros
        records = DailyRecord.query.all()
        print(f"\n📊 REGISTROS TOTALES: {len(records)}")
        
        # Registros de hoy
        today = date.today()
        today_records = DailyRecord.query.filter(
            DailyRecord.record_date == today
        ).all()
        
        print(f"\n📅 REGISTROS DE HOY ({today}): {len(today_records)}")
        
        if today_records:
            for record in today_records:
                print(f"   • {record.branch_name}: ${record.total_sales} ventas, ${record.total_expenses} gastos")
        else:
            print("❌ NO HAY REGISTROS PARA HOY")
            
        # Crear registros de prueba si no existen
        if len(today_records) == 0:
            create_test = input("\n¿Crear registros de prueba para HOY? (y/N): ")
            if create_test.lower() == 'y':
                create_test_data()

def create_test_data():
    """Crear datos de prueba para hoy"""
    
    app = create_app()
    with app.app_context():
        today = date.today()
        branches_data = [
            {'name': 'Uruguay', 'cash': 1500, 'mp': 1200, 'debit': 800, 'credit': 600, 'expenses': 400},
            {'name': 'Villa Cabello', 'cash': 1300, 'mp': 1000, 'debit': 700, 'credit': 500, 'expenses': 350},
            {'name': 'Tacuari', 'cash': 1100, 'mp': 900, 'debit': 600, 'credit': 400, 'expenses': 300},
            {'name': 'Candelaria', 'cash': 1000, 'mp': 800, 'debit': 500, 'credit': 300, 'expenses': 250},
            {'name': 'Itaembe Mini', 'cash': 900, 'mp': 700, 'debit': 400, 'credit': 200, 'expenses': 200}
        ]
        
        for branch_data in branches_data:
            # Buscar o crear usuario
            user = User.query.filter_by(branch_name=branch_data['name']).first()
            if not user:
                user = User(
                    username=branch_data['name'].lower().replace(' ', ''),
                    email=f"{branch_data['name'].lower().replace(' ', '')}@test.com",
                    branch_name=branch_data['name'],
                    role='branch_user'
                )
                user.set_password('test123')
                db.session.add(user)
                db.session.flush()
            
            # Verificar si ya existe registro para hoy
            existing = DailyRecord.query.filter_by(
                branch_name=branch_data['name'],
                record_date=today
            ).first()
            
            if not existing:
                record = DailyRecord(
                    user_id=user.id,
                    branch_name=branch_data['name'],
                    record_date=today,
                    cash_sales=branch_data['cash'],
                    mercadopago_sales=branch_data['mp'],
                    debit_sales=branch_data['debit'],
                    credit_sales=branch_data['credit'],
                    total_expenses=branch_data['expenses']
                )
                record.calculate_total_sales()
                db.session.add(record)
                print(f"✅ Creado registro para {branch_data['name']}")
        
        try:
            db.session.commit()
            print("✅ Datos de prueba creados exitosamente")
            check_data()  # Verificar otra vez
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")

if __name__ == '__main__':
    check_data()