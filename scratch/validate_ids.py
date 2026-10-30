import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

scripts = re.findall(r'<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>', html)
full_script = '\n'.join(scripts)

required_ids = set(re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]\)', full_script))
dom_ids = set(re.findall(r'id=[\'"]([^\'"]+)[\'"]', html))

missing = []
for req in sorted(required_ids):
    # Some IDs might be dynamically generated or referenced conditionally like node- or btn-
    if req not in dom_ids:
        missing.append(req)

print(f"Total required JS IDs: {len(required_ids)}")
print(f"Total DOM IDs defined: {len(dom_ids)}")
if missing:
    print(f"MISSING IDs ({len(missing)}):")
    for m in missing:
        print(f"  - {m}")
else:
    print("ALL 74 JavaScript getElementById targets exist in the DOM!")

safeBinds = set(re.findall(r'safeBind\([\'"]([^\'"]+)[\'"]', full_script))
missing_binds = [s for s in sorted(safeBinds) if s not in dom_ids]
if missing_binds:
    print(f"MISSING safeBind targets: {missing_binds}")
else:
    print("ALL safeBind targets exist in the DOM!")
