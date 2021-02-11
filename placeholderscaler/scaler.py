#!/usr/bin/env python3
import logging
import os
import time


from traitlets.log import get_logger

from .reflector import NamespacedResourceReflector
from .clients import shared_client


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
    placeholder, num_user_pods, min_placeholders=0, min_capacity=0
):
    # import pprint
    # pprint.pprint(placeholder)
    capacity_placeholders = min_capacity - num_user_pods
    current_placeholders = placeholder["spec"]["replicas"]
    target_placeholders = max(capacity_placeholders, min_placeholders)
    kube = shared_client("AppsV1Api")
    log = get_logger()
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


def get_target_capacity():
    """Get the current target capacity

    Currently static, but could retrieve from a calendar, etc.
    """
    min_placeholders = int(os.environ.get("PLACEHOLDER_MIN_COUNT", "5"))
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
