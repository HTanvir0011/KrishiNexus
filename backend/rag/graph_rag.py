"""Multi-hop supply-chain GraphRAG over a NetworkX knowledge graph (Neo4j-compatible schema).

Node labels and relationships::

    (:Upazila)-[:IN_DISTRICT]->(:District)
    (:Upazila)-[:GROWS]->(:Crop)
    (:Upazila)-[:NEAR_STORAGE {road_km}]->(:ColdStorage)<-[:STORED_AT]-(:Crop)
    (:ColdStorage)-[:SHIPS_VIA]->(:TransportCorridor)<-[:ORIGIN_OF]-(:District)
    (:TransportCorridor)-[:DELIVERS_TO]->(:Market)-[:BUYS]->(:Crop)
    (:Crop)-[:GOVERNED_BY]->(:Rule)-[:CITED_IN]->(:Document)
    (:ColdStorage)-[:ENFORCES]->(:Rule)

The graph is assembled from the live MCP seed data (bd_geo, DAM hubs, BCSA facilities)
and the knowledge seed, so traversal results stay consistent with what the MCP tools
return. Paths are ranked by net Tk/kg to the grower after transit loss, freight, hub fees
and storage.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache

import networkx as nx
from pydantic import BaseModel

from config import now_bdt
from mcp_servers import bd_geo
from mcp_servers.coldchain_iot_mcp import FACILITIES, open_farmer_quota_mt
from mcp_servers.dam_market_mcp import (
    CROP_SURPLUS_DISTRICTS,
    SEASONAL_CURVES,
    SELLING_HUBS,
    hub_buying_price,
    hub_fees,
    pooled_truck_leg,
)
from mcp_servers.base import ToolExecutionError
from rag.knowledge_seed import GRAPH_RULES, KNOWLEDGE_DOCS
from schemas.mcp_models import Crop, Grade, HubType

FOCUS_DISTRICTS = ("Bogura", "Rangpur", "Munshiganj", "Sunamganj", "Thakurgaon", "Jessore", "Kishoreganj", "Netrokona")
HAOR = frozenset({"Sunamganj", "Kishoreganj", "Netrokona"})
STORABLE = frozenset({Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO})
NEAR_STORAGE_KM = 60.0


class GraphHop(BaseModel):
    node_id: str
    node_type: str
    label: str
    relation_to_next: str | None


class GraphPath(BaseModel):
    rank: int
    crop: Crop
    hops: list[GraphHop]
    storage_facility: str | None
    storage_open_quota_t: float | None
    storage_cost_tk_per_kg: float
    corridor: str
    corridor_road_km: float
    corridor_cost_tk_per_kg: float
    bridges: list[str]
    market: str
    market_type: str
    hub_price_today_tk_per_kg: float
    hub_fees_tk_per_kg: float
    net_to_grower_tk_per_kg: float
    narrative: str


class GraphRuleView(BaseModel):
    rule_id: str
    name: str
    kind: str
    statement: str
    cited_docs: list[str]


class GraphEdgeView(BaseModel):
    source: str
    target: str
    relation: str


class GraphTraversalResult(BaseModel):
    start_node: str
    start_district: str
    crops: list[Crop]
    paths_considered: int
    paths: list[GraphPath]
    rules: list[GraphRuleView]
    subgraph_nodes: list[GraphHop]
    subgraph_edges: list[GraphEdgeView]
    cypher: str
    graph_stats: dict[str, int]
    notes: list[str]


def _node(kind: str, key: str) -> str:
    return f"{kind}:{key}"


class SupplyChainGraph:
    def __init__(self) -> None:
        self.g = nx.DiGraph()
        self._build()

    def _add(self, node_id: str, node_type: str, label: str, **attrs: object) -> None:
        self.g.add_node(node_id, node_type=node_type, label=label, **attrs)

    def _build(self) -> None:
        g = self.g
        for crop in Crop:
            self._add(_node("CROP", crop.value), "Crop", crop.value)
        for doc in KNOWLEDGE_DOCS:
            self._add(_node("DOC", doc.doc_id), "Document", doc.title, source=doc.source)
        for rule in GRAPH_RULES:
            self._add(_node("RULE", rule.rule_id), "Rule", rule.name, kind=rule.kind, statement=rule.statement)
            for doc_id in rule.cites:
                g.add_edge(_node("RULE", rule.rule_id), _node("DOC", doc_id), relation="CITED_IN")
            for crop_name in rule.crops or tuple(c.value for c in Crop):
                g.add_edge(_node("CROP", crop_name), _node("RULE", rule.rule_id), relation="GOVERNED_BY")

        market_districts: set[str] = set()
        wfp_counts = Counter(h.district for h in SELLING_HUBS if h.hub_type is HubType.WFP_AGGREGATION_CENTRE)
        for hub in SELLING_HUBS:
            if hub.hub_type is HubType.WFP_AGGREGATION_CENTRE:
                continue
            self._add(_node("MKT", hub.hub_id), "Market", hub.name, hub_type=hub.hub_type.value, district=hub.district, hub_id=hub.hub_id)
            market_districts.add(hub.district)
        for district, count in wfp_counts.items():
            representative = next(h for h in SELLING_HUBS if h.district == district and h.hub_type is HubType.WFP_AGGREGATION_CENTRE)
            self._add(_node("MKT", f"WFP-{district}"), "Market", f"WFP Aggregation Centres, {district} ({count})",
                      hub_type=HubType.WFP_AGGREGATION_CENTRE.value, district=district, hub_id=representative.hub_id)
            market_districts.add(district)
        for market_id, data in list(g.nodes(data=True)):
            if data["node_type"] != "Market":
                continue
            for crop in Crop:
                if not (data["hub_type"] == HubType.WFP_AGGREGATION_CENTRE.value and crop is Crop.BORO_RICE):
                    g.add_edge(market_id, _node("CROP", crop.value), relation="BUYS")

        for district_name in FOCUS_DISTRICTS:
            district = bd_geo.district_by_name(district_name)
            self._add(_node("DIST", district_name), "District", district_name, division=district.division)
            upazilas = bd_geo.upazilas_in(district_name)
            if not any(u.name.endswith("Sadar") for u in upazilas):
                upazilas.append(bd_geo.Upazila(f"{district_name} Sadar", district_name, district.lat, district.lon))
            grown = [c for c in Crop if district_name in CROP_SURPLUS_DISTRICTS[c]]
            if district_name in HAOR and Crop.BORO_RICE not in grown:
                grown.append(Crop.BORO_RICE)
            for upz in upazilas:
                uid = _node("UPZ", upz.name)
                self._add(uid, "Upazila", upz.name, district=district_name, lat=upz.lat, lon=upz.lon)
                g.add_edge(uid, _node("DIST", district_name), relation="IN_DISTRICT")
                for crop in grown:
                    g.add_edge(uid, _node("CROP", crop.value), relation="GROWS")
            for market_district in sorted(market_districts):
                destination = bd_geo.district_by_name(market_district)
                leg = pooled_truck_leg(district, destination, destination.lat, destination.lon)
                cid = _node("COR", f"{district_name}->{market_district}")
                self._add(cid, "TransportCorridor", f"{district_name} -> {market_district}", road_km=leg.road_km,
                          cost_per_kg=leg.cost_per_kg, transit_hours=leg.transit_hours,
                          bridges=[b.name for b in leg.bridges], destination=market_district)
                g.add_edge(_node("DIST", district_name), cid, relation="ORIGIN_OF")
                for market_id, data in g.nodes(data=True):
                    if data["node_type"] == "Market" and data["district"] == market_district:
                        g.add_edge(cid, market_id, relation="DELIVERS_TO")

        for facility in FACILITIES.values():
            sid = _node("CS", facility.facility_id)
            self._add(sid, "ColdStorage", facility.name, district=facility.district, facility_id=facility.facility_id,
                      tariff=facility.tariff_tk_per_kg, handling=facility.handling_fee_tk_per_kg)
            g.add_edge(sid, _node("RULE", "RULE-POT-STORE"), relation="ENFORCES")
            for crop in STORABLE:
                g.add_edge(_node("CROP", crop.value), sid, relation="STORED_AT")
            if facility.district in FOCUS_DISTRICTS:
                for cid in g.successors(_node("DIST", facility.district)):
                    g.add_edge(sid, cid, relation="SHIPS_VIA")
            for uid, data in list(g.nodes(data=True)):
                if data["node_type"] != "Upazila":
                    continue
                km = bd_geo.road_distance_km(data["lat"], data["lon"], facility.lat, facility.lon)
                if km <= NEAR_STORAGE_KM:
                    g.add_edge(uid, sid, relation="NEAR_STORAGE", road_km=round(km, 1))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        counts = Counter(data["node_type"] for _, data in self.g.nodes(data=True))
        edges = Counter(data["relation"] for _, _, data in self.g.edges(data=True))
        return {"nodes": self.g.number_of_nodes(), "edges": self.g.number_of_edges(),
                **{f"nodes.{k}": v for k, v in counts.items()}, **{f"edges.{k}": v for k, v in edges.items()}}

    def _resolve_start(self, start: str) -> str:
        upazila = bd_geo.resolve_upazila(start)
        uid = _node("UPZ", upazila.name)
        if uid not in self.g:
            raise ToolExecutionError(
                f"'{upazila.name}' is outside the graph; covered districts: {', '.join(FOCUS_DISTRICTS)}."
            )
        return uid

    def _hop(self, node_id: str, relation: str | None) -> GraphHop:
        data = self.g.nodes[node_id]
        return GraphHop(node_id=node_id, node_type=data["node_type"], label=data["label"], relation_to_next=relation)

    def _market_economics(self, market_id: str, crop: Crop) -> tuple[float, float] | None:
        data = self.g.nodes[market_id]
        hub = next(h for h in SELLING_HUBS if h.hub_id == data["hub_id"])
        price = hub_buying_price(hub, crop, Grade.A, now_bdt().date())
        return None if price is None else (price, hub_fees(hub, price))

    def traverse(self, start: str, crop: Crop | None = None, max_paths: int = 5) -> GraphTraversalResult:
        g = self.g
        uid = self._resolve_start(start)
        district = g.nodes[uid]["district"]
        grown = [Crop(g.nodes[c]["label"]) for c in g.successors(uid) if g.nodes[c]["node_type"] == "Crop"]
        crops = [crop] if crop else grown
        notes: list[str] = []
        if crop and crop not in grown:
            notes.append(f"{crop.value} is not a surplus crop of {district}; paths are still computed.")

        paths: list[GraphPath] = []
        for c in crops:
            crop_id = _node("CROP", c.value)
            if c in STORABLE:
                origins = [
                    (sid, g.edges[uid, sid]["road_km"]) for sid in g.successors(uid)
                    if g.nodes[sid]["node_type"] == "ColdStorage" and g.has_edge(crop_id, sid)
                ]
            else:
                origins = [(None, 0.0)]
            for sid, storage_km in origins:
                corridor_source = sid if sid else _node("DIST", district)
                for cid in g.successors(corridor_source):
                    if g.nodes[cid]["node_type"] != "TransportCorridor":
                        continue
                    for mid in g.successors(cid):
                        if not g.has_edge(mid, crop_id):
                            continue
                        economics = self._market_economics(mid, c)
                        if economics is None:
                            continue
                        price, fees = economics
                        corridor = g.nodes[cid]
                        open_quota = None
                        storage_cost = 0.0
                        hops = [self._hop(uid, "GROWS"), self._hop(crop_id, "STORED_AT" if sid else "SHIPS_VIA")]
                        if sid:
                            facility = FACILITIES[g.nodes[sid]["facility_id"]]
                            open_quota = open_farmer_quota_mt(facility)
                            if open_quota <= 0:
                                continue
                            storage_cost = facility.tariff_tk_per_kg + facility.handling_fee_tk_per_kg
                            hops.append(self._hop(sid, "SHIPS_VIA"))
                        hops += [self._hop(cid, "DELIVERS_TO"), self._hop(mid, None)]
                        loss_pct = min(40.0, corridor["transit_hours"] * SEASONAL_CURVES[c].transit_loss_pct_per_hour)
                        net = price * (1 - loss_pct / 100) - fees - corridor["cost_per_kg"] - storage_cost
                        market_label = g.nodes[mid]["label"]
                        narrative = (
                            f"{g.nodes[uid]['label']} -> {c.value}"
                            + (f" -> {g.nodes[sid]['label']} ({storage_km:.0f} km, {open_quota:.0f} t open, Tk {storage_cost:.2f}/kg)" if sid else "")
                            + f" -> {corridor['label']} (Tk {corridor['cost_per_kg']:.2f}/kg) -> {market_label} "
                            f"pays Tk {price:.2f}/kg; net Tk {net:.2f}/kg"
                        )
                        paths.append(
                            GraphPath(
                                rank=1, crop=c, hops=hops,
                                storage_facility=g.nodes[sid]["facility_id"] if sid else None,
                                storage_open_quota_t=round(open_quota, 1) if open_quota is not None else None,
                                storage_cost_tk_per_kg=round(storage_cost, 2),
                                corridor=corridor["label"], corridor_road_km=corridor["road_km"],
                                corridor_cost_tk_per_kg=corridor["cost_per_kg"], bridges=corridor["bridges"],
                                market=market_label, market_type=g.nodes[mid]["hub_type"],
                                hub_price_today_tk_per_kg=round(price, 2), hub_fees_tk_per_kg=round(fees, 2),
                                net_to_grower_tk_per_kg=round(net, 2), narrative=narrative,
                            )
                        )

        paths.sort(key=lambda p: -p.net_to_grower_tk_per_kg)
        top = [p.model_copy(update={"rank": i}) for i, p in enumerate(paths[:max_paths], start=1)]
        rule_ids = {r for c in crops for r in g.successors(_node("CROP", c.value)) if g.nodes[r]["node_type"] == "Rule"}
        rules = [
            GraphRuleView(rule_id=r.split(":", 1)[1], name=g.nodes[r]["label"], kind=g.nodes[r]["kind"],
                          statement=g.nodes[r]["statement"],
                          cited_docs=[d.split(":", 1)[1] for d in g.successors(r)])
            for r in sorted(rule_ids)
        ]
        node_ids = list(dict.fromkeys(h.node_id for p in top for h in p.hops)) + sorted(rule_ids)
        edges = [
            GraphEdgeView(source=a, target=b, relation=g.edges[a, b]["relation"])
            for a in node_ids for b in node_ids if g.has_edge(a, b)
        ]
        cypher = (
            "MATCH (u:Upazila {name: $upazila})-[:GROWS]->(c:Crop {name: $crop})\n"
            "OPTIONAL MATCH (u)-[ns:NEAR_STORAGE]->(s:ColdStorage)<-[:STORED_AT]-(c)\n"
            "MATCH (src)-[:SHIPS_VIA|ORIGIN_OF]->(t:TransportCorridor)-[:DELIVERS_TO]->(m:Market)-[:BUYS]->(c)\n"
            "WHERE src = coalesce(s, (u)-[:IN_DISTRICT]->(:District))\n"
            "OPTIONAL MATCH (c)-[:GOVERNED_BY]->(r:Rule)-[:CITED_IN]->(d:Document)\n"
            "RETURN u, c, s, t, m, collect(DISTINCT r) AS rules ORDER BY t.cost_per_kg LIMIT $max_paths"
        )
        return GraphTraversalResult(
            start_node=uid,
            start_district=district,
            crops=crops,
            paths_considered=len(paths),
            paths=top,
            rules=rules,
            subgraph_nodes=[self._hop(n, None) for n in node_ids],
            subgraph_edges=edges,
            cypher=cypher,
            graph_stats=self.stats(),
            notes=notes,
        )

    def facts(self, start: str, crop: Crop | None, limit: int = 3) -> list[str]:
        """Compact textual facts from the best paths and rules, for grounding RAG answers."""
        result = self.traverse(start, crop, max_paths=limit)
        return [p.narrative for p in result.paths] + [f"Rule {r.rule_id}: {r.statement}" for r in result.rules]


@lru_cache(maxsize=1)
def get_graph() -> SupplyChainGraph:
    return SupplyChainGraph()
