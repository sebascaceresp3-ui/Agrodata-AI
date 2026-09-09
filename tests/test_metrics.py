from utils.metrics import annual_change, cagr, safe_div
def test_annual_change(): assert annual_change(110,100)==10
def test_zero(): assert annual_change(1,0) is None
def test_cagr(): assert round(cagr(100,121,2),6)==10
def test_share(): assert safe_div(25,100)==.25
