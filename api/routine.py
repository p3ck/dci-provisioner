import os
import subprocess
import siphon
import redis
import settings
import rq
import requests
import time
from utils import makedirs_ignore
import json
import random

import logging

logger = logging.getLogger(__name__)

r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

#Replace with a decorator for which methods can be queued...
actions = ["provision"]


# Validate against actual LABS
def get_jobs_queue(name: str) -> rq.Queue:
    return rq.Queue(
        name=name,
        default_timeout=settings.RQ_JOBS_TIMEOUT,
        connection=r,
    )

def fetch_file(url, dest):
    # NOTE the stream=True parameter
    req = requests.get(url, stream=True)
    with open(dest, 'wb') as file:
        for chunk in req.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                file.write(chunk)
                #file.flush() commented by recommendation from J.F.Sebastian

def find_power_script(power_type):
    power_path = '/etc/power-scripts/%s' % power_type
    if os.path.exists(power_path) and os.access(power_path, os.X_OK):
        return power_path
    raise ValueError('Invalid power type %r' % power_type)

def build_power_env(system, command):
    env = os.environ.copy()
    env['power_address'] = (system.get('bmc_address') or u'').encode('utf8')
    env['power_id'] = (system.get('bmc_port') or u'').encode('utf8')
    env['power_user'] = (system.get('bmc_user') or u'').encode('utf8')
    env['power_pass'] = (system.get('bmc_password') or u'').encode('utf8')
    env['power_mode'] = command.encode('utf8')
    return env

def handle_power(system, command):
    script = find_power_script(system.get('bmc_type'))
    env = build_power_env(system, command)
    # We try the command up to 5 times, because some power commands
    # are flakey (apparently)...
    for attempt in range(1, settings.POWER_ATTEMPTS + 1):
        if attempt > 1:
            # After the first attempt fails we do a randomised exponential
            # backoff in the style of Ethernet.
            # Instead of just doing time.sleep we do a timed wait on
            # shutting_down, so that our delay doesn't hold up the shutdown.
            delay = random.uniform(attempt, 2**attempt)
            logger.debug('Backing off %0.3f seconds for power command %s',
                    delay, system.get('fqdn'))
            time.sleep(delay)
        logger.debug('Launching power script %s (attempt %s) with env %r',
                script, attempt, env)

        p = subprocess.Popen([script], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            output,std_err = p.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            p.kill()
            output,std_err = p.communicate()

        if p.returncode == 0:
            break
    if p.returncode != 0:
        output = output.decode("utf-8")
        sanitised_output = output[:150].strip()
        if system.get('bmc_password'):
            sanitised_output = sanitised_output.replace(
                    system.get('bmc_password'), '********')
        raise ValueError('Power script %s failed after %s attempts with exit status %s:\n%s'
                % (script, attempt, p.returncode, sanitised_output))

def power_cycle(system):
    """
    Power cycle Host
    """

    handle_power(system, "off")
    time.sleep(5)
    handle_power(system, "on")

def provision(system, action):
    """
    Provision a host..
      Retrieve Kernel and Ramdisk
      Set Netboot entry
      Power cycle Host
    """

    # Fetch image installer for host
    if action.get("image_url"):
        image_rel_path = os.path.join(action["hex_ip"], 'image')
        image_path = os.path.join(settings.TFTP_ROOT, image_rel_path)
        makedirs_ignore(os.path.dirname(image_path), mode=0o755)
        logger.debug('Fetching file %s for %s', action["image_url"], image_path)
        fetch_file(action["image_url"], image_path)
    else:
        image_rel_path = ''

    # Fetch kernel for host
    kernel_rel_path = os.path.join(action["hex_ip"], 'kernel')
    kernel_path = os.path.join(settings.TFTP_ROOT, kernel_rel_path)
    makedirs_ignore(os.path.dirname(kernel_path), mode=0o755)
    logger.debug('Fetching file %s for %s', action["kernel_url"], kernel_path)
    fetch_file(action["kernel_url"], kernel_path)

    # Fetch ramdisk for host
    initrd_rel_path = os.path.join(action["hex_ip"], 'initrd')
    initrd_path = os.path.join(settings.TFTP_ROOT, initrd_rel_path)
    makedirs_ignore(os.path.dirname(initrd_path), mode=0o755)
    logger.debug('Fetching file %s for %s', action["initrd_url"], initrd_path)
    fetch_file(action["initrd_url"], initrd_path)

    # Configure tftp for host
    netboot_values = dict(hex_ip = action["hex_ip"],
                          arch = system.get("arch"),
                          image_path = image_rel_path,
                          kernel_path = kernel_rel_path,
                          initrd_path = initrd_rel_path,
                          use_boot_image = str(action.get('use_boot_image')),
                          kernel_options = action.get("kernel_options", ''))
    r.hset("netboot:%s" % action["hex_ip"], mapping=netboot_values)
    r.expire("netboot:%s" % action["hex_ip"], 3600)

    # Configure kickstart for host
    ks_meta = action.get("ks_meta", {})
    kickstart_values = json.dumps(dict(hex_ip = action["hex_ip"],
                                       fqdn = system.get("fqdn", ""),
                                       arch = system.get("arch", ""),
                                       **ks_meta))
    r.set("kickstart:%s" % action["hex_ip"], kickstart_values)

    # Power cycle host
    power_cycle(system)

    provision_settings = dict(netboot_values = netboot_values,
                              kickstart_values = kickstart_values)
    return provision_settings
