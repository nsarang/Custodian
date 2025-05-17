from decimal import Decimal


def isclose(a, b, rel_tol=Decimal("1e-9"), abs_tol=Decimal("0")):
    """
    Determines if two Decimal values are approximately equal.

    Similar to np.isclose() but works with Decimal objects.

    Parameters
    ----------
    a : Decimal
        First value
    b : Decimal
        Second value
    rel_tol : Decimal, optional
        Relative tolerance
    abs_tol : Decimal, optional
        Absolute tolerance

    Returns
    -------
    bool
        True if values are approximately equal
    """
    a, b = Decimal(a), Decimal(b)
    if a == b:
        return True
    diff = abs(a - b)
    return diff <= abs_tol or diff <= rel_tol * max(abs(a), abs(b))


def displayPandas(df, precision=10, text=False):
    df = df.copy()
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, Decimal)).any():
            df[col] = df[col].apply(lambda x: f"{x:.{precision}g}" if isinstance(x, Decimal) else x)

    if text:
        return df.to_markdown()
    else:
        from IPython.display import HTML, display

        display(HTML(df.to_html()))
