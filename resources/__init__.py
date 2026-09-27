"""Resource definitions for the RIO gateway stack, split by concern.

Submodules:
    config           stack configuration, addressing plan, sandbox leases
    cloud_init       user_data for gateways and sandboxes
    network          gateway and sandbox networks, router
    security_groups  sg-gateway and sg-sandbox
    ports            gateway ports, VIP port, floating IP
    compute          the two gateway instances
    sandboxes        one instance per active sandbox lease
"""
