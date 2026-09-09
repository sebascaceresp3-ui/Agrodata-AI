from collections.abc import Mapping
import pandas as pd
from services.cached import query

ELEMENTS = {
    'PP': ('Producer Price (USD/tonne)',),
    'TCL': ('Import quantity','Export quantity','Import value','Export value'),
}

class LazyFrames(Mapping):
    """Same mapping consumed by views. Iterating keys never loads a dataset.

    The existing CSV selector reads one domain. Excel's .items() materializes
    every selected domain only after the existing prepare button is pressed.
    """
    def __init__(self, base, service, scope, items, years, metadata, errors):
        self.loaded = {'QCL':base}
        self.service = service
        self.scope, self.items_selected, self.years = scope, items, years
        self.metadata, self.errors = metadata, errors

    def __iter__(self):
        return iter(('QCL','PP','TCL'))

    def __len__(self):
        return 3

    def __getitem__(self, code):
        if code not in ('QCL','PP','TCL'):
            raise KeyError(code)
        if code not in self.loaded:
            try:
                meta = self.service.cached_metadata(code)
                self.metadata[code] = meta
                self.loaded[code] = query(code,meta['file'],self.scope,self.items_selected,ELEMENTS[code],self.years,self.service)
            except Exception as exc:
                self.errors[code] = str(exc)
                self.loaded[code] = pd.DataFrame(columns=self.loaded['QCL'].columns)
        return self.loaded[code]
