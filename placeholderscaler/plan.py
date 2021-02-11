"""
Print out a plan
"""
import argparse
import datetime
import os
import tempfile
import warnings
from unittest import mock

from dateutil.parser import parse as parse_date

from . import scaler


def check_plan(url: str = None, start=None, days: int = 7, interval: int = 1):
    """Check what a calendar will produce over time

    Simulates the check over time each `interval` hours for the given number of days.

    Results are printed to stdout.
    """

    if start is None:
        start = scaler.utcnow()

    if url is None:
        url = os.environ["PLACEHOLDER_ICS_URL"]

    if url.startswith("http"):
        try:
            import requests_cache
        except ImportError:
            warnings.warn(
                "plan will run faster with requests_cache",
                RuntimeWarning,
            )
        else:
            requests_cache.install_cache(tempfile.mkstemp()[1])

    end = start + datetime.timedelta(days=days)
    # set the env that used for config
    os.environ["PLACEHOLDER_ICS_URL"] = url

    t = start
    prev_placeholders = -1
    prev_capacity = -1
    while t < end:
        # mock scaler.utcnow to simulate moving forward in time
        with mock.patch.object(scaler, "utcnow", lambda: t):
            min_placeholders, min_capacity = scaler.get_target_capacity()
            if (min_placeholders, min_capacity) != (prev_placeholders, prev_capacity):
                # print new values if there was a change
                prev_placeholders = min_placeholders
                prev_capacity = min_capacity
                print(
                    f"{t.strftime('%Y-%m-%d %H:%S %Z')}: placeholders={min_placeholders}, capacity={min_capacity}"
                )
        # step forward
        t += datetime.timedelta(hours=interval)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url", type=str, help="The URL of a calendar with annotations to test."
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="The number of days for which to run the test",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=1,
        help="Number of hours between samples to check.",
    )
    parser.add_argument(
        "--start",
        "-s",
        type=str,
        help="Start date. Anyting dateutil can parse will do. Default: now.",
    )
    args = parser.parse_args()
    if args.start:
        start = parse_date(args.start)
        if not start.tzinfo:
            start = start.astimezone(datetime.timezone.utc)
    else:
        start = scaler.utcnow()

    check_plan(
        url=args.url,
        start=start,
        interval=args.interval,
        days=args.days,
    )
