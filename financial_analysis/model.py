"""Recalculate transparent SaaS scenarios. Blank inputs remain unknown, never zero.

Usage: python3 financial_analysis/model.py [model_inputs.json]
Prints CSV to stdout. It does not contact production systems.
"""

import csv
import json
import sys
from decimal import Decimal
from pathlib import Path


def decimal_or_none(value):
    return None if value is None or value == "" else Decimal(str(value))


def display(value):
    return "" if value is None else format(value.quantize(Decimal("0.01")), "f")


path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("model_inputs.json")
inputs = json.loads(path.read_text(encoding="utf-8"))
price = decimal_or_none(inputs["price_usd_per_month"])
if price is None or price < 0:
    raise ValueError("price_usd_per_month must be nonnegative")

writer = csv.writer(sys.stdout)
writer.writerow(["modelo", "perfil", "usuarios_objetivo", "precio_usd_mes", "mrr_salida_usd", "arr_salida_usd", "facturacion_bruta_teorica_anual_usd", "coste_variable_usuario_mes_usd", "margen_contribucion_mes_usd", "resultado_operativo_mes_usd", "estado"])

unit_costs = {key: decimal_or_none(value) for key, value in inputs["unit_cost_usd"].items()}
fee = decimal_or_none(inputs["payment_fee_fraction"])
fixed = decimal_or_none(inputs["fixed_operating_usd_per_month"])
if fee is not None and not Decimal(0) <= fee < Decimal(1):
    raise ValueError("payment_fee_fraction must be in [0,1)")

for profile_name, usage in inputs["profiles"].items():
    consumption = {key: decimal_or_none(value) for key, value in usage.items()}
    if any(value is not None and value < 0 for value in consumption.values()):
        raise ValueError("usage must be nonnegative")
    complete = all(consumption.get(key) is not None and cost is not None for key, cost in unit_costs.items()) and fee is not None
    unit_variable = sum((consumption[key] * unit_costs[key] for key in unit_costs), Decimal(0)) + price * fee if complete else None
    for users in inputs["scales"]:
        if not isinstance(users, int) or users < 0:
            raise ValueError("scales must contain nonnegative integer users")
        for model in ("estabilizado", "progresivo"):
            monthly = inputs.get("progressive_paid_subscribers_by_month", {}).get(str(users))
            if model == "progresivo" and monthly is not None:
                if len(monthly) != 12 or any(not isinstance(n, int) or n < 0 for n in monthly):
                    raise ValueError("progressive monthly subscriber series must have 12 nonnegative integers")
                exit_users = monthly[-1]
                annual = price * sum(monthly)
            elif model == "progresivo":
                exit_users = None
                annual = None
            else:
                exit_users = users
                annual = price * users * 12
            mrr = price * exit_users if exit_users is not None else None
            variable_all = unit_variable * exit_users if unit_variable is not None and exit_users is not None else None
            contribution = mrr - variable_all if mrr is not None and variable_all is not None else None
            operating = contribution - fixed if contribution is not None and fixed is not None else None
            writer.writerow([model, profile_name, users, display(price), display(mrr), display(mrr * 12 if mrr is not None else None), display(annual), display(unit_variable), display(contribution), display(operating), "completo" if operating is not None and annual is not None else "faltan_insumos"])
