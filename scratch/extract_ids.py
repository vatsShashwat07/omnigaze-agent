import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

scripts = re.findall(r'<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>', text)
full_script = '\n'.join(scripts)

ids = set(re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]\)', full_script))
print(f'Total getElementById targets ({len(ids)}):')
for i in sorted(ids):
    print(f'  - {i}')

safeBinds = set(re.findall(r'safeBind\([\'"]([^\'"]+)[\'"]', full_script))
print(f'\nsafeBind targets ({len(safeBinds)}):')
for s in sorted(safeBinds):
    print(f'  - {s}')
