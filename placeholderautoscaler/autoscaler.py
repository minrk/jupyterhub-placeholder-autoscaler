#!/usr/bin/env python3
import logging
import os
import re
import time
import datetime

import icalendar
import requests
from icalevents import icalevents

# imports needed for vendored _get_cal_tz:
from dateutil.tz import gettz
from pytz import timezone

UTC = datetime.timezone.utc


# reflectors vendored from kubespawner-0.15
from .reflector import NamespacedResourceReflector
from .clients import shared_client


log = logging.getLogger(__name__)


class PodReflector(NamespacedResourceReflector):
    """Reflector for user pods

    identical to KubeSpawner
    """

    kind = "pods"
    list_method_name = "list_namespaced_pod"
    labels = {
        "component": "singleuser-server",
    }


class PlaceholderReflector(NamespacedResourceReflector):
    """Reflector for placeholder-pod stateful set"""

    api_group_name = "AppsV1Api"
    kind = "stateful sets"
    list_method_name = "list_namespaced_stateful_set"
    labels = {
        "component": "user-placeholder",
    }


def check_placeholder_count(
    placeholder: dict,
    num_user_pods: int,
    min_placeholders: int = 0,
    min_capacity: int = 0,
):
    """Check the placeholder count and update the stateful set if necessary"""
    capacity_placeholders = min_capacity - num_user_pods
    current_placeholders = placeholder["spec"]["replicas"]
    target_placeholders = max(capacity_placeholders, min_placeholders)
    kube = shared_client("AppsV1Api")
    log.debug(
        f"User pods: {num_user_pods}, target placeholders: {target_placeholders}, current placeholders: {current_placeholders}"
    )
    if target_placeholders != current_placeholders:
        if capacity_placeholders > min_placeholders:
            reason = f"for minimum capacity={min_capacity}"
        else:
            reason = f"for minimum placeholder count"
        name = placeholder["metadata"]["name"]
        namespace = placeholder["metadata"]["namespace"]
        log.info(
            f"Scaling {name}.replicas {current_placeholders}->{target_placeholders} {reason}"
        )
        kube.patch_namespaced_stateful_set(
            body={"spec": {"replicas": target_placeholders}},
            namespace=namespace,
            name=name,
        )
    else:
        log.debug(f"Placeholder count {current_placeholders} is correct")


assignment_pattern = re.compile(
    r"^\s*([a-z_0-9]+)\s*[\=:]\s*(\d+)\s*$", flags=re.IGNORECASE
)


def parse_event(event):
    """Parse a single event

    Looks for lines in the description like

    min_capacity = 100
    min_placeholders = 10
    """
    log.debug(f"Checking {_event_repr(event)} for configuration")
    min_placeholders = None
    min_capacity = None
    for line in event.description.splitlines():
        m = assignment_pattern.match(line)
        if m:
            key, value_str = m.groups()
            if key == "min_capacity":
                min_capacity = int(value_str)
            elif key == "min_placeholders":
                min_placeholders = int(value_str)
    return min_placeholders, min_capacity


def utcnow():
    """Standalone function for easier mocking"""
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _event_repr(event):
    """Simple repr of a calenar event

    For use in logging. Shows title and time.
    """
    if event.all_day:
        return f"{event.summary} {event.start.date()}"
    else:
        if event.end.date() == event.start.date():
            return f"{event.summary} {event.start.strftime('%Y-%m-%d %H:%M')}-{event.end.strftime('%H:%M')}"
        else:
            return f"{event.summary} {event.start.strftime('%Y-%m-%d %H:%M')}-{event.end.strftime('%Y-%m-%d %H:%M')}"


def _get_cal_tz(content: str):
    """Get the calendar timezone

    This code is extracted from icalevents.icalparser
    It's not in an importable form over there, so copy it outright

    License: MIT
    """
    calendar = icalendar.Calendar.from_ical(content)

    # BEGIN PATCH: support X-WR-Timezone, which google sets as calendar default timezone
    if calendar.get("x-wr-timezone"):
        return gettz(str(calendar["x-wr-timezone"]))
    # END PATCH

    # Keep track of the timezones defined in the calendar
    timezones = {}
    for c in calendar.walk("VTIMEZONE"):
        name = str(c["TZID"])
        try:
            timezones[name] = c.to_tz()
        except IndexError:
            # This happens if the VTIMEZONE doesn't
            # contain start/end times for daylight
            # saving time. Get the system pytz
            # value from the name as a fallback.
            timezones[name] = timezone(name)

    # If there's exactly one timezone in the file,
    # assume it applies globally, otherwise UTC
    if len(timezones) == 1:
        cal_tz = gettz(list(timezones)[0])
    else:
        cal_tz = UTC
    return cal_tz


