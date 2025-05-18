import pandas as pd

from custodium.portfolio import Holdings


def calculate_yearly_gains(capgains):
    """
    Calculate capital gains by year from a list of capital gains records.

    Parameters
    ----------
    capgains : list
        List of capital gains records returned by `process_transactions()`

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


def plot_holdings_history(
    holdings: Holdings,
    show_plot: bool = False,
    quantity_title: str = "Quantity",
    acb_title: str = "ACB",
    date_title: str = "Date",
    height: int = 600,
    width: int = 900,
    title: str = "Portfolio Holdings History",
):
    """
    Generate an interactive plot showing the history of holdings quantities and ACB.

    Creates a dual-axis plot with quantity on the primary y-axis and ACB on the
    secondary y-axis, both plotted over time.

    Parameters
    ----------
    holdings : Holdings
        The Holdings object containing historical data to plot
    show_plot : bool, optional
        Whether to display the plot immediately, defaults to True
    quantity_title : str, optional
        Title for the primary y-axis, defaults to "Quantity"
    acb_title : str, optional
        Title for the secondary y-axis, defaults to "ACB (CAD)"
    date_title : str, optional
        Title for the x-axis, defaults to "Date"
    height : int, optional
        Plot height in pixels, defaults to 600
    width : int, optional
        Plot width in pixels, defaults to 900
    title : str, optional
        Title for the plot

    Returns
    -------
    plotly.graph_objects.Figure
        The generated figure object for further customization or saving

    Examples
    --------
    >>> fig = plot_holdings_history(holdings)
    >>> # Save to file instead of displaying
    >>> fig.write_html("holdings_history.html")
    >>> # Customize further
    >>> fig.update_layout(title="My Portfolio History")
    """
    import plotly.express as px
    from plotly.subplots import make_subplots

    if len(holdings.df) == 0:
        raise ValueError("Holdings contain no data to plot")

    # Create quantity plot
    fig_quantity = px.line(holdings.df, x="date", y="quantity", color="asset", markers=True)

    # Create ACB plot
    fig_acb = px.line(holdings.df, x="date", y="acb", color="asset")

    # Update ACB traces to use secondary y-axis and dashed lines
    fig_acb.update_traces(yaxis="y2", line=dict(dash="dashdot"))

    # Combine into a single figure with dual y-axes
    subfig = make_subplots(specs=[[{"secondary_y": True}]])
    subfig.add_traces(fig_quantity.data + fig_acb.data)

    subfig.layout.xaxis.title = date_title
    subfig.layout.yaxis.title = f"{quantity_title} (solid lines)"
    subfig.layout.yaxis2.title = f"{acb_title} (dashed lines)"

    subfig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center", font=dict(weight="bold", size=18)),
        legend=dict(x=1.05, xanchor="left", y=0.5, yanchor="middle"),
    )

    subfig.update_layout(height=height, width=width)

    if show_plot:
        subfig.show()

    return subfig
