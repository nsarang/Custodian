"""
This module provides utility classes for managing transactions, assets, and holdings.

Classes
-------
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
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import List, Tuple

import pandas as pd
from sortedcontainers import SortedDict

from custodium.utils import isclose


@dataclass
class Transaction:
    date: str
    description: str
    base_currency: str
    quote_currency: str
    quantity: Decimal
    price: Decimal
    fees: Decimal = Decimal("0")
    quote_to_reporting_rate: Decimal = None
    note: str = ""

    def __post_init__(self):
        if self.base_currency == self.quote_currency:
            raise ValueError("Base and quote currencies cannot be the same")

    @property
    def action(self) -> str:
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
    def cost(self) -> Decimal:
        """
        Calculates the total cost of the transaction including fees.

        Returns
        -------
        Decimal
            The total cost of the transaction.
        """
        return self.quantity * self.price + self.fees

    @property
    def reporting_cost(self) -> Decimal:
        """
        Calculates the total cost of the transaction in the reporting currency.

        Returns
        -------
        Decimal
            The total cost in the reporting currency.
        """

        if self.quote_to_reporting_rate is None:
            raise ValueError("No quote to reporting rate set")
        return self.cost * self.quote_to_reporting_rate

    def with_effective_price(self) -> "Transaction":
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
        instance.fees = Decimal("0")
        return instance

    def flip(self) -> "Transaction":
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
            price=Decimal("1") / self.price,
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
    quantity : Decimal, default=0
        The total quantity of the asset held in the portfolio. Positive values indicate
        ownership, whereas negative values can represent short positions.
    acb : Decimal, default=0
        The per-unit Adjusted Cost Base (ACB) of the asset, representing the average cost
        per unit of acquisition adjusted for any sales, dividends, or other capital adjustments.
    """

    date: str
    asset: str
    quantity: Decimal = Decimal("0")
    acb: Decimal = Decimal("0")


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
    def records(self) -> List[Asset]:
        """
        Provides a list of all asset records.
        """
        return self.historical.values()

    @property
    def df(self) -> pd.DataFrame:
        """
        Generates a DataFrame from historical asset records.
        """
        if len(self.historical) == 0:
            return pd.DataFrame(columns=Asset.__annotations__.keys())
        return pd.json_normalize([asdict(trx) for trx in self.records]).drop_duplicates(
            subset=["asset", "date"], keep="last"
        )

    @property
    def current(self) -> pd.DataFrame:
        """
        Generates a DataFrame of the most recent record for each asset,
        representing the current portfolio composition and cost basis.
        """
        return self.df.sort_values("date").drop_duplicates(subset="asset", keep="last")

    def add(self, asset: Asset, overwrite: bool = False) -> "Holdings":
        """
        Adds a new asset record to the holdings.

        Parameters
        ----------
        asset : Asset
            The asset record to add.
        overwrite : bool, optional
            Whether to overwrite an existing record with the same key. Defaults to False.

        Returns
        -------
        Holdings
            Self reference for method chaining.
        """
        key = self._key(asset)
        if key in self.historical.keys() and not overwrite:
            raise ValueError("Asset already exists")
        self.historical[key] = asset
        return self

    def update(self, asset: Asset) -> "Holdings":
        """
        Updates an existing asset record or adds a new one if it doesn't exist.

        Parameters
        ----------
        asset : Asset
            The asset record to update or add.
        """
        return self.add(asset, overwrite=True)

    def get(self, asset: str, date: str = None, auto_create: bool = False) -> Asset:
        """
        Retrieves the most recent record for an asset up to a specific date.

        Parameters
        ----------
        asset : str
            The asset code.
        date : str, optional
            The date up to which to retrieve the record. If not provided, the most recent
            record is returned.
        auto_create : bool, optional
            Whether to create a new asset record if none is found. Defaults to False.

        Returns
        -------
        Asset
            The most recent asset record up to the specified date, or a new asset record
            if `auto_create` is True. Otherwise, returns None.
        """
        for key in reversed(self.historical.keys()):
            if key[1] == asset and (date is None or key[0] <= date):
                return copy.deepcopy(self.historical[key])
        if auto_create:
            return Asset(date, asset)

    def _key(self, asset: Asset) -> Tuple[str, str]:
        """
        Generates a key for an asset based on its date and asset code. Used to store
        assets in the historical dictionary.
        """
        return (asset.date, asset.asset)

    def _validate_asset(self, asset: Asset):
        """
        Validates the asset record to ensure it meets certain criteria.

        Parameters
        ----------
        asset : Asset
            The asset record to validate.
        """
        if asset.quantity < 0 and not isclose(asset.quantity, 0):
            raise ValueError(f"Quantity cannot be negative. Asset: {asset}")