def get_events(url: str):
    """Wrapper for icalevents.events

    Mostly to deal with weird issues around url parsing and timezones
    """

    if url.startswith("file://"):
        path = url.split("://", 1)[1]
        with open(path) as f:
            content = f.read()
    elif "://" not in url:
        path = url
        with open(path) as f:
            content = f.read()
    else:
        r = requests.get(url)
        r.raise_for_status()
        content = r.text

    cal_tz = _get_cal_tz(content)

    now = utcnow()
    events = icalevents.parse_events(content, start=now, end=now)
    for event in events:
        # fix timezone for all-day events
        if not event.start.tzinfo:
            log.debug(
                f"Using calendar default timezone {cal_tz} for {_event_repr(event)}"
            )
            event.start = event.start.replace(tzinfo=cal_tz)
        if not event.end.tzinfo:
            event.end = event.end.replace(tzinfo=cal_tz)
    return events


def get_target_capacity_ics(url: str):
    """Get the target capacity from an ICS calendar

    Given a URL, parse the calendar for current events
    and read the descriptions of current events to get
    overrides for capacity configuration.

    If no current events are found, default to environment variables.
    """
    log.debug(f"Fetching calendar {url}")
    events = get_events(url)
    min_placeholders = None
    min_capacity = None
    now = utcnow()
    for event in events:
        # icalevents filters *nearby* events,
        # but can still return events that aren't happening right now
        if not (event.start < now and event.end > now):
            # exclude events not occurring right now
            continue
        evt_placeholders, evt_capacity = parse_event(event)
        if evt_placeholders is not None:
            if min_placeholders is None or min_placeholders < evt_placeholders:
                min_placeholders = evt_placeholders
                log.info(
                    f"Event {_event_repr(event)} setting min_placeholders={min_placeholders}"
                )
        if evt_capacity is not None:
            if min_capacity is None or min_capacity < evt_capacity:
                min_capacity = evt_capacity
                log.info(
                    f"Event {_event_repr(event)} setting min_capacity={min_capacity}"
                )
        if evt_capacity is None and evt_placeholders is None:
            log.debug(f"Event {_event_repr(event)} sets no values")

    return min_placeholders, min_capacity


def get_target_capacity():
    """Get the current target capacity

    Currently static, but could retrieve from a calendar, etc.
    """
    ics_url = os.environ.get("PLACEHOLDER_ICS_URL")
    min_placeholders = min_capacity = None
    if ics_url:
        min_placeholders, min_capacity = get_target_capacity_ics(ics_url)
    if min_placeholders is None:
        min_placeholders = int(os.environ.get("PLACEHOLDER_MIN_COUNT", "5"))
    if min_capacity is None:
        min_capacity = int(os.environ.get("PLACEHOLDER_MIN_CAPACITY", "10"))
    return (min_placeholders, min_capacity)


def main():
    logging.basicConfig(level=logging.DEBUG)

    # load config from env
    interval = int(os.environ.get("PLACEHOLDER_CHECK_INTERVAL", "60"))
    namespace = os.environ["NAMESPACE"]

    # TODO: support loading config into these?
    pod_reflector = PodReflector(namespace=namespace)
    placeholder_reflector = PlaceholderReflector(namespace=namespace)

    # wait for placeholder and pod reflectors to have some resources
    # before we start checking
    pod_reflector.first_load_future.result()
    placeholder_reflector.first_load_future.result()

    # validate placeholder selector
    assert (
        len(placeholder_reflector.resources) == 1
    ), "Expected exactly one placeholder, got {', '.join(placeholder.resources)}"

    while True:
        pods = pod_reflector.resources
        placeholder = next(iter(placeholder_reflector.resources.values()))

        min_placeholders, min_capacity = get_target_capacity()

        check_placeholder_count(
            placeholder,
            num_user_pods=len(pods),
            min_placeholders=min_placeholders,
            min_capacity=min_capacity,
        )
        time.sleep(interval)


if __name__ == "__main__":
    pass
