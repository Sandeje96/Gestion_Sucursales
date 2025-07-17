from app import create_app, db
import sqlalchemy as sa

app = create_app()

with app.app_context():
    try:
        # Verificar si la columna ya existe
        inspector = sa.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('cash_trays')]
        
        if 'accumulated_cash_expenses' not in columns:
            print("🔧 Agregando columna accumulated_cash_expenses...")
            
            # Para SQLite, solo agregamos la columna (sin constraint)
            with db.engine.connect() as connection:
                connection.execute(sa.text("""
                    ALTER TABLE cash_trays 
                    ADD COLUMN accumulated_cash_expenses NUMERIC(12,2) NOT NULL DEFAULT 0.00
                """))
                connection.commit()
            
            print("✅ Campo agregado exitosamente")
        else:
            print("ℹ️ El campo ya existe en la base de datos")
        
        # Recalcular todas las bandejas para incluir los gastos
        print("🔄 Recalculando bandejas con gastos...")
        from app.models.cash_tray import CashTray
        
        # Primero, actualizar valores de gastos en registros existentes
        from app.models.daily_record import DailyRecord
        
        # Obtener todas las sucursales
        branches = db.session.query(DailyRecord.branch_name).distinct().all()
        
        for (branch_name,) in branches:
            print(f"🔄 Procesando {branch_name}...")
            
            # Obtener o crear bandeja
            tray = CashTray.query.filter_by(branch_name=branch_name).first()
            if not tray:
                continue
            
            # Calcular gastos acumulados de registros NO retirados
            records = DailyRecord.query.filter_by(
                branch_name=branch_name,
                is_withdrawn=False
            ).all()
            
            total_expenses = sum(float(r.total_expenses or 0) for r in records)
            tray.accumulated_cash_expenses = total_expenses
            
            print(f"   Gastos acumulados: ${total_expenses:.2f}")
        
        db.session.commit()
        print("✅ Bandejas recalculadas con gastos incluidos")
        
        # Mostrar resumen
        print("\n📊 RESUMEN DE BANDEJAS:")
        trays = CashTray.query.all()
        for tray in trays:
            available_cash = tray.get_available_cash()
            print(f"   {tray.branch_name}:")
            print(f"     Ventas efectivo: ${tray.accumulated_cash:.2f}")
            print(f"     Gastos efectivo: ${tray.accumulated_cash_expenses:.2f}")
            print(f"     Efectivo disponible: ${available_cash:.2f}")
            print(f"     Total bandeja: ${tray.get_total_accumulated():.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()