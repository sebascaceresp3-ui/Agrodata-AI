"""Official bulk downloads, atomic versioned Parquet cache and precise queries."""
from __future__ import annotations
import json
import os
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import duckdb
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CATALOG_URL = "https://bulks-faostat.fao.org/production/datasets_E.json"
SOURCE_URL = "https://www.fao.org/faostat/en/#data"
DOMAINS = {"QCL": "Producción", "PP": "Precios al productor", "TCL": "Comercio"}
LOCK = threading.RLock()
REQUIRED = {"Area", "Item", "Element", "Year", "Unit", "Value"}

class FAOSTATError(RuntimeError):
    pass

class FAOSTATService:
    def __init__(self, cache_dir=None):
        self.root = Path(cache_dir or os.getenv("AGRODATA_CACHE", str(Path(__file__).resolve().parents[1] / "data/cache")))
        self.root.mkdir(parents=True, exist_ok=True)
        self.timeout = int(os.getenv("AGRODATA_TIMEOUT", "180"))
        self.warnings = []
        self._ready = {}
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))

    def catalog(self, refresh=False):
        path = self.root / "catalog.json"
        with LOCK:
            try:
                if refresh or not path.exists() or time.time() - path.stat().st_mtime > 86400:
                    r = self.session.get(CATALOG_URL, timeout=(15, 30))
                    r.raise_for_status()
                    payload = r.json()
                    if not isinstance(payload["Datasets"]["Dataset"], list):
                        raise ValueError("Catálogo inválido")
                    part = path.with_suffix(f".{uuid.uuid4().hex}.part")
                    part.write_text(json.dumps(payload), encoding="utf-8")
                    part.replace(path)
                return json.loads(path.read_text(encoding="utf-8"))["Datasets"]["Dataset"]
            except Exception as exc:
                if path.exists():
                    self.warnings.append("Catálogo sin conexión: se utiliza la última copia local.")
                    return json.loads(path.read_text(encoding="utf-8"))["Datasets"]["Dataset"]
                raise FAOSTATError(f"No se pudo consultar el catálogo oficial: {exc}") from exc

    def metadata(self, code):
        if code not in DOMAINS:
            raise FAOSTATError(f"Dominio no admitido: {code}")
        row = next((x for x in self.catalog() if x.get("DatasetCode") == code), None)
        if not row:
            raise FAOSTATError(f"Dominio {code} no encontrado")
        url = row.get("FileLocation", "")
        if urlparse(url).scheme != "https" or urlparse(url).hostname != "bulks-faostat.fao.org":
            raise FAOSTATError("La descarga no corresponde al servidor HTTPS oficial de FAOSTAT")
        return {"code": code, "name": row.get("DatasetName", DOMAINS[code]), "updated": row.get("DateUpdate", "No indicada"), "url": url, "source": SOURCE_URL}

    def ensure(self, code="QCL"):
        with LOCK:
            if code in self._ready:
                return self._ready[code]
            meta = self.metadata(code)
            manifest = self.root / f"{code}.json"
            old = None
            if manifest.exists():
                try:
                    old = json.loads(manifest.read_text())
                    cached = self.root / old['file']
                    with duckdb.connect() as check:
                        if not REQUIRED.issubset(check.read_parquet(str(cached)).columns):
                            raise ValueError('Esquema incompleto')
                except Exception:
                    old = None
                    self.warnings.append(f'{code}: caché dañada o incompleta; se descargará de nuevo.')
            if old and old.get("updated") == meta["updated"] and (self.root / old["file"]).exists():
                self._ready[code] = self.root / old["file"]
                return self._ready[code]
            token = uuid.uuid4().hex
            archive = self.root / f"{code}.{token}.zip.part"
            csv = self.root / f"{code}.{token}.csv.part"
            parquet = self.root / f"{code}.{token}.parquet"
            try:
                with self.session.get(meta["url"], stream=True, timeout=(15, self.timeout)) as response:
                    response.raise_for_status()
                    with archive.open("wb") as dst:
                        for chunk in response.iter_content(1024 * 1024):
                            dst.write(chunk)
                with zipfile.ZipFile(archive) as z:
                    members = [n for n in z.namelist() if n.lower().endswith(".csv") and "normalized" in n.lower()]
                    if len(members) != 1:
                        raise FAOSTATError("No se encontró un único CSV normalizado oficial")
                    with z.open(members[0]) as src, csv.open("wb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                with duckdb.connect(config={"threads": 2, "memory_limit": "1GB"}) as con:
                    relation = con.read_csv(str(csv), header=True, all_varchar=True)
                    if not REQUIRED.issubset(relation.columns):
                        raise FAOSTATError("Esquema FAOSTAT incompleto")
                    relation.create_view("raw")
                    con.execute('CREATE VIEW normalized AS SELECT * REPLACE (CAST(Year AS INTEGER) AS Year, CAST(Value AS DOUBLE) AS Value) FROM raw')
                    con.table("normalized").write_parquet(str(parquet), compression="zstd")
                    count = con.execute("SELECT count(*) FROM normalized").fetchone()[0]
                    if not count:
                        raise FAOSTATError("El archivo oficial está vacío")
                record = {**meta, "file": parquet.name, "rows": count, "retrieved": time.time()}
                part = manifest.with_suffix(f".{token}.part")
                part.write_text(json.dumps(record), encoding="utf-8")
                part.replace(manifest)
                self._ready[code] = parquet
                return parquet
            except Exception as exc:
                parquet.unlink(missing_ok=True)
                if old and (self.root / old["file"]).exists():
                    self.warnings.append(f"{code}: actualización fallida; se usa la versión {old['updated']}.")
                    self._ready[code] = self.root / old["file"]
                    return self._ready[code]
                raise FAOSTATError(f"Descarga {code} fallida: {exc}") from exc
            finally:
                archive.unlink(missing_ok=True)
                csv.unlink(missing_ok=True)

    def cached_metadata(self, code):
        self.ensure(code)
        return json.loads((self.root / f"{code}.json").read_text(encoding="utf-8"))

    def con(self, code="QCL"):
        con = duckdb.connect(config={"threads": 2})
        try:
            con.read_parquet(str(self.ensure(code))).create_view("fao")
            return con
        except Exception:
            con.close()
            raise

    @staticmethod
    def filters(areas=None, items=None, elements=None, years=None):
        clauses, params = [], []
        for col, values in (("Area", areas), ("Item", items), ("Element", elements)):
            if values is not None:
                if not len(values):
                    clauses.append("FALSE")
                else:
                    clauses.append(f'"{col}" IN ({",".join("?" for _ in values)})')
                    params.extend(values)
        if years is not None:
            clauses.append("Year BETWEEN ? AND ?")
            params.extend(years)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

    def dimensions(self, code="QCL"):
        with self.con(code) as con:
            result = {key: con.execute(f'SELECT DISTINCT "{col}" FROM fao WHERE "{col}" IS NOT NULL ORDER BY 1').df()[col].tolist()
                      for key, col in (("areas", "Area"), ("items", "Item"), ("elements", "Element"))}
            lo, hi = con.execute("SELECT min(Year), max(Year) FROM fao").fetchone()
            return {**result, "min_year": lo, "max_year": hi}

    def available_items(self, code="QCL", areas=None):
        where, params = self.filters(areas=areas)
        if code == "QCL":
            where += (" AND " if where else " WHERE ") + '''Element = 'Area harvested' AND NOT contains("Item Code (CPC)", 'F')'''
        with self.con(code) as con:
            return con.execute(f"SELECT DISTINCT Item FROM fao{where} ORDER BY Item", params).df().Item.dropna().tolist()

    def area_table(self, code="QCL"):
        with self.con(code) as con:
            return con.execute('SELECT DISTINCT Area, "Area Code (M49)" FROM fao').df()

    def available_years(self, code="QCL", areas=None, items=None, elements=None):
        where, params = self.filters(areas, items, elements)
        with self.con(code) as con:
            return con.execute(f"SELECT DISTINCT Year FROM fao{where} ORDER BY Year", params).df().Year.dropna().astype(int).tolist()

    def query(self, code="QCL", areas=None, items=None, elements=None, years=None):
        where, params = self.filters(areas, items, elements, years)
        if code == "PP":
            where += (" AND " if where else " WHERE ") + "Months = 'Annual value'"
        with self.con(code) as con:
            return con.execute(f"SELECT * FROM fao{where} ORDER BY Area, Item, Element, Year", params).df()
