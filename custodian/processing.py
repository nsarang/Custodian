"""
Functions for processing transactions and analyzing portfolios.
"""

import json
from dataclasses import asdict
from decimal import Decimal

from .exchange import BankofCanadaRates
from .portfolio import Holdings, Transaction
from .utils import isclose


def process_transaction(trx, holdings, exchange, reporting_currency="CAD"):
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
    None
        Updates holdings and capgains in place
    """
    # reflect fees in the price
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

    # Vesting transactions are funded by the company, so we need to add
    # a preceding funding transaction
    if "Vest" in trx.description:
        process_transaction(
            Transaction(
                date=trx.date,
                description=trx.description.replace("Vest", "Funding"),
                base_currency=trx.quote_currency,
                quote_currency=reporting_currency,
                quantity=trx.cost,
                price=trx.quote_to_reporting_rate,
                fees=Decimal("0"),
                quote_to_reporting_rate=Decimal("1"),
            ),
            holdings=holdings,
            exchange=exchange,
            reporting_currency=reporting_currency,
        )

    # Flip the transaction if it is a sell order
    if trx.quantity < 0:
        trx = trx.flip()

    # Get the current holdings
    base_holding = holdings.get(trx.base_currency, trx.date)
    quote_holding = holdings.get(trx.quote_currency, trx.date)

    # Update the ACB and quantity for the base currency
    if trx.base_currency != reporting_currency:
        base_holding.acb = (
            base_holding.quantity * base_holding.acb + trx.cost * quote_holding.acb
        ) / (base_holding.quantity + trx.quantity)
    base_holding.quantity += trx.quantity
    base_holding.date = trx.date

    # Calculate the capital gain for liquidating transactions
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

    holdings.add(base_holding, overwrite=True)
    holdings.add(quote_holding, overwrite=True)

    return gain


def process_transactions(transactions, holdings=None, exchange=None, reporting_currency="CAD"):
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
    capgains = []

    if holdings is None:
        holdings = Holdings()
    if exchange is None:
        exchange = BankofCanadaRates(start_date="2018-01-01")

    # Process each transaction
    for trx in transactions:
        process_transaction(trx, holdings, capgains, reporting_currency, exchange)

    return holdings, capgains
