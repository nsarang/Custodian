"""
This module provides utility classes for managing foreign exchange rates, transactions, 
assets, and holdings.

Classes
-------
BankofCanadaRates:
    A class to fetch and manage foreign exchange rates from the Bank of Canada.

Transaction:
    Represents a financial transaction, including details such as date, description,
    currencies, quantity, price, fees, and more.

Asset:
    Represents an asset within a portfolio, tracking its per-unit adjusted cost basis (ACB)
    and the quantity held.

Holdings:
    Manages a collection of assets and their historical records.
"""

import copy
import io
from dataclasses import asdict, dataclass
from functools import cached_property

import pandas as pd
import requests
from sortedcontainers import SortedDict


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
        rates = (
            pd.read_csv(io.StringIO(rates_str)).sort_values("date").set_index("date")
        )
        rates.index = pd.to_datetime(rates.index)
        all_days = pd.date_range(rates.index.min(), rates.index.max(), freq="D")
        rates = rates.reindex(all_days).ffill()
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
        float
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
            return 1
        return self.rates.loc[date, f"FX{base_currency}CAD"]

    @cached_property
    def currencies(self):
        """
        Returns a set of all currencies available in the fetched rates.
        """
        return set(sum(map(lambda col: [col[2:5], col[5:8]], self.rates.columns), []))


@dataclass
class Transaction:
    date: str
    description: str
    base_currency: str
    quote_currency: str
    quantity: float
    price: float
    fees: float = 0
    quote_to_reporting_rate: float = None
    note: str = ""

    @property
    def action(self):
        """
        Determines if the transaction is a "BUY" or "SELL" based on the quantity attribute.

        Returns
        -------
        str
            "BUY" if the quantity is positive, "SELL" otherwise.
        """
        if self.quantity > 0:
            return "BUY"
        return "SELL"

    @property
    def cost(self):
        """
        Calculates the total cost of the transaction including fees.

        Returns
        -------
        float
            The total cost of the transaction.
        """
        return self.quantity * self.price + self.fees

    @property
    def reporting_cost(self):
        """
        Calculates the total cost of the transaction in the reporting currency.

        Returns
        -------
        float
            The total cost in the reporting currency.
        """

        if self.quote_to_reporting_rate is None:
            raise ValueError("No quote to reporting rate set")
        return self.cost * self.quote_to_reporting_rate

    def with_effective_price(self):
        """
        Adjusts the transaction to reflect fees in the price, returning a modified
        copy of the transaction.

        Returns
        -------
        Transaction
            A new Transaction instance with adjusted price and zero fees.
        """
        instance = copy.deepcopy(self)
        instance.price = self.cost / self.quantity
        instance.fees = 0
        return instance

    def flip(self):
        """
        Flips the transaction, swapping the roles of the base and quote currencies,
        inverting the quantity according to the price, adjusting the price to
        represent the inverse of the original transaction rate, and recalculating fees
        based on the new price. This method is useful for converting a buy action into
        its equivalent sell action, or vice versa, from the perspective of currency exchange.

        Raises
        ------
        ValueError
            If the quote to reporting rate is not set prior to flipping.

        Returns
        -------
        Transaction
            A new Transaction instance representing the flipped transaction,
            with inverted base and quote currencies, quantity, and appropriately
            adjusted price and fees.
        """
        if self.quote_to_reporting_rate is None:
            raise ValueError("quote to reporting rate is not set")
        return Transaction(
            date=self.date,
            description=self.description,
            base_currency=self.quote_currency,
            quote_currency=self.base_currency,
            quantity=-(self.quantity * self.price),
            price=1 / self.price,
            fees=self.fees / self.price,
            quote_to_reporting_rate=self.quote_to_reporting_rate * self.price,
        )


@dataclass
class Asset:
    """
    Represents an asset within a portfolio, tracking its per-unit adjusted cost basis (ACB)
    and the quantity held as of a certain date.

    Attributes
    ----------
    date : str
        The date of the last transaction or valuation update for the asset.
    asset : str
        The identifier or code for the asset, such as a stock ticker.
    quantity : float, default=0
        The total quantity of the asset held in the portfolio. Positive values indicate
        ownership, whereas negative values can represent short positions.
    acb : float, default=0
        The per-unit Adjusted Cost Base (ACB) of the asset, representing the average cost
        per unit of acquisition adjusted for any sales, dividends, or other capital adjustments.
    """

    date: str
    asset: str
    quantity: float = 0
    acb: float = 0


class Holdings:
    """
    Manages a collection of assets and their historical records.

    Attributes
    ---------
    records : list
        A list of all asset records.
    df : DataFrame
        A DataFrame of historical asset records.
    current : DataFrame
        A DataFrame of the most recent record for each asset.
    """

    def __init__(self) -> None:
        self.historical = SortedDict()

    @property
    def records(self):
        """
        Provides a list of all asset records.
        """
        return self.historical.values()

    @property
    def df(self):
        """
        Generates a DataFrame from historical asset records.
        """
        if len(self.historical) == 0:
            return pd.DataFrame(columns=Asset.__annotations__.keys())
        return pd.json_normalize([asdict(trx) for trx in self.records]).drop_duplicates(
            subset=["asset", "date"], keep="last"
        )

    @property
    def current(self):
        """
        Generates a DataFrame of the most recent record for each asset.
        """
        return self.df.sort_values("date").drop_duplicates(subset="asset", keep="last")

    def add(self, asset: Asset, overwrite: bool = False):
        """
        Adds a new asset record to the holdings.

        Parameters
        ----------
        asset : Asset
            The asset record to add.
        overwrite : bool, optional
            Whether to overwrite an existing record with the same key. Defaults to False.
        """
        key = self._key(asset)
        if key in self.historical.keys() and not overwrite:
            raise ValueError("Asset already exists")
        self.historical[key] = asset

    def get(self, asset: str, date: str = None):
        """
        Retrieves the most recent record for an asset up to a specific date.

        Parameters
        ----------
        asset : str
            The asset code.
        date : str, optional
            The date up to which to retrieve the record. If not provided, the most recent
            record is returned.

        Returns
        -------
        Asset
            An Asset instance representing the retrieved record. If no record is found, a
            new Asset instance with the provided asset code and date is returned.
        """
        for key in reversed(self.historical.keys()):
            if key[1] == asset and (date is None or key[0] <= date):
                return copy.deepcopy(self.historical[key])
        return Asset(date, asset)

    def _key(self, asset: Asset):
        """
        Generates a key for an asset based on its date and asset code. Used to store
        assets in the historical dictionary.
        """
        return (asset.date, asset.asset)
