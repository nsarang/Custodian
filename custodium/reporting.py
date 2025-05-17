import pandas as pd


def calculate_yearly_gains(capgains):
    """
    Calculate capital gains by year from a list of capital gains records.

    Parameters
    ----------
    capgains : list
        List of capital gains records

    Returns
    -------
    DataFrame
        Summary of capital gains by year
    """
    if not capgains:
        return pd.DataFrame()

    df_capgains = pd.DataFrame(capgains)
    df_capgains["Date"] = pd.to_datetime(df_capgains["Date"])

    years = range(df_capgains["Date"].dt.year.min(), df_capgains["Date"].dt.year.max() + 1)

    yearly_gains = []
    for year in years:
        yearly = df_capgains.query(f"'{year}-01-01' <= Date <= '{year}-12-31'")
        if not yearly.empty:
            yearly_sum = yearly.drop(columns="Date").sum().to_dict()
            yearly_sum["Year"] = year
            yearly_gains.append(yearly_sum)

    return pd.DataFrame(yearly_gains)
