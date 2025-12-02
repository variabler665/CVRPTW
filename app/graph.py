import os
import json
from functools import lru_cache
import osmnx as ox
import networkx as nx

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
GRAPH_PATH = os.path.join(CACHE_DIR, "kyiv.graphml")


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def load_kyiv_graph():
    ensure_cache_dir()
    if os.path.exists(GRAPH_PATH):
        return ox.load_graphml(GRAPH_PATH)
    graph = ox.graph_from_place("Kyiv, Ukraine", network_type="drive")
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    ox.save_graphml(graph, GRAPH_PATH)
    return graph


@lru_cache(maxsize=1)
def get_graph():
    return load_kyiv_graph()


def nearest_node(graph: nx.MultiDiGraph, point):
    return ox.distance.nearest_nodes(graph, point[1], point[0])


def shortest_path_info(graph: nx.MultiDiGraph, origin, destination):
    origin_node = nearest_node(graph, origin)
    dest_node = nearest_node(graph, destination)
    path = ox.shortest_path(graph, origin_node, dest_node, weight="travel_time")
    length_m = sum(ox.utils_graph.get_route_edge_attributes(graph, path, "length"))
    travel_time = sum(ox.utils_graph.get_route_edge_attributes(graph, path, "travel_time"))
    coordinates = [(graph.nodes[node]["y"], graph.nodes[node]["x"]) for node in path]
    return {
        "path": coordinates,
        "distance": length_m,
        "travel_time": travel_time,
    }
