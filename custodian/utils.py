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
