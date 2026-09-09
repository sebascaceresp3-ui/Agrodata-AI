"""Synthetic regression fixtures used only by tests, never by the dashboard."""
import pandas as pd
from io import BytesIO
from utils.analytics import aggregate, shares_and_ranks, normalize_yields
from utils.exports import csv_bytes, excel_bytes
from services.faostat import FAOSTATService


def sample():
    return pd.DataFrame([
        ['A','Crop',2024,'Production','t',10],
        ['A','Crop',2024,'Area harvested','ha',2],
        ['A','Crop',2024,'Yield','kg/ha',5000],
        ['B','Crop',2024,'Production','t',90],
        ['B','Crop',2024,'Area harvested','ha',3],
        ['B','Crop',2024,'Yield','kg/ha',30000],
    ], columns=['Area','Item','Year','Element','Unit','Value'])


def test_weighted_yield():
    assert aggregate(sample(),'Yield',['Year']).Value.iloc[0] == 20000


def test_missing_yield_is_not_zero_or_reconstructed():
    data = sample()
    data.loc[data.Area.eq('B') & data.Element.eq('Yield'), 'Value'] = None
    assert pd.isna(aggregate(data,'Yield',['Year']).Value.iloc[0])


def test_units_and_countries():
    result = aggregate(sample(),'Production',['Area','Year'])
    assert result.Value.tolist() == [10,90]
    data = sample()
    data.loc[data.Element.eq('Yield'), 'Unit'] = 'hg/ha'
    assert normalize_yields(data).query("Element == 'Yield'").Value.tolist() == [500,3000]


def test_share_full_population_and_ties():
    result = shares_and_ranks(pd.DataFrame({'Area':['A','B','C'],'Value':[40,40,20]}))
    assert result.Ranking.tolist() == [1,1,3]
    assert result['Participación (%)'].tolist() == [40,40,20]
    assert result.head(1)['Participación (%)'].sum() == 40


def test_no_data_share():
    result = shares_and_ranks(pd.DataFrame({'Area':['A'],'Value':[0]}))
    assert result['Participación (%)'].isna().all()


def test_empty_filter_is_not_all():
    where, params = FAOSTATService.filters(items=[])
    assert 'FALSE' in where and params == []
    assert FAOSTATService.filters()[0] == ''


def test_filter_parameters():
    where, params = FAOSTATService.filters(['A','B'],['Crop'],['Yield'],(2020,2024))
    assert where.count('?') == 6 and params == ['A','B','Crop','Yield',2020,2024]


def test_exports_roundtrip():
    data = sample()
    pd.testing.assert_frame_equal(pd.read_csv(BytesIO(csv_bytes(data))), data)
    pd.testing.assert_frame_equal(pd.read_excel(BytesIO(excel_bytes({'QCL':data}))),data)


def test_export_formula_and_null():
    data = pd.DataFrame({'text':['=1+1',None],'value':[None,0]})
    result = pd.read_excel(BytesIO(excel_bytes({'data':data})))
    assert result.text.iloc[0] == "'=1+1"
    assert pd.isna(result.value.iloc[0])
