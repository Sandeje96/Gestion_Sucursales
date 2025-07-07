import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar para Railway
os.environ['FLASK_ENV'] = 'production'

from app import create_app, db
from app.models.daily_record import DailyRecord

def test_branch_filters_fixed():
    """Probar los filtros corregidos en Railway."""
    
    app = create_app('production')
    
    with app.app_context():
        print("🧪 PROBANDO FILTROS CORREGIDOS EN RAILWAY")
        print("=" * 60)
        
        # Importar las funciones corregidas
        from app.routes.reports import (
            normalize_branch_name_fixed, 
            get_matching_branches_fixed,
            get_general_statistics_fixed
        )
        
        # 1. Ver sucursales en BD
        print("\n📋 SUCURSALES EN BASE DE DATOS:")
        branches = db.session.query(DailyRecord.branch_name).distinct().all()
        for i, (branch,) in enumerate(branches, 1):
            count = DailyRecord.query.filter(DailyRecord.branch_name == branch).count()
            print(f"   {i}. '{branch}' -> {count} registros")
        
        # 2. Probar normalización
        print(f"\n🔧 PROBANDO NORMALIZACIÓN:")
        test_names = ['Uruguay', 'uruguay', 'Villa Cabello', 'villa cabello', 
                     'Tacuari', 'tacuari', 'Candelaria', 'candelaria']
        
        for test_name in test_names:
            normalized = normalize_branch_name_fixed(test_name)
            print(f"   '{test_name}' -> '{normalized}'")
        
        # 3. Probar coincidencias
        print(f"\n🎯 PROBANDO COINCIDENCIAS:")
        test_filters = ['Uruguay', 'uruguay', 'Villa Cabello', 'villa cabello']
        
        for test_filter in test_filters:
            matches = get_matching_branches_fixed(test_filter)
            print(f"   Filtro '{test_filter}' -> Coincidencias: {matches}")
        
        # 4. Probar estadísticas con filtro
        print(f"\n📊 PROBANDO ESTADÍSTICAS CON FILTROS:")
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        for test_filter in ['Uruguay', 'Villa Cabello', 'Tacuari']:
            stats = get_general_statistics_fixed(start_date, end_date, test_filter)
            print(f"   Filtro '{test_filter}':")
            print(f"      Registros: {stats['total_records']}")
            print(f"      Ventas: ${stats['total_sales']:,.2f}")
            print(f"      Sucursales activas: {stats['active_branches']}")
        
        # 5. Comparar con "Todas" (sin filtro)
        stats_all = get_general_statistics_fixed(start_date, end_date, None)
        print(f"\n   SIN FILTRO (todas):")
        print(f"      Registros: {stats_all['total_records']}")
        print(f"      Ventas: ${stats_all['total_sales']:,.2f}")
        print(f"      Sucursales activas: {stats_all['active_branches']}")
        
        print(f"\n✅ PRUEBAS COMPLETADAS")

if __name__ == '__main__':
    test_branch_filters_fixed()