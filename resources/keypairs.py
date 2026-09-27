import pulumi_openstack as openstack

# 1. Ask OpenStack to generate a keypair
keypair = openstack.compute.Keypair("ansible_keypair",
    name="ansible-deploy-key"
)