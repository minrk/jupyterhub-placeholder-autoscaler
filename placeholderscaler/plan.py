import argparse
import datetime
import os
from unittest import mock

from . import scaler


def check_plan(start=None, days=7, interval=1):
    if start is None:
        start = scaler.utcnow()
    t = start
    # scan a week and see what we come up with
    end = start + datetime.timedelta(days=days)
    f = os.path.abspath("test-course.ics")
    os.environ["PLACEHOLDER_ICS_URL"] = f
    while t < end:
        with mock.patch.object(scaler, "utcnow", lambda: t):
            print(t, scaler.get_target_capacity())
        t += datetime.timedelta(hours=interval)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)
    check_plan()
