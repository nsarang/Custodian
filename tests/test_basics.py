from decimal import Decimal

import pytest

from custodium.portfolio import Asset, Holdings, Transaction
from custodium.processing import process_transaction, process_transactions
from custodium.reporting import calculate_yearly_gains


class TestTransaction:
    def test_transaction_creation(self):
        """Test basic Transaction creation and properties."""
        trx = Transaction(
            date="2023-01-15",
            description="Buy AAPL",
            base_currency="AAPL",
            quote_currency="USD",
            quantity=Decimal("10"),
            price=Decimal("150.25"),
            fees=Decimal("9.95"),
        )

        assert trx.action == "BUY"
        assert trx.cost == Decimal("10") * Decimal("150.25") + Decimal("9.95")

    def test_transaction_flip(self):
        """Test the transaction flip method."""
        trx = Transaction(
            date="2023-01-15",
            description="Sell AAPL",
            base_currency="AAPL",
            quote_currency="USD",
            quantity=Decimal("-5"),
            price=Decimal("150.25"),
            fees=Decimal("9.95"),
            quote_to_reporting_rate=Decimal("1.25"),
        )

        flipped = trx.flip()
        assert flipped.base_currency == "USD"
        assert flipped.quote_currency == "AAPL"
        # For negative quantity, the flip makes it positive (double negative)
        assert flipped.quantity == -(Decimal("-5") * Decimal("150.25"))
        assert flipped.price == Decimal("1") / Decimal("150.25")

    def test_with_effective_price(self):
        """Test converting fees into effective price."""
        trx = Transaction(
            date="2023-01-15",
            description="Buy AAPL",
            base_currency="AAPL",
            quote_currency="USD",
            quantity=Decimal("10"),
            price=Decimal("150.25"),
            fees=Decimal("9.95"),
        )

        effective = trx.with_effective_price()
        assert effective.fees == Decimal("0")
        assert effective.price > Decimal("150.25")  # Price should increase to include fees
        assert effective.cost == trx.cost  # Total cost should remain the same


class TestAsset:
    def test_asset_creation(self):
        """Test basic Asset creation."""
        asset = Asset(
            date="2023-01-15", asset="AAPL", quantity=Decimal("10"), acb=Decimal("155.25")
        )

        assert asset.asset == "AAPL"
        assert asset.quantity == Decimal("10")
        assert asset.acb == Decimal("155.25")


class TestHoldings:
    def test_holdings_add_get(self):
        """Test adding assets to holdings and retrieving them."""
        holdings = Holdings()

        asset1 = Asset(date="2023-01-15", asset="AAPL", quantity=Decimal("10"), acb=Decimal("150"))
        asset2 = Asset(date="2023-02-15", asset="MSFT", quantity=Decimal("5"), acb=Decimal("200"))

        holdings.add(asset1)
        holdings.add(asset2)

        # Test retrieval
        retrieved = holdings.get("AAPL")
        assert retrieved.asset == "AAPL"
        assert retrieved.quantity == Decimal("10")

        # Test historical retrieval
        holdings.add(
            Asset(date="2023-03-01", asset="AAPL", quantity=Decimal("15"), acb=Decimal("155"))
        )
        historical = holdings.get("AAPL", date="2023-02-01")
        assert historical.date == "2023-01-15"
        assert historical.quantity == Decimal("10")

    def test_holdings_current(self):
        """Test the current property returns the latest holdings."""
        holdings = Holdings()

        holdings.add(
            Asset(date="2023-01-15", asset="AAPL", quantity=Decimal("10"), acb=Decimal("150"))
        )
        holdings.add(
            Asset(date="2023-02-15", asset="AAPL", quantity=Decimal("15"), acb=Decimal("155"))
        )

        current = holdings.current
        assert len(current) == 1
        assert current.iloc[0]["asset"] == "AAPL"
        assert current.iloc[0]["quantity"] == Decimal("15")


