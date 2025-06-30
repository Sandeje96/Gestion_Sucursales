# debug_data.py - Ejecutar desde la raíz del proyecto para verificar los datos

import os
import sys
from datetime import date, datetime

# Agregar el path del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.daily_record import DailyRecord

def debug_dashboard_data():
    """Verificar qué datos hay en la base de datos para el dashboard."""
    
    app = create_app('development')
    
    with app.app_context():
        print("🔍 DEBUGGING - Dashboard Data")
        print("=" * 50)
        
        # Verificar usuarios
        users = User.query.all()
        print(f"\n👥 USUARIOS EN SISTEMA: {len(users)}")
        for user in users:
            print(f"   • {user.username} ({user.role}) - {user.branch_name or 'Sin sucursal'}")
        
        # Verificar registros diarios
        all_records = DailyRecord.query.all()
        print(f"\n📊 REGISTROS DIARIOS TOTALES: {len(all_records)}")
        
        if all_records:
            print("\nTodos los registros:")
            for record in all_records:
                print(f"   • {record.record_date} - {record.branch_name} - Ventas: ${record.total_sales}")
        
        # Verificar registros de hoy específicamente
        today = date.today()
        today_records = DailyRecord.query.filter(DailyRecord.record_date == today).all()
        
        print(f"\n📅 REGISTROS DE HOY ({today}): {len(today_records)}")
        
        if today_records:
            total_cash = sum(float(r.cash_sales or 0) for r in today_records)
            total_mercadopago = sum(float(r.mercadopago_sales or 0) for r in today_records)
            total_debit = sum(float(r.debit_sales or 0) for r in today_records)
            total_credit = sum(float(r.credit_sales or 0) for r in today_records)
            total_sales = sum(float(r.total_sales or 0) for r in today_records)
            total_expenses = sum(float(r.total_expenses or 0) for r in today_records)
            
            print(f"\n💰 TOTALES DE HOY:")
            print(f"   • Efectivo: ${total_cash:.2f}")
            print(f"   • MercadoPago: ${total_mercadopago:.2f}")
            print(f"   • Débito: ${total_debit:.2f}")
            print(f"   • Crédito: ${total_credit:.2f}")
            print(f"   • Total Ventas: ${total_sales:.2f}")
            print(f"   • Total Gastos: ${total_expenses:.2f}")
            print(f"   • Ganancia: ${total_sales - total_expenses:.2f}")
            
            print(f"\n🏪 SUCURSALES QUE REPORTARON HOY:")
            branches = list(set([r.branch_name for r in today_records]))
            for branch in branches:
                print(f"   • {branch}")
                
        else:
            print("❌ No hay registros para el día de hoy")
            print("\n💡 SUGERENCIA: Crea algunos registros de prueba para ver datos en el dashboard")
            
            # Ofrecer crear registros de prueba
            create_test = input("\n¿Crear registros de prueba para hoy? (y/N): ")
            if create_test.lower() == 'y':
                create_test_records()

def create_test_records():
    """Crear registros de prueba para el día de hoy."""
    
    try:
        today = date.today()
        branches = ['Uruguay', 'Villa Cabello', 'Tacuari', 'Candelaria', 'Itaembe Mini']
        
        # Verificar que existan usuarios para cada sucursal
        print("\n🔨 Creando registros de prueba...")
        
        for i, branch in enumerate(branches):
            # Buscar usuario de la sucursal
            user = User.query.filter_by(branch_name=branch).first()
            
            if not user:
                print(f"⚠️  No hay usuario para {branch}, creando usuario de prueba...")
                user = User(
                    username=branch.lower().replace(' ', ''),
                    email=f"{branch.lower().replace(' ', '')}@test.com",
                    branch_name=branch,
                    role='branch_user',
                    is_admin=False,
                    is_active=True
                )
                user.set_password('test123')
                db.session.add(user)
                db.session.flush()  # Para obtener el ID
            
            # Crear registro de prueba
            record = DailyRecord(
                user_id=user.id,
                branch_name=branch,
                record_date=today,
                cash_sales=1000 + (i * 200),
                mercadopago_sales=800 + (i * 150),
                debit_sales=600 + (i * 100),
                credit_sales=400 + (i * 80),
                total_expenses=500 + (i * 50),
                notes=f"Registro de prueba para {branch}"
            )
            
            # El total se calcula automáticamente
            record.calculate_total_sales()
            
            db.session.add(record)
            print(f"✅ Creado registro para {branch}")
        
        db.session.commit()
        print("✅ Registros de prueba creados exitosamente")
        
        # Mostrar totales
        debug_dashboard_data()
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creando registros de prueba: {str(e)}")

if __name__ == '__main__':
    debug_dashboard_data()