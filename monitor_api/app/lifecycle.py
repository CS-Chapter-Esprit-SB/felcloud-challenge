from __future__ import annotations


from .openstack_client import (
    classify_instance,
    get_connection,
)


class LifecycleError(RuntimeError):
    pass


def change_instance_state(
    server_id: str,
    action: str,
) -> dict[str, str]:
    """Start or stop a managed sandbox after validating ownership."""

    if action not in {"start", "stop"}:
        raise ValueError("Action must be 'start' or 'stop'.")

    connection = get_connection()
    server = connection.compute.get_server(server_id)

    if server is None:
        raise LifecycleError("Instance not found.")

    classification = classify_instance(server)

    if classification != "sandbox":
        raise LifecycleError(
            f"Refusing to {action} an instance classified as "
            f"'{classification}'."
        )

    if action == "start":
        if server.status == "ACTIVE":
            return {
                "id": server.id,
                "status": server.status,
                "message": "Instance is already running.",
            }

        if server.status != "SHUTOFF":
            raise LifecycleError(
                f"Cannot start instance in state {server.status}."
            )

        connection.compute.start_server(server)

    else:
        if server.status == "SHUTOFF":
            return {
                "id": server.id,
                "status": server.status,
                "message": "Instance is already stopped.",
            }

        if server.status != "ACTIVE":
            raise LifecycleError(
                f"Cannot stop instance in state {server.status}."
            )

        connection.compute.stop_server(server)

    return {
        "id": server.id,
        "status": "operation_requested",
        "message": f"Instance {action} requested.",
    }