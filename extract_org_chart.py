import html
import json
import re

# Read the HTML file
file_path = r"C:\Users\Sam\.cursor\Projects\Frappe HR\BEI Company Details\BEI Org Chart.drawio (1).html"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the data-mxgraph attribute using regex
pattern = r'data-mxgraph="([^"]+)"'
match = re.search(pattern, content)

if match:
    # The value is HTML-encoded JSON, decode it
    encoded_json = match.group(1)
    # Decode HTML entities
    decoded_json = html.unescape(encoded_json)
    # Parse JSON
    data = json.loads(decoded_json)
    
    # Get the XML content
    xml_str = html.unescape(data['xml'])
    
    # Save raw XML first for inspection
    xml_file = r"C:\Users\Sam\.cursor\Projects\Frappe HR\BEI Company Details\org_chart_raw.xml"
    with open(xml_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    print(f"Raw XML saved to: {xml_file}\n")
    
    # Extract org chart data using regex
    org_chart_data = []
    
    # Find all UserObject elements - extract the full tag first
    # Pattern: <UserObject ... >
    userobject_tags = re.finditer(r'<UserObject[^>]*>', xml_str)
    
    matches = []
    for tag_match in userobject_tags:
        tag_content = tag_match.group(0)
        # Extract id
        id_match = re.search(r'id="([^"]+)"', tag_content)
        if not id_match:
            continue
        obj_id = id_match.group(1)
        
        # Extract label - handle HTML-encoded content
        # Label can span multiple lines and contain quotes, so we need a different approach
        # Find the position of this UserObject tag
        tag_start = tag_match.start()
        # Find the closing > of UserObject
        tag_end = tag_match.end()
        # Get the full UserObject element including its content
        # Look for the closing </UserObject>
        closing_match = re.search(r'</UserObject>', xml_str[tag_start:])
        if closing_match:
            full_element = xml_str[tag_start:tag_start + closing_match.end()]
            # Extract label from the full element
            label_match = re.search(r'label="((?:[^"]|&quot;)+)"', full_element)
            if label_match:
                label_html = html.unescape(label_match.group(1).replace('&quot;', '"'))
                matches.append((obj_id, label_html))
    
    # Now process the matches
    for obj_id, label_html in matches:
        
        # Extract name - usually first text before <div> or in first <span>/<font>
        # Try multiple patterns
        name = ''
        # Pattern 1: Text before first <div>
        name_match = re.search(r'^([^<]+?)(?:<div|$)', label_html)
        if name_match:
            name = name_match.group(1).strip()
        else:
            # Pattern 2: First <span> or <font> content
            name_match = re.search(r'<(?:span|font)[^>]*>([^<]+)</(?:span|font)>', label_html)
            if name_match:
                name = name_match.group(1).strip()
            else:
                # Pattern 3: First text in <div><font> or <div>text
                name_match = re.search(r'<div[^>]*><(?:font|span)[^>]*>([^<]+)</(?:font|span)>|<div[^>]*>([^<]+)</div>', label_html)
                if name_match:
                    name = (name_match.group(1) or name_match.group(2)).strip()
        
        # Extract position - usually in <i> tags or <font> with gray color
        position = ''
        # Pattern 1: <i> tags
        pos_match = re.search(r'<i[^>]*>([^<]+)</i>', label_html)
        if pos_match:
            position = pos_match.group(1).strip()
        else:
            # Pattern 2: <font> with color gray or specific styling
            pos_match = re.search(r'<font[^>]*(?:color|style)[^>]*>([^<]+)</font>', label_html)
            if pos_match:
                position = pos_match.group(1).strip()
        
        # Clean position - remove any remaining HTML
        position = re.sub(r'<[^>]+>', '', position).strip()
        
        # Extract email - from mailto links
        email = ''
        email_match = re.search(r'mailto:([^"&]+)', label_html)
        if email_match:
            email = email_match.group(1).strip()
        else:
            # Try href="mailto:..."
            email_match = re.search(r'href="mailto:([^"]+)"', label_html)
            if email_match:
                email = email_match.group(1).strip()
        
        # Clean up name - remove HTML tags
        name = re.sub(r'<[^>]+>', '', name).strip()
        
        if name:  # Only add if we have a name
            org_chart_data.append({
                'id': obj_id,
                'name': name,
                'position': position,
                'email': email
            })
    
    # Also find connections (edges) separately
    edge_pattern = r'<mxCell[^>]*edge="1"[^>]*source="([^"]*)"[^>]*target="([^"]*)"[^>]*>'
    edges = re.finditer(edge_pattern, xml_str)
    connections = []
    for edge in edges:
        connections.append({
            'source': edge.group(1),
            'target': edge.group(2)
        })
    
    # Build hierarchy - map connections to names
    nodes_by_id = {node['id']: node for node in org_chart_data}
    
    # Print the org chart structure
    print("=" * 80)
    print("ORGANIZATIONAL CHART EXTRACTED FROM DRAW.IO FILE")
    print("=" * 80)
    print(f"\nTotal nodes found: {len(org_chart_data)}")
    print(f"Total connections found: {len(connections)}\n")
    
    print("\n--- ORG CHART NODES ---\n")
    for i, node in enumerate(org_chart_data, 1):
        print(f"{i}. {node['name']}")
        if node['position']:
            print(f"   Position: {node['position']}")
        if node['email']:
            print(f"   Email: {node['email']}")
        print()
    
    # Build hierarchical structure
    print("\n--- HIERARCHICAL STRUCTURE ---\n")
    
    # Build hierarchy - map connections to names
    print("\n--- HIERARCHICAL STRUCTURE ---\n")
    
    # Find root nodes (nodes that are sources but not targets, or have most connections as source)
    all_sources = {conn['source'] for conn in connections}
    all_targets = {conn['target'] for conn in connections}
    
    # Find the CEO/top level (usually the node with most outgoing connections)
    source_counts = {}
    for conn in connections:
        source_counts[conn['source']] = source_counts.get(conn['source'], 0) + 1
    
    # Get root (node with most outgoing connections that's not a target)
    root_id = None
    if source_counts:
        # Find node with most outgoing connections that's not a target
        candidates = [(sid, count) for sid, count in source_counts.items() if sid not in all_targets]
        if candidates:
            root_id = max(candidates, key=lambda x: x[1])[0]
        else:
            # If all are targets, use the one with most connections
            root_id = max(source_counts.items(), key=lambda x: x[1])[0]
    
    def print_hierarchy(node_id, level=0, visited=None):
        if visited is None:
            visited = set()
        if node_id in visited:
            return
        visited.add(node_id)
        
        node = nodes_by_id.get(node_id)
        if not node:
            return
        
        indent = "  " * level
        position_str = f" ({node['position']})" if node['position'] else ""
        print(f"{indent}└─ {node['name']}{position_str}")
        
        # Find children (nodes where this is the source)
        children = [conn['target'] for conn in connections if conn['source'] == node_id]
        for child_id in children:
            print_hierarchy(child_id, level + 1, visited)
    
    if root_id and root_id in nodes_by_id:
        print("Organization Hierarchy:\n")
        print_hierarchy(root_id)
        print()
    else:
        # If no clear root, show connections
        print("Connection Map (showing first 20):\n")
        for conn in connections[:20]:
            source = nodes_by_id.get(conn['source'], {}).get('name', conn['source'])
            target = nodes_by_id.get(conn['target'], {}).get('name', conn['target'])
            print(f"  {source} -> {target}")
    
    # Save to a readable format
    output_file = r"C:\Users\Sam\.cursor\Projects\Frappe HR\BEI Company Details\org_chart_extracted.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("ORGANIZATIONAL CHART EXTRACTED FROM DRAW.IO FILE\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total nodes found: {len(org_chart_data)}\n")
        f.write(f"Total connections found: {len(connections)}\n\n")
        f.write("--- ORG CHART NODES ---\n\n")
        for i, node in enumerate(org_chart_data, 1):
            f.write(f"{i}. {node['name']}\n")
            if node['position']:
                f.write(f"   Position: {node['position']}\n")
            if node['email']:
                f.write(f"   Email: {node['email']}\n")
            f.write("\n")
    
    print(f"\nExtracted data saved to: {output_file}")

else:
    print("Could not find data-mxgraph attribute in the HTML file")
