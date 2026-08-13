"""One-off utility: merge infrastructure-plan nodes into the knowledge graph.

Reads existing graphify-out/graph.json, merges hardcoded infrastructure node data,
reclusters communities, and regenerates GRAPH_REPORT.md and graph.json exports.
Uses graphify.{cache,build,cluster,analyze,report,export} and networkx.
"""

import json
from pathlib import Path

from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.build import build_from_json
from graphify.cache import save_semantic_cache
from graphify.cluster import cluster, score_all
from graphify.export import to_html, to_json
from graphify.report import generate
from networkx.readwrite import json_graph

new_extract = {
    "nodes": [
        {"id": "infra_node_a", "label": "node-a (Primary / Orchestration, 192.168.10.10)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_node_b", "label": "node-b (AI / Inference, prior Linux laptop i5/16GB)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_node_c", "label": "node-c (Data / Secondary, i5/8GB)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_node_d", "label": "node-d (Auxiliary, dead battery)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_nginx", "label": "nginx (Existing Host Reverse Proxy on node-a)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_cloudflared", "label": "cloudflared / node-a-n8n Tunnel (Already Running)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_ollama_migration", "label": "Ollama Migration: Windows 10.0.1.105 to node-b", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_adguard", "label": "AdGuard Home (DNS Ad-Blocker, to add on node-a)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_tailscale", "label": "Tailscale --ssh (Remote Access to All 4 Nodes)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_uptimerobot", "label": "UptimeRobot (External Monitoring, Survives Power Outage)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_ansible", "label": "Ansible (Config Management for 4 Nodes)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_restic_b2", "label": "restic to Backblaze B2 (Encrypted Incremental Backup)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_rationale_tunnel", "label": "Rationale: Tunnel over Port Forwarding (CGNAT-safe, zero open ports)", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_rationale_oom", "label": "Rationale: OOM — Bielik-11B + Qwen3:8B simultaneously exceed 16GB", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_rationale_ext_mon", "label": "Rationale: External monitoring must survive local power outage", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
        {"id": "infra_rationale_ollama_move", "label": "Rationale: Move Ollama to node-b — eliminates Windows laptop sleep dependency", "file_type": "document", "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "source_url": None, "captured_at": None, "author": None, "contributor": None},
    ],
    "edges": [
        {"source": "infra_node_a", "target": "infra_nginx", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_node_a", "target": "infra_cloudflared", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_node_a", "target": "infra_adguard", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_node_b", "target": "infra_ollama_migration", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_ollama_migration", "target": "infra_rationale_ollama_move", "relation": "rationale_for", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_rationale_tunnel", "target": "infra_cloudflared", "relation": "rationale_for", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_rationale_oom", "target": "infra_ollama_migration", "relation": "rationale_for", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_rationale_ext_mon", "target": "infra_uptimerobot", "relation": "rationale_for", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_ansible", "target": "infra_tailscale", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_restic_b2", "target": "infra_node_a", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_node_a", "target": "infra_tailscale", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
        {"source": "infra_node_b", "target": "infra_tailscale", "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": "INFRASTRUCTURE_PLAN.md", "source_location": None, "weight": 1.0},
    ],
    "hyperedges": [],
    "input_tokens": 0,
    "output_tokens": 0,
}

save_semantic_cache(new_extract["nodes"], new_extract["edges"], new_extract["hyperedges"])

existing_data = json.loads(Path("graphify-out/graph.json").read_text())
G_existing = json_graph.node_link_graph(existing_data, edges="links")

G_new = build_from_json(new_extract)
G_existing.update(G_new)
print(f"After merge: {G_existing.number_of_nodes()} nodes, {G_existing.number_of_edges()} edges")

communities = cluster(G_existing)
cohesion = score_all(G_existing, communities)
gods = god_nodes(G_existing)

labels_raw = json.loads(Path(".graphify_labels.json").read_text()) if Path(".graphify_labels.json").exists() else {}
labels = {int(k): v for k, v in labels_raw.items()}
for cid in communities:
    if cid not in labels:
        labels[cid] = "Infrastructure & Deployment"

detection = {"total_files": 28, "total_words": 24488, "files": {}, "warning": None}
tokens = {"input": 0, "output": 0}
surprises = surprising_connections(G_existing, communities)
questions = suggest_questions(G_existing, communities, labels)
report = generate(G_existing, communities, cohesion, labels, gods, surprises, detection, tokens, ".", suggested_questions=questions)

Path("graphify-out/GRAPH_REPORT.md").write_text(report, encoding="utf-8")
to_json(G_existing, communities, "graphify-out/graph.json")
to_html(G_existing, communities, "graphify-out/graph.html", community_labels=labels)
Path(".graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}))

print("Graph rebuilt.")
print("God nodes:", [g["label"] if isinstance(g, dict) else g for g in gods[:5]])
