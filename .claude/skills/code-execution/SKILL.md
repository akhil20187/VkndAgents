---
description: Execute Python or JavaScript code safely in an E2B cloud sandbox - data analysis, API calls, file processing
allowed-tools:
  - Bash
---

# Code Execution Skill (E2B Sandbox)

This skill enables safe code execution in an E2B cloud sandbox environment.

## Prerequisites
- E2B API key must be set: `export E2B_API_KEY=your_key`
- E2B SDK installed: `pip install e2b`

## Usage

### Execute Python Code
```bash
cd /Users/akhilesh/Documents/Workplace/temporal-claude
./venv/bin/python -c "
import asyncio
from e2b import Sandbox

async def run_code():
    sandbox = await Sandbox.create()
    
    result = await sandbox.run_code('''
# Your Python code here
import pandas as pd
import numpy as np

# Example: data analysis
data = {'values': [1, 2, 3, 4, 5]}
df = pd.DataFrame(data)
print(f'Mean: {df.values.mean()}')
print(f'Sum: {df.values.sum()}')
''')
    
    print('STDOUT:', result.stdout)
    if result.stderr:
        print('STDERR:', result.stderr)
    
    await sandbox.close()

asyncio.run(run_code())
"
```

### Install Packages & Run
```bash
cd /Users/akhilesh/Documents/Workplace/temporal-claude
./venv/bin/python -c "
import asyncio
from e2b import Sandbox

async def run_with_packages():
    sandbox = await Sandbox.create()
    
    # Install packages
    await sandbox.run_code('!pip install requests beautifulsoup4')
    
    # Run code with packages
    result = await sandbox.run_code('''
import requests
from bs4 import BeautifulSoup

response = requests.get(\"https://example.com\")
soup = BeautifulSoup(response.text, \"html.parser\")
print(soup.title.string)
''')
    
    print(result.stdout)
    await sandbox.close()

asyncio.run(run_with_packages())
"
```

## When to Use
- When asked to run Python or JavaScript code
- For data analysis, calculations, or processing
- When code needs external packages or network access
- For safe, isolated code execution
- When testing code snippets before implementing

## Safety Notes
- Code runs in isolated E2B sandbox
- Network access is available
- File system is ephemeral (cleared after sandbox closes)
- Maximum execution time: 5 minutes per sandbox
