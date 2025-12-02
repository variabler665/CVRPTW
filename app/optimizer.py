import math
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple
from .graph import get_graph, shortest_path_info


@dataclass
class Request:
    id: int
    external_id: str
    volume: float
    window: Tuple[float, float]
    location: Tuple[float, float]


@dataclass
class VehicleProfile:
    id: int
    name: str
    capacity: float


@dataclass
class Route:
    vehicle: VehicleProfile
    stops: List[int]
    distance: float
    travel_time: float
    geometry: List[List[Tuple[float, float]]]


class CVRPTWOptimizer:
    def __init__(self, depot: Tuple[float, float], requests: List[Request], vehicles: List[VehicleProfile]):
        self.depot = depot
        self.requests = requests
        self.vehicles = vehicles
        self.graph = get_graph()
        self.distance_cache: Dict[Tuple[int, int], Tuple[float, float, List[Tuple[float, float]]]] = {}

    def compute_cost(self, from_loc: Tuple[float, float], to_loc: Tuple[float, float]) -> Tuple[float, float, List[Tuple[float, float]]]:
        key = (hash(from_loc), hash(to_loc))
        if key in self.distance_cache:
            return self.distance_cache[key]
        info = shortest_path_info(self.graph, from_loc, to_loc)
        result = (info["distance"], info["travel_time"], info["path"])
        self.distance_cache[key] = result
        return result

    def initial_solution(self):
        sorted_requests = sorted(self.requests, key=lambda r: r.window[0])
        routes = [[] for _ in self.vehicles]
        loads = [0 for _ in self.vehicles]
        for request in sorted_requests:
            best_idx = None
            for idx, vehicle in enumerate(self.vehicles):
                if loads[idx] + request.volume <= vehicle.capacity:
                    best_idx = idx
                    break
            if best_idx is None:
                continue
            routes[best_idx].append(request.id)
            loads[best_idx] += request.volume
        return routes

    def route_cost(self, route: List[int]) -> Tuple[float, float]:
        distance = 0.0
        time = 0.0
        prev = self.depot
        for req_id in route:
            req = next(r for r in self.requests if r.id == req_id)
            d, t, _ = self.compute_cost(prev, req.location)
            distance += d
            time += t
            if req.window[0] is not None and time < req.window[0]:
                time = req.window[0]
            if req.window[1] is not None and time > req.window[1]:
                distance += 1e6
            prev = req.location
        d, t, _ = self.compute_cost(prev, self.depot)
        return distance + d, time + t

    def random_destroy(self, routes: List[List[int]], remove_fraction: float = 0.2):
        flat = [r for route in routes for r in route]
        remove_count = max(1, int(len(flat) * remove_fraction))
        to_remove = set(random.sample(flat, remove_count))
        new_routes = []
        removed = []
        for route in routes:
            remaining = [r for r in route if r not in to_remove]
            removed.extend([r for r in route if r in to_remove])
            new_routes.append(remaining)
        return new_routes, removed

    def greedy_repair(self, routes: List[List[int]], removed: List[int]):
        remaining = removed.copy()
        random.shuffle(remaining)
        for req_id in remaining:
            request = next(r for r in self.requests if r.id == req_id)
            best_vehicle = None
            best_position = None
            best_cost = math.inf
            for v_idx, vehicle in enumerate(self.vehicles):
                route = routes[v_idx]
                load = sum(next(r.volume for r in self.requests if r.id == rid) for rid in route)
                if load + request.volume > vehicle.capacity:
                    continue
                for pos in range(len(route) + 1):
                    new_route = route[:pos] + [req_id] + route[pos:]
                    dist, _ = self.route_cost(new_route)
                    if dist < best_cost:
                        best_cost = dist
                        best_vehicle = v_idx
                        best_position = pos
            if best_vehicle is None:
                continue
            routes[best_vehicle].insert(best_position, req_id)
        return routes

    def solution_cost(self, routes: List[List[int]]):
        return sum(self.route_cost(route)[0] for route in routes)

    def optimize(self, iterations: int = 200):
        current = self.initial_solution()
        best = current
        best_cost = self.solution_cost(best)
        temperature = 1000
        cooling = 0.995
        for _ in range(iterations):
            destroyed, removed = self.random_destroy(current)
            candidate = self.greedy_repair(destroyed, removed)
            candidate_cost = self.solution_cost(candidate)
            delta = candidate_cost - best_cost
            if delta < 0 or math.exp(-delta / temperature) > random.random():
                current = candidate
                if candidate_cost < best_cost:
                    best = candidate
                    best_cost = candidate_cost
            temperature *= cooling
        return self.materialize(best)

    def materialize(self, routes: List[List[int]]):
        materialized = []
        for route, vehicle in zip(routes, self.vehicles):
            distance = 0
            travel_time = 0
            geometry_segments: List[List[Tuple[float, float]]] = []
            prev_loc = self.depot
            for req_id in route:
                req = next(r for r in self.requests if r.id == req_id)
                d, t, path = self.compute_cost(prev_loc, req.location)
                distance += d
                travel_time += t
                geometry_segments.append(path)
                prev_loc = req.location
            d, t, path = self.compute_cost(prev_loc, self.depot)
            if route:
                geometry_segments.append(path)
            distance += d
            travel_time += t
            materialized.append(
                Route(
                    vehicle=vehicle,
                    stops=route,
                    distance=distance,
                    travel_time=travel_time,
                    geometry=geometry_segments,
                )
            )
        return materialized


def select_vehicle_set(vehicles: List[VehicleProfile], total_demand: float, force_all: bool):
    if force_all:
        return vehicles
    sorted_vehicles = sorted(vehicles, key=lambda v: v.capacity, reverse=True)
    chosen = []
    capacity = 0
    for vehicle in sorted_vehicles:
        chosen.append(vehicle)
        capacity += vehicle.capacity
        if capacity >= total_demand:
            break
    return chosen
