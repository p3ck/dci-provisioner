import os

# python-RQ and workers settings
RQ_JOBS_TIMEOUT = os.getenv("JOBS_TIMEOUT", "10h")
IMAGE_FETCH_TIMEOUT = os.getenv("IMAGE_FETCH_TIMEOUT", 120)

# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)

# Provisioner settings
PROVISIONER_PORT = os.getenv("PROVISIONER_PORT", 8000)

# Lab settings
LAB_HOST = os.getenv("LAB_HOST", "localhost")
LAB_PORT = os.getenv("LAB_PORT", 8000)
TFTP_ROOT = os.getenv("TFTP_ROOT", "/opt/tftpboot")
TEMPLATE_DIR = os.getenv("TEMPLATE_DIR", "/opt/templates")
POWER_ATTEMPTS = os.getenv("POWER_ATTEMPTS", 5)

# This is set to dci-provisioner but you will never be able to login
# unless you change the default kickstart template, since we disable password logins for root
ROOT_PW = "$6$DCI$vNnnHOqY2pZqc2FF26kEFXrUuTYKNwYk9LhH7aeamcxPBukke1mfldc8bv62AEb/AGREsqXcfdHYVSMOYjEoC0"
