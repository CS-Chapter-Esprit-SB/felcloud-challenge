import pulumi_openstack as openstack

# 1. Ask OpenStack to generate a keypair
_ = openstack.compute.Keypair("ansible_keypair",
    name="ansible-deploy-key"
)
keypair = openstack.compute.get_keypair(name="aymen_key_2")
