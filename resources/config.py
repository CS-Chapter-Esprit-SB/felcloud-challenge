"""Shared configuration values for the felcloud proxy stack."""
import pulumi

config = pulumi.Config()

external_network_name = "INTERNET"
image_name = "Ubuntu 22.04 LTS - Jammy Jellyfish"
flavor_name = "G0.basic.1c2g"