import io
import json
import math
from contextlib import contextmanager
from flask import Blueprint, jsonify, request, render_template
import pandas as pd
from .database import get_session
from .models import Vehicle, Order, Depot
from .geocode import geocode_address
from .graph import get_graph
from .optimizer import Request, VehicleProfile, CVRPTWOptimizer, select_vehicle_set

api_bp = Blueprint("api", __name__)
pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@contextmanager
def session_scope():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def serialize_order(order: Order):
    return {
        "id": order.id,
        "external_id": order.external_id,
        "address": order.address,
        "latitude": order.latitude,
        "longitude": order.longitude,
        "volume": order.volume,
        "window_start": order.window_start,
        "window_end": order.window_end,
    }


def serialize_vehicle(vehicle: Vehicle):
    return {
        "id": vehicle.id,
        "name": vehicle.name,
        "capacity": vehicle.capacity,
        "active": vehicle.active,
        "default_ready": vehicle.default_ready,
    }


@api_bp.route("/vehicles", methods=["GET", "POST"])
def vehicles_handler():
    with session_scope() as session:
        if request.method == "POST":
            data = request.json
            vehicle = Vehicle(name=data["name"], capacity=float(data["capacity"]), active=True)
            session.add(vehicle)
            session.commit()
        vehicles = session.query(Vehicle).all()
        return jsonify([serialize_vehicle(v) for v in vehicles])


@api_bp.route("/vehicles/<int:vehicle_id>", methods=["PUT", "DELETE"])
def vehicle_detail(vehicle_id):
    with session_scope() as session:
        vehicle = session.query(Vehicle).get(vehicle_id)
        if not vehicle:
            return jsonify({"error": "vehicle not found"}), 404
        if request.method == "DELETE":
            session.delete(vehicle)
            session.commit()
            return jsonify({"status": "deleted"})
        data = request.json
        vehicle.name = data.get("name", vehicle.name)
        if "capacity" in data:
            vehicle.capacity = float(data["capacity"])
        if "active" in data:
            vehicle.active = bool(data["active"])
        session.commit()
        return jsonify(serialize_vehicle(vehicle))


@api_bp.route("/orders", methods=["GET", "POST"])
def orders_handler():
    with session_scope() as session:
        if request.method == "POST":
            data = request.json
            lat = data.get("latitude")
            lon = data.get("longitude")
            address = data.get("address")
            if lat is None or lon is None:
                if not address:
                    return jsonify({"error": "address or coordinates required"}), 400
                coords = geocode_address(address)
                if not coords:
                    return jsonify({"error": "could not geocode"}), 400
                lat, lon = coords
            order = Order(
                external_id=data["external_id"],
                address=address,
                latitude=float(lat),
                longitude=float(lon),
                volume=float(data.get("volume", 0)),
                window_start=float(data.get("window_start")) if data.get("window_start") else None,
                window_end=float(data.get("window_end")) if data.get("window_end") else None,
            )
            session.add(order)
            session.commit()
        orders = session.query(Order).all()
        return jsonify([serialize_order(o) for o in orders])


@api_bp.route("/orders/<int:order_id>", methods=["PUT", "DELETE"])
def order_detail(order_id):
    with session_scope() as session:
        order = session.query(Order).get(order_id)
        if not order:
            return jsonify({"error": "order not found"}), 404
        if request.method == "DELETE":
            session.delete(order)
            session.commit()
            return jsonify({"status": "deleted"})
        data = request.json
        if "external_id" in data:
            order.external_id = data["external_id"]
        if "address" in data:
            order.address = data["address"]
        if "latitude" in data and "longitude" in data:
            order.latitude = float(data["latitude"])
            order.longitude = float(data["longitude"])
        if "volume" in data:
            order.volume = float(data["volume"])
        if "window_start" in data:
            order.window_start = float(data["window_start"]) if data["window_start"] is not None else None
        if "window_end" in data:
            order.window_end = float(data["window_end"]) if data["window_end"] is not None else None
        session.commit()
        return jsonify(serialize_order(order))


