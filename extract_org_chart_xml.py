import xml.etree.ElementTree as ET
import html
import re

# Read the XML file
file_path = r"C:\Users\Sam\.cursor\Projects\Frappe HR\BEI Company Details\BEI Org Chart.drawio (1).xml"

try:
    tree = ET.parse(file_path)
    root = tree.getroot()
except ET.ParseError as e:
    print(f"Error parsing XML: {e}")
    exit(1)

# Extract org chart data
org_chart_data = []
connections = []

# Find all UserObject elements (these contain the employee data)
for user_obj in root.iter('UserObject'):
    obj_id = user_obj.get('id', '')
    label_html = user_obj.get('label', '')
    
    if not label_html or not obj_id:
        continue
    
    # Decode HTML entities
    label_html = html.unescape(label_html)
    
    # Extract name - try multiple patterns
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
    
    # Extract position - usually in <i> tags
    position = ''
    pos_match = re.search(r'<i[^>]*>([^<]+)</i>', label_html)
    if pos_match:
        position = pos_match.group(1).strip()
        # Clean position - remove any remaining HTML
        position = re.sub(r'<[^>]+>', '', position).strip()
    
    # Extract email - from mailto links
    email = ''
    email_match = re.search(r'mailto:([^"&<>]+)', label_html)
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

# Find all connections (edges)
for cell in root.iter('mxCell'):
    if cell.get('edge') == '1':
        source = cell.get('source', '')
        target = cell.get('target', '')
        if source and target:
            connections.append({
                'source': source,
                'target': target
            })

# Build hierarchy
nodes_by_id = {node['id']: node for node in org_chart_data}

# Print results
print("=" * 80)
print("ORGANIZATIONAL CHART EXTRACTED FROM DRAW.IO XML FILE")
print("=" * 80)
print(f"\nTotal employees found: {len(org_chart_data)}")
print(f"Total connections found: {len(connections)}\n")

print("\n--- EMPLOYEE LIST ---\n")
for i, node in enumerate(org_chart_data, 1):
    print(f"{i}. {node['name']}")
    if node['position']:
        print(f"   Position: {node['position']}")
    if node['email']:
        print(f"   Email: {node['email']}")
    print()

# Build hierarchical structure
print("\n--- ORGANIZATIONAL HIERARCHY ---\n")

# Find root node (CEO/President - usually the one with most outgoing connections)
source_counts = {}
for conn in connections:
    source_counts[conn['source']] = source_counts.get(conn['source'], 0) + 1

# Find root (node with most outgoing connections)
root_id = None
if source_counts:
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
    position_str = f" - {node['position']}" if node['position'] else ""
    print(f"{indent}+- {node['name']}{position_str}")
    
    # Find children (nodes where this is the source)
    children = [conn['target'] for conn in connections if conn['source'] == node_id]
    for child_id in children:
        print_hierarchy(child_id, level + 1, visited)

if root_id and root_id in nodes_by_id:
    print("Organization Structure:\n")
    print_hierarchy(root_id)
    print()
else:
    print("Could not determine root node. Showing all connections:\n")
    for conn in connections[:30]:
        source = nodes_by_id.get(conn['source'], {}).get('name', conn['source'])
        target = nodes_by_id.get(conn['target'], {}).get('name', conn['target'])
        print(f"  {source} -> {target}")

# Save to file
output_file = r"C:\Users\Sam\.cursor\Projects\Frappe HR\BEI Company Details\org_chart_extracted.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("ORGANIZATIONAL CHART EXTRACTED FROM DRAW.IO XML FILE\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"Total employees found: {len(org_chart_data)}\n")
    f.write(f"Total connections found: {len(connections)}\n\n")
    f.write("--- EMPLOYEE LIST ---\n\n")
    for i, node in enumerate(org_chart_data, 1):
        f.write(f"{i}. {node['name']}\n")
        if node['position']:
            f.write(f"   Position: {node['position']}\n")
        if node['email']:
            f.write(f"   Email: {node['email']}\n")
        f.write("\n")
    
    f.write("\n--- ORGANIZATIONAL HIERARCHY ---\n\n")
    if root_id and root_id in nodes_by_id:
        def write_hierarchy(node_id, level=0, visited=None, file=f):
            if visited is None:
                visited = set()
            if node_id in visited:
                return
            visited.add(node_id)
            
            node = nodes_by_id.get(node_id)
            if not node:
                return
            
            indent = "  " * level
            position_str = f" - {node['position']}" if node['position'] else ""
            file.write(f"{indent}+- {node['name']}{position_str}\n")
            
            children = [conn['target'] for conn in connections if conn['source'] == node_id]
            for child_id in children:
                write_hierarchy(child_id, level + 1, visited, file)
        
        write_hierarchy(root_id)

print(f"\nExtracted data saved to: {output_file}")

# Also create a CSV file for easy import
csv_file = r"C:\Users\Sam\.cursor\Projects\Frappe HR\BEI Company Details\org_chart_employees.csv"
with open(csv_file, 'w', encoding='utf-8') as f:
    f.write("Name,Position,Email,Reports To\n")
    for node in org_chart_data:
        # Find who this person reports to
        reports_to = ''
        for conn in connections:
            if conn['target'] == node['id']:
                manager = nodes_by_id.get(conn['source'], {}).get('name', '')
                if manager:
                    reports_to = manager
                    break
        
        f.write(f'"{node["name"]}","{node["position"]}","{node["email"]}","{reports_to}"\n')

print(f"CSV file created: {csv_file}")

