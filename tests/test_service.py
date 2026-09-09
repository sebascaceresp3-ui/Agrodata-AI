"""Offline transport/cache tests. Synthetic CSVs never enter the app's cache."""
import json
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
import requests
from services.bulk import FAOSTATService, FAOSTATError


@pytest.fixture
def cache():
    path = Path(tempfile.mkdtemp(prefix='agrodata-test-'))
    yield path
    shutil.rmtree(path)


def archive(value='12'):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('test_Normalized.csv', 'Area,Item,Element,Year,Unit,Value\nTest,Test,Production,2024,t,' + value + '\n')
    return buffer.getvalue()


class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def raise_for_status(self):
        pass
    def iter_content(self, size):
        yield self.data
    def json(self):
        return json.loads(self.data)


def setup_service(cache, monkeypatch, version='2024'):
    service = FAOSTATService(cache)
    monkeypatch.setattr(service, 'metadata', lambda code: {'code':code,'name':'test','updated':version,'url':'https://bulks-faostat.fao.org/test.zip'})
    return service


def test_atomic_cache_and_version_refresh(cache, monkeypatch):
    service = setup_service(cache, monkeypatch)
    monkeypatch.setattr(service.session, 'get', lambda *a, **k: Response(archive()))
    original = service.ensure()
    assert original.exists()
    assert service.query(items=[]).empty
    assert service.query().Value.iloc[0] == 12
    assert not list(cache.glob('*.part'))
    newer = setup_service(cache, monkeypatch, '2025')
    monkeypatch.setattr(newer.session, 'get', lambda *a, **k: Response(archive('25')))
    assert newer.ensure() != original
    assert newer.query().Value.iloc[0] == 25
    assert json.loads((cache/'QCL.json').read_text())['updated'] == '2025'


def test_failed_update_preserves_old_version(cache, monkeypatch):
    service = setup_service(cache, monkeypatch)
    monkeypatch.setattr(service.session, 'get', lambda *a, **k: Response(archive()))
    original = service.ensure()
    newer = setup_service(cache, monkeypatch, '2025')
    monkeypatch.setattr(newer.session, 'get', lambda *a, **k: Response(b'broken zip'))
    assert newer.ensure() == original
    assert newer.warnings
    assert newer.cached_metadata('QCL')['updated'] == '2024'
    assert not list(cache.glob('*.part'))


def test_invalid_values_are_not_silently_dropped(cache, monkeypatch):
    service = setup_service(cache, monkeypatch)
    monkeypatch.setattr(service.session, 'get', lambda *a, **k: Response(archive('INVALID')))
    with pytest.raises(FAOSTATError):
        service.ensure()
    assert not (cache/'QCL.json').exists()
    assert not list(cache.glob('*.parquet'))


def test_bad_catalog_does_not_overwrite_good_cache(cache, monkeypatch):
    payload = {'Datasets':{'Dataset':[{'DatasetCode':'QCL'}]}}
    path = cache/'catalog.json'
    path.write_text(json.dumps(payload))
    service = FAOSTATService(cache)
    monkeypatch.setattr(service.session, 'get', lambda *a, **k: Response(b'{}'))
    assert service.catalog(refresh=True) == payload['Datasets']['Dataset']
    assert json.loads(path.read_text()) == payload
    assert service.warnings


def test_offline_without_cache_is_explicit(cache, monkeypatch):
    service = FAOSTATService(cache)
    def offline(*a, **k):
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(service.session, 'get', offline)
    with pytest.raises(FAOSTATError, match='catálogo oficial'):
        service.catalog()


def test_corrupt_parquet_is_rebuilt(cache, monkeypatch):
    service = setup_service(cache, monkeypatch)
    monkeypatch.setattr(service.session, 'get', lambda *a, **k: Response(archive()))
    original = service.ensure()
    original.write_bytes(b'broken parquet')
    repaired = setup_service(cache, monkeypatch)
    monkeypatch.setattr(repaired.session, 'get', lambda *a, **k: Response(archive('20')))
    assert repaired.ensure() != original
    assert repaired.query().Value.iloc[0] == 20
    assert repaired.warnings
