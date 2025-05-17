"""
Functions for processing transactions and analyzing portfolios.
"""

import datetime as dt
import json
from dataclasses import asdict
from decimal import Decimal
from typing import List, Tuple

import pandas as pd

from custodium.exchange import BankofCanadaRates
from custodium.portfolio import Asset, Holdings, Transaction
from custodium.utils import isclose


def process_transaction(
    trx: Transaction,
    holdings: Holdings,
    exchange: BankofCanadaRates,
    reporting_currency: str = "CAD",
):
    """
    Process a single transaction, updating holdings and recording capital gains.

    Parameters
    ----------
    trx : Transaction
        The transaction to process
    holdings : Holdings
        The holdings object to update
    exchange : BankofCanadaRates
        Exchange rate provider
    reporting_currency : str, optional
        The currency to report in, defaults to "CAD"

    Returns
    -------
    dict or None
        Dictionary containing capital gain information if a taxable event occurred,
        or None if no taxable event. Updates holdings in place.
    """
    # Incorporate transaction fees into the price to simplify calculations
    trx = trx.with_effective_price()

    # Determine the quote_to_reporting_rate
    if trx.quote_to_reporting_rate is None:
        if trx.quote_currency == reporting_currency:
            trx.quote_to_reporting_rate = Decimal("1")
        else:
            try:
                trx.quote_to_reporting_rate = exchange.get_rate(
                    trx.quote_currency, reporting_currency, trx.date
                )
            except Exception as e:
                raise Exception(
                    f"Error getting rate for {trx.date} {trx.quote_currency} to {reporting_currency}: {e!s}"
                )

    # Flip the transaction if it is a sell order
    if trx.quantity < 0:
        trx = trx.flip()

    # Create a synthetic funding transaction to represent employer-provided equity compensation
    if "Vest" in trx.description:
        # Artificial funding transaction
        funding_trx = Transaction(
            date=trx.date,
            description=trx.description.replace("Vest", "Funding"),
            base_currency=trx.quote_currency,
            quote_currency=reporting_currency,
            quantity=trx.cost,
            price=trx.quote_to_reporting_rate,
            fees=Decimal("0"),
            quote_to_reporting_rate=Decimal("1"),
        )
        # Update the cash balance in the reporting currency to reflect the vested compensation
        reporting_holding = holdings.get(reporting_currency, trx.date)
        reporting_holding.quantity += funding_trx.cost
        holdings.update(reporting_holding)

        process_transaction(
            trx=funding_trx,
            holdings=holdings,
            exchange=exchange,
            reporting_currency=reporting_currency,
        )

    # Get the current holdings
    base_holding = holdings.get(trx.base_currency, trx.date, auto_create=True)
    quote_holding = holdings.get(trx.quote_currency, trx.date, auto_create=True)

    # Update the ACB and quantity for the base currency
    if trx.base_currency != reporting_currency:
        base_holding.acb = (
            base_holding.quantity * base_holding.acb + trx.cost * quote_holding.acb
        ) / (base_holding.quantity + trx.quantity)
    base_holding.quantity += trx.quantity
    base_holding.date = trx.date

    # Calculate gain/loss of a disposition event
    if trx.base_currency == reporting_currency:
        cost_base = quote_holding.acb * trx.cost
        gross_proceeds = trx.quantity
        capital_gain = gross_proceeds - cost_base
        gain = {
            "Date": trx.date,
            "Cost Base": cost_base,
            "Gross Proceeds": gross_proceeds,
            "Capital Gain": capital_gain,
        }
    else:
        gain = None

    # Update the quantity for the quote currency
    if (quote_holding.quantity < trx.cost) and (not isclose(quote_holding.quantity, trx.cost)):
        raise Exception(
            f"Insufficient funds to complete transaction on {trx.date}.\n"
            f" - Cost: {trx.cost} {trx.quote_currency}\n"
            f" - Current holdings: {quote_holding.quantity} {trx.quote_currency}\n"
            "Details:\n"
            f"Transaction: {json.dumps(asdict(trx), default=str, indent=4)}\n"
            f"Current holdings:\n"
            f"{holdings.current}\n"
        )
    quote_holding.quantity -= trx.cost
    quote_holding.date = trx.date

    holdings.update(base_holding)
    holdings.update(quote_holding)

    return gain


def process_transactions(
    transactions: List[Transaction],
    holdings: Holdings = None,
    exchange: BankofCanadaRates = None,
    reporting_currency: str = "CAD",
):
    """
    Process a list of transactions and return holdings and capital gains.

    Parameters
    ----------
    transactions : list of Transaction
        Transactions to process in chronological order
    initial_balance : Decimal or int, optional
        Initial cash balance, defaults to 50000
    reporting_currency : str, optional
        Currency for reporting, defaults to "CAD"

    Returns
    -------
    tuple
        (holdings, capgains) - The updated holdings and capital gains list
    """
    gains = []

    if len(transactions) == 0:
        return holdings, gains

    # Sort transactions by date
    transactions = sorted(transactions, key=lambda x: x.date)
    min_date = transactions[0].date

    if holdings is None:
        holdings = Holdings()

    if exchange is None:
        start_date = (dt.datetime.fromisoformat(min_date) - dt.timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        exchange = BankofCanadaRates(start_date=start_date)

    if holdings.get(reporting_currency) is None:
        holdings.add(
            Asset(
                asset=reporting_currency,
                date=min_date,
                acb=Decimal("1"),
            )
        )

    # Process each transaction
    for trx in transactions:
        result = process_transaction(
            trx, holdings=holdings, exchange=exchange, reporting_currency=reporting_currency
        )
        if result is not None:
            gains.append(result)

    return holdings, gains


def load_transactions(file_path) -> Tuple[List[Transaction], pd.DataFrame]:
    """
    Load transactions from a CSV file.

    Parameters
    ----------
    file_path : str
        Path to the CSV file

    Returns
    -------
    DataFrame
        DataFrame containing the loaded transactions
    """
    decimal_columns = ["quantity", "price", "fees"]
    # Read the data as strings to avoid rounding issues
    trxs_log = pd.read_csv(file_path, dtype=str)
    trxs_log.columns = [col.lower().replace(" ", "_") for col in trxs_log.columns]
    trxs_log.index.name = "id"
    # Fill in missing values
    trxs_log = trxs_log.sort_values(["date", "id"]).fillna(
        {"description": "", "fees": 0, "note": ""}
    )
    # Convert numeric columns to Decimal
    for col in decimal_columns:
        trxs_log[col] = trxs_log[col].apply(
            lambda x: Decimal(x.replace(",", "")) if x else Decimal(0)
        )

    assert trxs_log.isnull().sum().sum() == 0, "Missing values found."
    trxs = trxs_log.apply(lambda r: Transaction(**r), axis=1).tolist()
    return trxs, trxs_log
