# -*- coding: utf-8 -*-
"""
API Blueprint para integración con el Tablero Financiero central de Mundolimp.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date
import os
from app.models.daily_record import DailyRecord

api_bp = Blueprint('api', __name__, url_prefix='/api')

FINANZAS_API_KEY = os.environ.get('FINANZAS_API_KEY', 'mundolimp-finanzas-secret-2026')


@api_bp.route('/finanzas/resumen', methods=['GET'])
def finanzas_resumen():
    """
    Endpoint seguro para consulta de ventas y gastos de sucursales en un período.
    Requiere header: X-Api-Key: <TOKEN>
    Parámetros GET:
        desde: YYYY-MM-DD
        hasta: YYYY-MM-DD
    """
    # ── Validación de Token ──
    api_key = request.headers.get('X-Api-Key') or request.args.get('api_key')
    if not api_key or api_key != FINANZAS_API_KEY:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401

    # ── Parámetros de fecha ──
    desde_str = request.args.get('desde', '')
    hasta_str = request.args.get('hasta', '')

    hoy = date.today()
    primer_dia_mes = date(hoy.year, hoy.month, 1)

    try:
        desde = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else primer_dia_mes
    except ValueError:
        desde = primer_dia_mes

    try:
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy
    except ValueError:
        hasta = hoy

    if desde > hasta:
        desde, hasta = hasta, desde

    # ── Consulta a DailyRecord ──
    records = DailyRecord.query.filter(
        DailyRecord.record_date >= desde,
        DailyRecord.record_date <= hasta
    ).all()

    total_ventas = sum(float(r.total_sales or 0) for r in records)
    total_gastos = sum(float(r.total_expenses or 0) for r in records)
    ventas_efectivo = sum(float(r.cash_sales or 0) for r in records)
    ventas_mp = sum(float(r.mercadopago_sales or 0) for r in records)
    ventas_debito = sum(float(r.debit_sales or 0) for r in records)
    ventas_credito = sum(float(r.credit_sales or 0) for r in records)

    sucursales_dict = {}
    for r in records:
        b_name = (r.branch_name or 'Sin Nombre').strip().title()
        if b_name not in sucursales_dict:
            sucursales_dict[b_name] = {
                'sucursal': b_name,
                'ventas': 0.0,
                'gastos': 0.0,
                'registros': 0
            }
        sucursales_dict[b_name]['ventas'] += float(r.total_sales or 0)
        sucursales_dict[b_name]['gastos'] += float(r.total_expenses or 0)
        sucursales_dict[b_name]['registros'] += 1

    # Ordenar por ventas descendente
    detalle_por_sucursal = sorted(sucursales_dict.values(), key=lambda x: x['ventas'], reverse=True)

    return jsonify({
        'success': True,
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),
        'total_ventas': total_ventas,
        'total_gastos': total_gastos,
        'desglose_pagos': {
            'efectivo': ventas_efectivo,
            'mercadopago': ventas_mp,
            'debito': ventas_debito,
            'credito': ventas_credito
        },
        'detalle_por_sucursal': detalle_por_sucursal,
        'total_registros': len(records)
    })
