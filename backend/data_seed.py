"""Seed files for the compose ``data`` profile: PostgreSQL + pgvector, Neo4j, Redis and n8n.

The node serves its knowledge chunks, supply-chain graph and cron jobs in-process. This writes the same data out for
the real servers, so they hold exactly what the node retrieves from. The node does not read these servers back yet.

    python -m data_seed <out_dir>

    00-n8n-database.sql   CREATE DATABASE n8n (n8n keeps its workflows and executions there)
    10-rag-chunks.sql     PGVECTOR_SCHEMA plus one row per chunk, with the vector the node indexes
    graph.cypher          SupplyChainGraph as idempotent MERGE statements
    n8n-workflows.json    the two cron workflows, calling the backend at http://backend:8000

Postgres runs the .sql files once, on its first start, and ignores the other two files.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from automation.workflows import N8N_HANDLERS
from rag.graph_rag import get_graph
from rag.hybrid_retriever import EMBEDDING_DIM, PGVECTOR_SCHEMA, get_retriever

BACKEND_URL = "http://backend:8000"  # the backend's compose service name
N8N_IDS = ("KnxDailyDamSync1", "KnxHourlySarChk1")  # stable ids: a re-import updates the workflow instead of copying it


def _sql(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _sql_array(items: tuple[str, ...]) -> str:
    return "ARRAY[" + ",".join(_sql(i) for i in items) + "]::text[]"


def pgvector_sql() -> str:
    retriever = get_retriever()
    vectors = retriever.vectors.matrix
    # shortcut: the seed uses the default hashing embedder; a KNX_EMBEDDING_MODEL with another width needs VECTOR(n) changed.
    assert vectors.shape == (len(retriever.chunks), EMBEDDING_DIM), vectors.shape
    rows = []
    for chunk, vector in zip(retriever.chunks, vectors, strict=True):
        doc = chunk.doc
        values = [_sql(chunk.chunk_id), _sql(doc.doc_id), _sql(doc.title), _sql(doc.source), _sql_array(doc.crops),
                  _sql_array(doc.districts), _sql_array(doc.topics), _sql(chunk.header), _sql(chunk.text),
                  _sql("[" + ",".join(f"{x:.7g}" for x in vector) + "]") + "::vector"]
        rows.append("INSERT INTO rag_chunks (chunk_id, doc_id, title, source, crops, districts, topics, context_header, "
                    f"content, embedding) VALUES ({', '.join(values)}) ON CONFLICT (chunk_id) DO NOTHING;")
    return "\n".join(["BEGIN;", PGVECTOR_SCHEMA, *rows, "COMMIT;", ""])


def _cypher(value: object) -> str:
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(float(value))  # float() drops numpy's repr wrapper
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_cypher(v) for v in value) + "]"
    raise TypeError(f"no Cypher literal for {type(value).__name__}")


def _cypher_map(props: dict[str, object]) -> str:
    return "{" + ", ".join(f"`{k}`: {_cypher(v)}" for k, v in props.items()) + "}"


def graph_cypher() -> str:
    g = get_graph().g
    nodes: dict[str, list[str]] = defaultdict(list)
    for node_id, data in g.nodes(data=True):
        props = {k: v for k, v in data.items() if k != "node_type"}
        nodes[data["node_type"]].append(f"{{id: {_cypher(node_id)}, props: {_cypher_map(props)}}}")
    edges: dict[str, list[str]] = defaultdict(list)
    for a, b, data in g.edges(data=True):
        props = {k: v for k, v in data.items() if k != "relation"}
        edges[data["relation"]].append(f"{{a: {_cypher(a)}, b: {_cypher(b)}, props: {_cypher_map(props)}}}")
    lines = ["CREATE CONSTRAINT knx_node_id IF NOT EXISTS FOR (n:KnxNode) REQUIRE n.id IS UNIQUE;"]
    lines += [f"UNWIND [{', '.join(rows)}] AS row MERGE (n:KnxNode {{id: row.id}}) SET n:{label}, n += row.props;"
              for label, rows in nodes.items()]
    lines += [f"UNWIND [{', '.join(rows)}] AS row MATCH (a:KnxNode {{id: row.a}}), (b:KnxNode {{id: row.b}}) "
              f"MERGE (a)-[r:{rel}]->(b) SET r += row.props;" for rel, rows in edges.items()]
    assert sum(map(len, nodes.values())) == g.number_of_nodes() and sum(map(len, edges.values())) == g.number_of_edges()
    return "\n".join(lines) + "\n"


def n8n_workflows() -> list[dict[str, object]]:
    return [{"id": i, **w} for i, w in zip(N8N_IDS, N8N_HANDLERS.workflow_definitions(BACKEND_URL), strict=True)]


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {"00-n8n-database.sql": "CREATE DATABASE n8n;\n", "10-rag-chunks.sql": pgvector_sql(),
             "graph.cypher": graph_cypher(), "n8n-workflows.json": json.dumps(n8n_workflows(), ensure_ascii=False, indent=1)}
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"{name}: {len(text.encode()):,} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
