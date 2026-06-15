import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def translate_flow_to_workflow(flow_data: dict) -> dict:
    """
    Translates visual React Flow graph (nodes & edges) into a sequential, 
    executable metadata structure for the execution engine.
    """
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])
    
    # Map nodes by ID
    node_map = {n["id"]: n for n in nodes}
    
    # Build adjacency lists for graph traversal
    adj = {n["id"]: [] for n in nodes}
    in_degree = {n["id"]: 0 for n in nodes}
    edge_types = {} # (source, target) -> edge_type (e.g. 'true', 'false', 'default')
    
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in node_map and tgt in node_map:
            adj[src].append(tgt)
            in_degree[tgt] += 1
            # n8n conditions use sourceHandle to differentiate true/false branches
            source_handle = edge.get("sourceHandle", "default")
            edge_types[(src, tgt)] = source_handle

    # Find starting nodes (nodes with 0 in-degree or type is leadSource)
    # n8n flows start at trigger/leadSource nodes
    start_nodes = [n_id for n_id, degree in in_degree.items() if degree == 0 or node_map[n_id].get("type") in ("csvUpload", "linkedinSearch", "apolloSearch", "manualLeads", "websiteLeads")]
    
    # Topological sort (Kahn's algorithm) to detect cycles and build sequence
    queue = list(start_nodes)
    ordered_ids = []
    in_degree_copy = in_degree.copy()
    
    while queue:
        curr = queue.pop(0)
        ordered_ids.append(curr)
        for neighbor in adj[curr]:
            in_degree_copy[neighbor] -= 1
            if in_degree_copy[neighbor] == 0:
                queue.append(neighbor)
                
    if len(ordered_ids) < len(nodes):
        logger.warning("Cycle detected in flow builder graph. Proceeding with partial topological sequence.")
        # Fallback: append any unvisited nodes to prevent omission
        unvisited = [n["id"] for n in nodes if n["id"] not in ordered_ids]
        ordered_ids.extend(unvisited)

    steps = []
    for node_id in ordered_ids:
        node = node_map.get(node_id)
        if not node:
            continue
            
        node_type = node.get("type", "")
        node_data = node.get("data", {})
        
        # Determine connections/outcomes
        next_nodes = adj.get(node_id, [])
        next_steps = {} # branch_name -> target_node_id
        for target_id in next_nodes:
            branch = edge_types.get((node_id, target_id), "default")
            next_steps[branch] = target_id

        step_def = {
            "id": node_id,
            "type": node_type,
            "label": node_data.get("label", node_type),
            "parameters": node_data.get("parameters", {}),
            "next_steps": next_steps
        }
        steps.append(step_def)
        
    return {
        "id": flow_data.get("id"),
        "name": flow_data.get("name", "Unnamed Flow"),
        "version": "1.0.0",
        "description": flow_data.get("description", "Translated visual builder flow"),
        "steps": steps,
        "raw_nodes": nodes,
        "raw_edges": edges
    }


def validate_flow_nodes(nodes: List[Dict], edges: List[Dict]) -> List[str]:
    """Validate flow structure and parameters before publishing."""
    errors = []
    if not nodes:
        errors.append("Flow has no nodes.")
        return errors

    has_source = any(n.get("type") in ("csvUpload", "linkedinSearch", "apolloSearch", "manualLeads", "websiteLeads") for n in nodes)
    if not has_source:
        errors.append("Flow must contain at least one Lead Source trigger node.")

    node_map = {n["id"]: n for n in nodes}
    for edge in edges:
        if edge.get("source") not in node_map:
            errors.append(f"Edge references non-existent source node: {edge.get('source')}")
        if edge.get("target") not in node_map:
            errors.append(f"Edge references non-existent target node: {edge.get('target')}")

    for node in nodes:
        n_id = node.get("id")
        n_type = node.get("type")
        params = node.get("data", {}).get("parameters", {})
        
        # Schema-like parameter checks
        if n_type == "linkedinSearch":
            if not params.get("keywords") and not params.get("industry"):
                errors.append(f"LinkedIn Search Node ({n_id}) requires either Keywords or Industry parameters.")
        elif n_type == "sendEmail":
            if not params.get("template") and not params.get("body_template"):
                errors.append(f"Send Email Node ({n_id}) requires an Email Template.")
        elif n_type == "delay":
            delay = params.get("delay")
            if delay is None or not str(delay).isdigit():
                errors.append(f"Delay Node ({n_id}) requires a positive integer Delay duration.")
        elif n_type == "condition":
            if not params.get("condition_type"):
                errors.append(f"Condition Node ({n_id}) requires a Condition Type parameter.")

    return errors
