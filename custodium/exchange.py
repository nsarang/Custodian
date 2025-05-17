import io
from decimal import Decimal
from functools import cached_property

import pandas as pd
import requests


class BankofCanadaRates:
    """
    A class to fetch and manage foreign exchange rates from the Bank of Canada.

    Parameters
    ----------
    start_date : str, optional
        The start date for the range of rates to be fetched in "YYYY-MM-DD" format.
    end_date : str, optional
        The end date for the range of rates to be fetched in "YYYY-MM-DD" format.

    Attributes
    ----------
    rates : DataFrame
        A pandas DataFrame holding the exchange rates, indexed by date.

    Methods
    -------
    get_rate(base_currency, quote_currency, date):
        Fetches the exchange rate between two currencies on a specific date.
    """

    def __init__(self, start_date=None, end_date=None):
        self.start_date = start_date
        self.end_date = end_date

        url = "https://www.bankofcanada.ca/valet/observations/group/FX_RATES_DAILY/csv?"
        if start_date is not None:
            url += "&start_date=" + start_date
        if end_date is not None:
            url += "&end_date=" + end_date

        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Error downloading data from Bank of Canada")
        data = response.text
        rates_str = data[data.find("OBSERVATIONS") + len("OBSERVATIONS") + 1 :].strip()
        rates = pd.read_csv(io.StringIO(rates_str), dtype=str).sort_values("date").set_index("date")
        rates.index = pd.to_datetime(rates.index)
        all_days = pd.date_range(rates.index.min(), rates.index.max(), freq="D")
        rates = rates.reindex(all_days).ffill()
        rates = rates.map(lambda x: Decimal(x.replace(",", "")) if x else Decimal("0"))
        self.rates = rates

    def get_rate(self, base_currency, quote_currency, date):
        """
        Fetches the exchange rate between two currencies on a specific date.

        Parameters
        ----------
        base_currency : str
            The base currency code.
        quote_currency : str
            The quote currency code.
        date : datetime-like
            The date for which to fetch the exchange rate.

        Returns
        -------
        Decimal
            The exchange rate.
        """
        for currency in [base_currency, quote_currency]:
            if currency not in self.currencies:
                raise ValueError(f"Currency {currency} not available")
        if quote_currency != "CAD":
            base_cad = self.get_rate(base_currency, "CAD", date)
            quote_cad = self.get_rate(quote_currency, "CAD", date)
            return base_cad / quote_cad
        if base_currency == "CAD":
            return Decimal("1")
        return self.rates.loc[date, f"FX{base_currency}CAD"]

    @cached_property
    def currencies(self):
        """
        Returns a set of all currencies available in the fetched rates.
        """
        return {curr for col in self.rates.columns for curr in (col[2:5], col[5:8])}
