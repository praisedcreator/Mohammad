"""Deterministic demo transfer checks, reused from the earlier inventory agent.

Fixed daily demand, one SKU, one route, no inbound receipts. Replace with the
existing analytics service before applying this calculator to real stock.
"""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone

class Rejected(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def number(value, name, minimum=0, integer=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise Rejected(name + " must be a finite number")
    if value < minimum or (integer and not isinstance(value, int)):
        raise Rejected(name + " has an invalid value")
    return value


def fresh(document):
    stamp = datetime.fromisoformat(document["as_of"])
    if stamp.tzinfo is None:
        raise Rejected("Snapshot timestamp must include a timezone")
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if age < -30 or age > 900 or not document.get("version"):
        raise Rejected("Snapshot is stale or lacks a version")


def fingerprint(inventory, policy):
    return digest({"inventory": {k: v for k, v in inventory.items() if k != "as_of"},
                   "policy": {k: v for k, v in policy.items() if k != "as_of"}})


def evaluate(quantity, inventory, policy, case):
    """Deterministic constant-demand example, with demand during transit included.

    Replace this with your existing day-by-day forecast/simulation service before
    production use. The model never supplies these calculations or policy limits.
    """
    number(quantity, "quantity", minimum=1, integer=True)
    fresh(inventory)
    fresh(policy)
    if inventory.get("inventory_valid") is not True or inventory.get("forecast_valid") is not True:
        raise Rejected("Invalid inventory or forecast data")
    if inventory.get("sku") != case["sku"]:
        raise Rejected("SKU is outside this exception's scope")
    if inventory.get("forecast_source") != "DEMO_CONSTANT_DEMAND":
        raise Rejected("Connect your production projection service for non-demo forecasts")
    source, destination, route = inventory["source"], inventory["destination"], inventory["route"]
    if source["site"] != case["source"] or destination["site"] != case["destination"] or source["site"] == destination["site"]:
        raise Rejected("Site scope mismatch")
    if inventory.get("unit") != "EA" or route["currency"] != policy["currency"]:
        raise Rejected("Unit or currency mismatch")
    if policy.get("approval_group") != "procurement":
        raise Rejected("Unexpected approval group")
    for site in (source, destination):
        for field in ("on_hand", "reserved", "blocked"):
            number(site[field], field, integer=True)
        number(site["daily_demand"], "daily_demand", minimum=0.000001)
        if site["reserved"] + site["blocked"] > site["on_hand"]:
            raise Rejected("Reservations exceed on-hand stock")
    for field in ("source_min_cover_days", "destination_target_cover_days", "destination_max_cover_days"):
        number(policy[field], field, minimum=1)
    for field in ("pack_size", "max_quantity", "max_transport_cost_minor"):
        number(policy[field], field, minimum=1, integer=True)
    if policy["destination_max_cover_days"] < policy["destination_target_cover_days"]:
        raise Rejected("Inconsistent coverage policy")
    transit = number(route["transit_days"], "transit_days", minimum=1, integer=True)
    cost = number(route["transport_cost_minor"], "transport_cost_minor", integer=True)
    number(inventory["supplier_lead_days"], "supplier_lead_days", minimum=1, integer=True)
    inbound = number(destination["confirmed_inbound_before_arrival"], "confirmed_inbound", integer=True)
    if inbound:
        raise Rejected("Use a time-phased projection service for inbound receipts; aggregate supply can hide an earlier shortage")
    available = lambda site: site["on_hand"] - site["reserved"] - site["blocked"]
    dest_available, source_available = available(destination), available(source)
    dest_at_arrival = dest_available + inbound - destination["daily_demand"] * transit
    source_at_arrival = source_available - quantity - source["daily_demand"] * transit
    destination_cover = (dest_at_arrival + quantity) / destination["daily_demand"]
    source_cover = source_at_arrival / source["daily_demand"]
    needed = max(0, policy["destination_target_cover_days"] * destination["daily_demand"] - dest_at_arrival)
    minimum_quantity = math.ceil(needed / policy["pack_size"]) * policy["pack_size"]
    conditions = {
        "no_replenishment_needed": minimum_quantity == 0,
        "quantity_exceeds_limit": quantity > policy["max_quantity"],
        "invalid_pack_multiple": quantity % policy["pack_size"] != 0,
        "transfer_arrives_after_stockout": dest_at_arrival < 0,
        "source_floor_breached": source_cover < policy["source_min_cover_days"],
        "destination_target_not_met": destination_cover < policy["destination_target_cover_days"],
        "destination_overstock": destination_cover > policy["destination_max_cover_days"],
        "transport_budget_exceeded": cost > policy["max_transport_cost_minor"],
    }
    violations = [name for name, failed in conditions.items() if failed]
    return {"allowed": not violations, "violations": violations, "quantity": quantity,
            "minimum_quantity": minimum_quantity, "destination_available_now": dest_available,
            "destination_units_before_arrival": dest_at_arrival,
            "destination_units_after_arrival": dest_at_arrival + quantity,
            "destination_cover_days_after_arrival": round(destination_cover, 3),
            "source_units_after_arrival": source_at_arrival,
            "source_cover_days_after_arrival": round(source_cover, 3),
            "transport_cost_minor": cost, "currency": route["currency"], "transit_days": transit,
            "supplier_lead_days": inventory["supplier_lead_days"],
            "forecast_source": inventory["forecast_source"],
            "evidence_fingerprint": fingerprint(inventory, policy)}
