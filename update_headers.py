import os
import glob

files = glob.glob('src/elemm/**/*.py', recursive=True) + glob.glob('src/elemm_gateway/**/*.py', recursive=True)
count = 0
for f in files:
    with open(f, 'r') as file:
        content = file.read()
    if '# Copyright (C) 2026 Marc Stöcker' in content and 'elemm.dev' not in content:
        content = content.replace('# Copyright (C) 2026 Marc Stöcker\n#', '# Copyright (C) 2026 Marc Stöcker\n# Website: https://elemm.dev\n#')
        with open(f, 'w') as file:
            file.write(content)
        count += 1
print(f"Updated {count} files.")
