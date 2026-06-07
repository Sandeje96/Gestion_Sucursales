# -*- coding: utf-8 -*-
"""
reset_branch_data.py
====================
Script para limpiar TODOS los datos cargados por las sucursales en Railway PostgreSQL.

MANTIENE:   users (usuarios, contrasenas, sesiones)
ELIMINA:    daily_records, branch_expenses, cash_trays

Uso:
    py -3 reset_branch_data.py
"""

import os
import sys


def get_database_url():
    """Obtiene la DATABASE_URL de Railway - siempre pide al usuario para evitar usar SQLite local."""
    print()
    print("Pega la DATABASE_URL de tu proyecto en Railway PostgreSQL.")
    print("La encontras en: Railway -> tu proyecto -> PostgreSQL -> Variables -> DATABASE_URL")
    print("(Empieza con postgresql:// o postgres://)")
    print()
    url = input("DATABASE_URL de Railway: ").strip()

    if not url:
        print("ERROR: No se ingreso ninguna URL.")
        sys.exit(1)

    # Validar que sea PostgreSQL
    if url.startswith('sqlite') or ':///' in url and 'postgres' not in url:
        print("ERROR: La URL ingresada parece ser SQLite, no PostgreSQL.")
        print("Necesitas la URL de Railway, no la local.")
        sys.exit(1)

    # Railway usa postgres:// pero psycopg2 necesita postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    return url


def main():
    print("=" * 60)
    print("  RESET DE DATOS DE SUCURSALES - Railway PostgreSQL")
    print("=" * 60)
    print()
    print("Este script eliminara PERMANENTEMENTE:")
    print("  - Todos los registros diarios       (daily_records)")
    print("  - Todos los gastos de sucursales    (branch_expenses)")
    print("  - Todas las bandejas de efectivo    (cash_trays)")
    print()
    print("Se CONSERVARA intacto:")
    print("  - Todos los usuarios (tabla users)")
    print("  - Todas las contrasenas")
    print("  - Todos los roles y permisos")
    print()

    # Primera confirmacion
    confirm1 = input("Estas seguro de que queres continuar? Escribe 'SI': ").strip()
    if confirm1.upper() != 'SI':
        print()
        print("Operacion cancelada. No se realizo ningun cambio.")
        sys.exit(0)

    # Segunda confirmacion
    confirm2 = input("Segunda confirmacion. Escribe 'BORRAR' para proceder: ").strip()
    if confirm2.upper() != 'BORRAR':
        print()
        print("Operacion cancelada. No se realizo ningun cambio.")
        sys.exit(0)

    print()
    print("Conectando a Railway PostgreSQL...")

    db_url = get_database_url()

    try:
        import psycopg2
    except ImportError:
        print()
        print("ERROR: Modulo 'psycopg2' no instalado.")
        print("Ejecuta: pip install psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cursor = conn.cursor()
        print("Conexion exitosa a la base de datos.")
        print()
    except Exception as e:
        print()
        print("ERROR al conectar: {}".format(e))
        sys.exit(1)

    try:
        # ── 1. Mostrar conteos ANTES del borrado ───────────────────────────────
        print("Conteo actual de registros en Railway:")

        tables_info = [
            ('daily_records',   'Registros diarios       '),
            ('branch_expenses', 'Gastos de sucursales    '),
            ('cash_trays',      'Bandejas de efectivo    '),
            ('users',           'Usuarios (NO se tocaran)'),
        ]

        counts = {}
        for table, label in tables_info:
            try:
                cursor.execute('SELECT COUNT(*) FROM "{}"'.format(table))
                count = cursor.fetchone()[0]
                counts[table] = count
                lock = "[PROTEGIDO]" if table == 'users' else "[A BORRAR] "
                print("  {} {} : {} registros".format(lock, label, count))
            except Exception as e:
                print("  [ERROR] No se pudo leer '{}': {}".format(table, e))
                counts[table] = 0

        print()

        # ── 2. Ejecutar el borrado ─────────────────────────────────────────────
        print("Ejecutando limpieza...")

        deletion_steps = [
            ('daily_records',   'Registros diarios'),
            ('branch_expenses', 'Gastos de sucursales'),
            ('cash_trays',      'Bandejas de efectivo'),
        ]

        deleted_counts = {}
        for table, label in deletion_steps:
            try:
                cursor.execute('DELETE FROM "{}"'.format(table))
                deleted = cursor.rowcount
                deleted_counts[table] = deleted
                print("  OK  {} : {} registros eliminados".format(label, deleted))
            except Exception as e:
                conn.rollback()
                print()
                print("ERROR al eliminar '{}': {}".format(table, e))
                print("Se hizo ROLLBACK. No se realizo ningun cambio.")
                cursor.close()
                conn.close()
                sys.exit(1)

        # ── 3. Verificar que users NO cambio ───────────────────────────────────
        cursor.execute('SELECT COUNT(*) FROM "users"')
        users_after = cursor.fetchone()[0]

        if users_after != counts.get('users', 0):
            conn.rollback()
            print()
            print("ERROR CRITICO: La tabla 'users' cambio ({} -> {})".format(
                counts.get('users'), users_after))
            print("Se hizo ROLLBACK. No se realizo ningun cambio.")
            cursor.close()
            conn.close()
            sys.exit(1)

        # ── 4. COMMIT ──────────────────────────────────────────────────────────
        conn.commit()

        print()
        print("=" * 60)
        print("  LIMPIEZA COMPLETADA CON EXITO")
        print("=" * 60)
        print()
        print("Resumen de cambios:")
        for table, label in deletion_steps:
            print("  - {} : {} registros eliminados".format(
                label, deleted_counts.get(table, 0)))
        print()
        print("Usuarios conservados: {}".format(users_after))
        print()
        print("El sistema esta listo para arrancar de cero con los mismos usuarios.")

    except Exception as e:
        conn.rollback()
        print()
        print("Error inesperado: {}".format(e))
        print("Se hizo ROLLBACK. No se realizo ningun cambio.")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