class TestProcessing:
    @pytest.fixture
    def sample_holdings(self):
        """Create a sample holdings with initial USD and CAD."""
        holdings = Holdings()
        holdings.add(
            Asset(date="2023-01-01", asset="USD", quantity=Decimal("10000"), acb=Decimal("1"))
        )
        holdings.add(
            Asset(date="2023-01-01", asset="CAD", quantity=Decimal("10000"), acb=Decimal("1"))
        )
        return holdings

    @pytest.fixture
    def exchange(self):
        """Create a mock exchange rates provider."""

        class MockExchange:
            def get_rate(self, base, quote, date):
                if base == "USD" and quote == "CAD":
                    return Decimal("1.25")
                return Decimal("1")

        return MockExchange()

    def test_process_transaction(self, sample_holdings, exchange):
        """Test processing a single transaction."""
        trx = Transaction(
            date="2023-01-15",
            description="Buy AAPL",
            base_currency="AAPL",
            quote_currency="USD",
            quantity=Decimal("10"),
            price=Decimal("150"),
            fees=Decimal("0"),
        )

        gain = process_transaction(
            trx=trx, holdings=sample_holdings, exchange=exchange, reporting_currency="CAD"
        )

        # Check holdings were updated
        apple_holding = sample_holdings.get("AAPL")
        assert apple_holding.quantity == Decimal("10")

        # Check USD was deducted
        usd_holding = sample_holdings.get("USD")
        assert usd_holding.quantity == Decimal("10000") - (Decimal("10") * Decimal("150"))

        # Should be no capital gain for a buy
        assert gain is None

    def test_process_transactions(self, exchange):
        """Test processing multiple transactions."""
        # Create holdings with initial balances
        holdings = Holdings()
        holdings.add(
            Asset(date="2023-01-01", asset="CAD", quantity=Decimal("10000"), acb=Decimal("1"))
        )

        transactions = [
            # Funding transaction to USD
            Transaction(
                date="2023-01-10",
                description="Deposit USD",
                base_currency="USD",
                quote_currency="CAD",
                quantity=Decimal("10000"),
                price=Decimal("0.8"),
                fees=Decimal("0"),
                quote_to_reporting_rate=Decimal("1"),
            ),
            # Buy AAPL with USD
            Transaction(
                date="2023-01-15",
                description="Buy AAPL",
                base_currency="AAPL",
                quote_currency="USD",
                quantity=Decimal("10"),
                price=Decimal("150"),
                fees=Decimal("0"),
            ),
            # Sell AAPL for USD
            Transaction(
                date="2023-02-15",
                description="Sell AAPL",
                base_currency="AAPL",
                quote_currency="USD",
                quantity=Decimal("-5"),
                price=Decimal("160"),
                fees=Decimal("0"),
            ),
            # Critical: Sell USD directly to CAD (this creates a capital gain in reporting currency)
            Transaction(
                date="2023-03-15",
                description="Sell USD to CAD",
                base_currency="CAD",
                quote_currency="USD",
                quantity=Decimal("1000"),
                price=Decimal("0.75"),
                fees=Decimal("0"),
            ),
        ]

        holdings, gains = process_transactions(
            transactions=transactions,
            holdings=holdings,
            exchange=exchange,
            reporting_currency="CAD",
        )

        # Check final holdings
        aapl_holding = holdings.get("AAPL")
        assert aapl_holding.quantity == Decimal("5")

        # Verify that we captured at least one capital gain
        assert len(gains) >= 1

        # Specifically, the USD to CAD transaction should create a gain
        cad_gain = [g for g in gains if g["Date"] == "2023-03-15"]
        assert len(cad_gain) == 1

        # Check final holdings
        aapl_holding = holdings.get("AAPL")
        assert aapl_holding.quantity == Decimal("5")

        # Check gains were recorded
        assert len(gains) == 1
        assert gains[0]["Date"] == "2023-03-15"
        assert gains[0]["Capital Gain"] > 0  # Should be positive gain


class TestReporting:
    def test_calculate_yearly_gains(self):
        """Test calculating yearly gains summary."""
        gains = [
            {
                "Date": "2023-01-15",
                "Capital Gain": Decimal("100"),
                "Cost Base": Decimal("900"),
                "Gross Proceeds": Decimal("1000"),
            },
            {
                "Date": "2023-06-30",
                "Capital Gain": Decimal("200"),
                "Cost Base": Decimal("800"),
                "Gross Proceeds": Decimal("1000"),
            },
            {
                "Date": "2024-03-15",
                "Capital Gain": Decimal("150"),
                "Cost Base": Decimal("850"),
                "Gross Proceeds": Decimal("1000"),
            },
        ]

        yearly = calculate_yearly_gains(gains)

        assert len(yearly) == 2  # Two years: 2023 and 2024
        assert yearly.iloc[0]["Year"] == 2023
        assert yearly.iloc[0]["Capital Gain"] == Decimal("300")  # Sum of 2023 gains
        assert yearly.iloc[1]["Year"] == 2024
        assert yearly.iloc[1]["Capital Gain"] == Decimal("150")  # 2024 gain
