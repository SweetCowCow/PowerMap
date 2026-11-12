"""Build tiny OSM .pbf fixtures for tests."""

from __future__ import annotations

from pathlib import Path

import osmium
from osmium.osm.mutable import Node, Relation, Way


class OsmBuilder:
    """Collect nodes/ways/relations, then write them in id order."""

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.ways: list[Way] = []
        self.relations: list[Relation] = []
        self._next_node = 1
        self._next_way = 1

    def node(self, lon: float, lat: float, tags: dict | None = None, node_id: int | None = None) -> int:
        nid = node_id or self._next_node
        self._next_node = max(self._next_node, nid) + 1
        self.nodes.append(Node(id=nid, location=(lon, lat), tags=tags or {}, version=1))
        return nid

    def way(self, coords: list[tuple[float, float]], tags: dict, way_id: int | None = None, closed: bool = False) -> int:
        node_ids = [self.node(lon, lat) for lon, lat in coords]
        if closed:
            node_ids.append(node_ids[0])
        wid = way_id or self._next_way
        self._next_way = max(self._next_way, wid) + 1
        self.ways.append(Way(id=wid, nodes=node_ids, tags=tags, version=1))
        return wid

    def relation(self, rel_id: int, members: list[tuple[str, int, str]], tags: dict) -> int:
        self.relations.append(Relation(id=rel_id, members=members, tags=tags, version=1))
        return rel_id

    def write(self, path: Path, timestamp: str | None = None) -> Path:
        header = osmium.io.Header()
        if timestamp:
            header.set("osmosis_replication_timestamp", timestamp)
        writer = osmium.SimpleWriter(str(path), header=header, overwrite=True)
        try:
            for n in sorted(self.nodes, key=lambda o: o.id):
                writer.add_node(n)
            for w in sorted(self.ways, key=lambda o: o.id):
                writer.add_way(w)
            for r in sorted(self.relations, key=lambda o: o.id):
                writer.add_relation(r)
        finally:
            writer.close()
        return path


def square(lon: float, lat: float, size: float = 0.01) -> list[tuple[float, float]]:
    return [(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size)]
