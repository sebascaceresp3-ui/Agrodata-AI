"""Package the app and its current prepared release, never the bulk cache."""
from pathlib import Path
import argparse
import ast
import gzip
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def package(output):
    with gzip.open(ROOT/'data/prepared/index.json.gz','rt',encoding='utf-8') as source:
        index = json.load(source)
    files = [p for p in ROOT.iterdir() if p.is_file() and
             (p.suffix in {'.py','.txt','.md','.cmd','.json'} or p.name in {'.env.example','.gitignore'})
             and p.name != 'run_checks.py']
    for folder in ('services','utils','components','tests','tools','.streamlit'):
        files.extend(p for p in (ROOT/folder).iterdir() if p.is_file() and p.suffix in {'.py','.json','.toml'})
    files.append(ROOT/'data/prepared/index.json.gz')
    for domain in index['domains'].values():
        for record in domain['files'].values():
            path = ROOT/'data/prepared'/record['path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError(f'Invalid prepared partition: {path}')
            files.append(path)
    for path in files:
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path,'agrodata-ai/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    print(f'{output}: {len(set(files))} files, {output.stat().st_size:,} bytes')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT.parent.parent/'AgroData-AI-cloud.zip')
    package(parser.parse_args().output)