@api_bp.route("/orders/import", methods=["POST"])
def import_orders():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file required"}), 400
    content = file.read()
    stream = io.BytesIO(content)
    filename = file.filename or ""
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(stream)
    else:
        df = pd.read_excel(stream)
    required = {"id", "volume"}
    if not required.issubset(set(df.columns)):
        return jsonify({"error": "columns id and volume required"}), 400
    created = []
    with session_scope() as session:
        for _, row in df.iterrows():
            lat = row.get("lat")
            lon = row.get("lon")
            address = row.get("address") if not (isinstance(row.get("address"), float) and math.isnan(row.get("address"))) else None
            if (pd.isna(lat) or pd.isna(lon)) and address:
                coords = geocode_address(address)
                if coords:
                    lat, lon = coords
            if pd.isna(lat) or pd.isna(lon):
                continue
            order = Order(
                external_id=str(row.get("id")),
                address=address,
                latitude=float(lat),
                longitude=float(lon),
                volume=float(row.get("volume", 0)),
                window_start=float(row.get("window_start")) if "window_start" in row and not pd.isna(row.get("window_start")) else None,
                window_end=float(row.get("window_end")) if "window_end" in row and not pd.isna(row.get("window_end")) else None,
            )
            session.add(order)
            session.flush()
            created.append(order)
        session.commit()
    return jsonify([serialize_order(o) for o in created])


@api_bp.route("/depot", methods=["GET", "POST"])
def depot_handler():
    with session_scope() as session:
        depot = session.query(Depot).first()
        if request.method == "GET":
            if not depot:
                return jsonify(None)
            return jsonify({"latitude": depot.latitude, "longitude": depot.longitude, "address": depot.address})
        data = request.json
        lat = data.get("latitude")
        lon = data.get("longitude")
        address = data.get("address")
        if lat is None or lon is None:
            if not address:
                return jsonify({"error": "coordinates or address required"}), 400
            coords = geocode_address(address)
            if not coords:
                return jsonify({"error": "could not geocode"}), 400
            lat, lon = coords
        if depot:
            depot.latitude = float(lat)
            depot.longitude = float(lon)
            depot.address = address
        else:
            depot = Depot(latitude=float(lat), longitude=float(lon), address=address)
            session.add(depot)
        session.commit()
        return jsonify({"latitude": depot.latitude, "longitude": depot.longitude, "address": depot.address})


@api_bp.route("/solve", methods=["POST"])
def solve():
    payload = request.json or {}
    force_all = bool(payload.get("force_all", False))
    active_vehicle_ids = payload.get("vehicles")
    with session_scope() as session:
        depot = session.query(Depot).first()
        if not depot:
            return jsonify({"error": "depot is required"}), 400
        orders = session.query(Order).all()
        if not orders:
            return jsonify({"error": "no orders"}), 400
        vehicles = session.query(Vehicle).filter(Vehicle.active.is_(True)).all()
        if not vehicles:
            return jsonify({"error": "no active vehicles"}), 400
        if active_vehicle_ids:
            vehicles = [v for v in vehicles if v.id in active_vehicle_ids]
        if not vehicles:
            return jsonify({"error": "no selected vehicles"}), 400
        total_demand = sum(o.volume for o in orders)
        vehicle_profiles = [VehicleProfile(id=v.id, name=v.name, capacity=v.capacity) for v in vehicles]
        vehicle_set = select_vehicle_set(vehicle_profiles, total_demand, force_all)
        requests = [
            Request(
                id=o.id,
                external_id=o.external_id,
                volume=o.volume,
                window=(o.window_start or 0, o.window_end or float("inf")),
                location=(o.latitude, o.longitude),
            )
            for o in orders
        ]
        optimizer = CVRPTWOptimizer(depot=(depot.latitude, depot.longitude), requests=requests, vehicles=vehicle_set)
        routes = optimizer.optimize()
        response = []
        for route in routes:
            response.append(
                {
                    "vehicle": {"id": route.vehicle.id, "name": route.vehicle.name, "capacity": route.vehicle.capacity},
                    "stops": route.stops,
                    "distance_km": route.distance / 1000,
                    "travel_time_min": route.travel_time / 60,
                    "geometry": route.geometry,
                }
            )
        return jsonify({"routes": response})


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok", "graph_loaded": bool(get_graph())})
