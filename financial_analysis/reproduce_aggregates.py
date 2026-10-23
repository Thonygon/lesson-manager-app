import collections
import datetime as dt
import json
import urllib.parse
import urllib.request
from decimal import Decimal


def load_env(path):
    data = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data


config = load_env("expo/.env.local")
base = config["EXPO_PUBLIC_SUPABASE_URL"].rstrip("/")
key = config["SUPABASE_SERVICE_ROLE_KEY"]


def get(table, params, count=False):
    uri = base + "/rest/v1/" + table + "?" + urllib.parse.urlencode(params)
    headers = {"apikey": key, "Authorization": "Bearer " + key, "Prefer": "count=exact" if count else "count=none"}
    with urllib.request.urlopen(urllib.request.Request(uri, headers=headers), timeout=20) as response:
        return json.load(response), response.headers.get("Content-Range", "")


def exact(table):
    _, range_header = get(table, {"select": "*", "limit": "0"}, True)
    return int(range_header.rsplit("/", 1)[-1])


def bounded(table, columns, maximum, order="id"):
    total = exact(table)
    if total > maximum:
        return None, total
    rows = []
    for offset in range(0, total, 500):
        batch, _ = get(table, {"select": columns, "order": order + ".asc", "limit": "500", "offset": str(offset)})
        rows.extend(batch)
    return rows, total


out = {"queried_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
for name in ["profiles", "ai_usage_logs", "usage_tracking", "worksheets", "quick_exams", "lesson_plans", "learning_programs", "payments", "classes", "students", "user_subscriptions", "payment_events", "plans"]:
    try:
        out.setdefault("exact_counts", {})[name] = exact(name)
    except Exception as exc:
        out.setdefault("exact_counts", {})[name] = "unavailable:" + type(exc).__name__

profiles, _ = bounded("profiles", "user_id,role,can_teach,is_test_user,created_at", 100)
payments, payment_total = bounded("payments", "id,user_id,student,paid_amount,currency,payment_date,number_of_lesson,lesson_adjustment_units", 500)
classes, class_total = bounded("classes", "id,user_id,student,lesson_date,number_of_lesson", 3000)
logs, log_total = bounded("ai_usage_logs", "id,user_id,feature_name,status,created_at,provider,model_name,tokens_used,meta_json", 5000)
subscriptions, _ = bounded("user_subscriptions", "user_id,plan_id,subscription_status,manual_override,provider_customer_id", 1000, "user_id")
plans, _ = bounded("plans", "id,name,price,billing_interval,limits_json,active", 50)

if profiles is not None and payments is not None and classes is not None:
    payment_owners = collections.Counter(p.get("user_id") for p in payments)
    class_owners = collections.Counter(c.get("user_id") for c in classes)
    profile_map = {p.get("user_id"): p for p in profiles}
    out["owner_coverage"] = [{"rank": i + 1, "payments": n, "classes": class_owners.get(uid, 0), "profile_role": profile_map.get(uid, {}).get("role"), "can_teach": profile_map.get(uid, {}).get("can_teach"), "is_test_user": profile_map.get(uid, {}).get("is_test_user")} for i, (uid, n) in enumerate(payment_owners.most_common())]
    if payment_owners:
        uid = payment_owners.most_common(1)[0][0]
        own_payments = [p for p in payments if p.get("user_id") == uid]
        own_classes = [c for c in classes if c.get("user_id") == uid]
        annual = collections.defaultdict(lambda: {"payments": 0, "amount_by_currency": collections.defaultdict(Decimal), "sold_units": 0})
        for p in own_payments:
            year = str(p.get("payment_date") or "")[:4]
            annual[year]["payments"] += 1
            annual[year]["amount_by_currency"][str(p.get("currency") or "unknown")] += Decimal(str(p.get("paid_amount") or 0))
            annual[year]["sold_units"] += int(p.get("number_of_lesson") or 0)
        out["education_largest_payment_owner"] = {
            "years": {year: {"payments": val["payments"], "amount_by_currency": {currency: str(amount) for currency, amount in val["amount_by_currency"].items()}, "sold_units": val["sold_units"]} for year, val in sorted(annual.items())},
            "class_rows": len(own_classes),
            "taught_units": sum(int(c.get("number_of_lesson") or 0) for c in own_classes),
            "payment_adjustment_units": sum(int(p.get("lesson_adjustment_units") or 0) for p in own_payments),
            "distinct_students_in_payments": len({str(p.get("student")).strip().lower() for p in own_payments if p.get("student")}),
            "distinct_students_in_classes": len({str(c.get("student")).strip().lower() for c in own_classes if c.get("student")}),
            "distinct_students_in_either": len({str(r.get("student")).strip().lower() for r in own_payments + own_classes if r.get("student")}),
            "class_date_min": min((c.get("lesson_date") for c in own_classes if c.get("lesson_date")), default=None),
            "class_date_max": max((c.get("lesson_date") for c in own_classes if c.get("lesson_date")), default=None),
        }

if logs is not None:
    out["ai_by_month_status"] = [{"month": month, "status": status, "count": n} for (month, status), n in sorted(collections.Counter((str(row.get("created_at") or "")[:7], str(row.get("status") or "unknown")) for row in logs).items())]
    out["ai_by_feature_status"] = [{"feature": feature, "status": status, "count": n} for (feature, status), n in sorted(collections.Counter((str(row.get("feature_name") or "unknown"), str(row.get("status") or "unknown")) for row in logs).items())]
    out["ai_provider_coverage"] = {"provider_filled": sum(bool(row.get("provider")) for row in logs), "model_filled": sum(bool(row.get("model_name")) for row in logs), "tokens_filled": sum(row.get("tokens_used") is not None for row in logs)}
    out["ai_distinct_users"] = len({row.get("user_id") for row in logs if row.get("user_id")})
    meta = [row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {} for row in logs]
    out["ai_metadata_key_coverage"] = dict(collections.Counter(key for item in meta for key in item.keys()))
    out["ai_metadata_provider_coverage"] = {"provider": sum(bool(item.get("provider")) for item in meta), "model": sum(bool(item.get("model")) for item in meta), "provider_chain": sum(bool(item.get("provider_chain")) for item in meta)}
    if profiles is not None and payments is not None:
        main_owner = collections.Counter(p.get("user_id") for p in payments).most_common(1)[0][0]
        own_logs = [row for row in logs if row.get("user_id") == main_owner]
        out["ai_largest_payment_owner"] = {
            "rows": len(own_logs),
            "first": min((row.get("created_at") for row in own_logs), default=None),
            "last": max((row.get("created_at") for row in own_logs), default=None),
            "by_month_status": [{"month": month, "status": status, "count": n} for (month, status), n in sorted(collections.Counter((str(row.get("created_at") or "")[:7], str(row.get("status") or "unknown")) for row in own_logs).items())],
        }

if subscriptions is not None:
    out["subscriptions_by_status_plan"] = [{"plan": plan, "status": status, "override": override, "count": n} for (plan, status, override), n in sorted(collections.Counter((str(row.get("plan_id")), str(row.get("subscription_status")), bool(row.get("manual_override"))) for row in subscriptions).items())]
    out["subscriptions_provider_customer_filled"] = sum(bool(row.get("provider_customer_id")) for row in subscriptions)
if plans is not None:
    out["plans"] = plans

print(json.dumps(out, indent=2, ensure_ascii=False, default=dict))
