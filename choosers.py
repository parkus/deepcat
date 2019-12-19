"""For consistency, function in this module should always return a list of measurements (even if narrowed down to one) or an empty list."""
from warnings import warn


def default(measurements):
    if len(measurements) == 0:
        return []

    msmts = nonlimits(measurements)
    if len(msmts) == 1:
        return msmts[0]

    if len(msmts) == 0:
        msmts = highest_quality(measurements)
        if len(msmts) == 1:
            return msmts[0]

        msmts = strictest_limit(measurements)
        if len(msmts) == 1:
            return msmts[0]

    if len(msmts) > 1:
        msmts = highest_quality(measurements)
        if len(msmts) == 1:
            return msmts[0]

        msmts = most_precise(measurements)

        if len(msmts) > 1:
            warn('Multiple measurements have the same quality and precision. Picking one arbitrarily.')
        return msmts[0]


def nonlimits(measurements):
    return [m for m in measurements if m.limit == '=']


def highest_quality(measurements):
    msmts = [m for m in measurements if m.quality is not None]
    if len(msmts) == 0:
        return measurements
    quals = [m.quality for m in msmts]
    maxq = max(quals)
    return [m for m in msmts if m.quality == maxq]


def most_precise(measurements):
    errors = [m.simple_error for m in measurements]
    if all(e is None for e in errors):
        return measurements

    values = [m.value for m in measurements]
    precisions = [e/v for e, v in zip(errors, values)]
    min_precision = min(precisions)
    keep = [p == min_precision for p in precisions]
    return [m for m, k in zip(measurements, keep) if k]


def strictest_limit(measurements):
    limits = [m.limit for m in measurements]
    values = [m.value for m in measurements]

    n_lolims = sum(l == '>' for l in limits)
    if n_lolims == len(measurements):
        max_limit = max(values)
        return [m for m in measurements if m.value == max_limit]

    n_uplims = sum(l == '<' for l in limits)
    if n_uplims == len(measurements):
        min_limit = min(values)
        return [m for m in measurements if m.value == min_limit]

    raise NotImplementedError("Can't handle a property that has upper limits and lower limits, but no actual measurements.")
