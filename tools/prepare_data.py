"""Run locally BEFORE deployment. Never imported by the Streamlit application.

Partition exact official observations; do not aggregate, fill, round or rename.
Atomic release directories keep an interrupted build away from the current index.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import sys
import uuid
import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.bulk import FAOSTATService


def prepare(cache, target):
    service = FAOSTATService(cache)
    target.mkdir(parents=True, exist_ok=True)
    release = 'release-' + uuid.uuid4().hex[:12]
    output = target / release
    output.mkdir()
    # Preparation is intentionally a separate maintenance process.
    paths = {code: service.ensure(code) for code in ('QCL','PP','TCL')}
    with duckdb.connect(config={'threads':1, 'memory_limit':'256MB'}) as con:
        con.read_parquet(str(paths['QCL'])).create_view('qcl')
        crops = con.execute('''SELECT DISTINCT Item FROM qcl WHERE Element='Area harvested'
                               AND NOT contains("Item Code (CPC)", 'F') ORDER BY Item''').df().Item.tolist()
        areas = con.execute('SELECT DISTINCT Area, "Area Code (M49)" FROM qcl ORDER BY Area').df().to_dict('records')
        availability = con.execute('''SELECT Area, Item, list(DISTINCT Year ORDER BY Year) AS Years,
                                      bool_or(Element='Area harvested') AS harvested
                                      FROM qcl WHERE Element IN ('Production','Area harvested','Yield')
                                      GROUP BY Area,Item ORDER BY Area,Item''').fetchall()
        availability = [[a,i,ys,harvested] for a,i,ys,harvested in availability if i in crops]
        index = {'schema':1, 'release':release, 'areas':areas, 'crops':crops, 'availability':availability, 'domains':{}}
        for code in paths:
            print('Preparing',code,flush=True)
            directory = output / code
            directory.mkdir()
            con.read_parquet(str(paths[code])).create_view('source', replace=True)
            condition = {
                'QCL': "Element IN ('Production','Area harvested','Yield')",
                'PP': "Element='Producer Price (USD/tonne)' AND Months='Annual value'",
                'TCL': "Element IN ('Export quantity','Import quantity','Export value','Import value')",
            }[code]
            domain = {'metadata':service.cached_metadata(code), 'columns':con.table('source').columns, 'files':{}}
            for item in crops:
                data = con.sql(f'SELECT * FROM source WHERE Item=? AND {condition} ORDER BY Area,Year,Element', params=[item])
                count = data.count('*').fetchone()[0]
                if not count:
                    continue
                filename = hashlib.sha256(item.encode()).hexdigest()[:20] + '.parquet'
                path = directory / filename
                data.write_parquet(str(path),compression='zstd',row_group_size=2048)
                domain['files'][item] = {'path':f'{release}/{code}/{filename}', 'rows':count,
                                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            index['domains'][code] = domain
        temp = target / 'index.json.gz.part'
        with gzip.open(temp,'wt',encoding='utf-8') as f:
            json.dump(index,f,ensure_ascii=False,separators=(',',':'))
        temp.replace(target/'index.json.gz')
    print('Prepared',sum(len(d['files']) for d in index['domains'].values()),'partitions',flush=True)
    print('Bytes',sum(p.stat().st_size for p in output.rglob('*.parquet')),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path,default=ROOT/'data/cache')
    parser.add_argument('--output',type=Path,default=ROOT/'data/prepared')
    args=parser.parse_args()
    prepare(args.cache,args.output)
