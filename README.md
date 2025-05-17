# Custodium

<div align="center">

<img alt="Custodium" src="logo.jpg" width="500px" style="max-width: 100%;">
<br/>
<br/>

[![PyPI](https://img.shields.io/pypi/v/custodium?logoSize=auto)](https://pypi.org/project/custodium/)
[![Python Versions](https://img.shields.io/pypi/pyversions/custodium?logoSize=auto)](https://pypi.org/project/custodium/)
![License](https://img.shields.io/pypi/l/custodium?logo=auto)

</div>


Custodium is a Python package for tracking investment portfolios and calculating adjusted cost basis (ACB) for Canadian capital gain/loss calculations. Primarily designed for educational purposes.

## Key Features

- Track investment transactions across multiple currencies with automatic exchange rate handling
- Calculate and maintain adjusted cost basis (ACB) over time
- Process special transaction types (e.g., equity vesting)
- Generate capital gains reports for tax purposes

## Installation
```
pip install custodium
```

## Usage

### Processing Transactions

Create a CSV file with these columns:
```csv
date,description,base_currency,quote_currency,quantity,price,fees,note
2023-01-15,Buy AAPL shares,AAPL,USD,10,150.25,9.95,Initial purchase
2023-06-30,Sell AAPL shares,AAPL,USD,-5,175.50,9.95,Partial sale
2023-07-15,Vest RSUs,GOOG,USD,3,135.75,0,Employee compensation
```
Then load and process:

```python
from custodium.processing import load_transactions, process_transactions
from custodium.reporting import calculate_yearly_gains
from custodium.utils import displayPandas

# Load transactions from CSV
transactions, df_log = load_transactions("my_transactions.csv")

# Process the transactions
holdings, gains = process_transactions(transactions)

# View current holdings with readable formatting
displayPandas(holdings.current, precision=2)

# Calculate and display the yearly gains/losses
calculate_yearly_gains(gains)
```

## Disclaimer
This package is provided for educational purposes only. Users should not rely on this software for financial advice, tax reporting, or investment decisions without independent verification. The authors accept no responsibility for any financial losses, tax implications, or other issues that may arise from the use of this software.
