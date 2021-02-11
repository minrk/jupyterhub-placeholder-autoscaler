import datetime
import os
from unittest import mock

from placeholderscaler import scaler


def test():
    # scan a week and see what we come up with
    t = start = scaler.utcnow() - datetime.timedelta(days=3)
    end = t + datetime.timedelta(days=7)
    f = os.path.abspath("test-course.ics")
    os.environ["PLACEHOLDER_ICS_URL"] = f
    while t < end:
        with mock.patch.object(scaler, "utcnow", lambda: t):
            print(t, scaler.get_target_capacity())
        t += datetime.timedelta(hours=1)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    test()
