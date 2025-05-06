import flask
import json
import redis
import jinja2
import settings
import routine
import socket
import string
from utils import decode_values, extract_arg


app = flask.Flask(__name__)
r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

@app.route("/netboots", methods=["GET"])
def get_all_netboots():
    netboots = [v.decode('utf-8') for v in r.scan_iter('netboot:*')]
    nb_netboots = len(netboots)
    return flask.jsonify({"netboots": netboots, "_meta": {"count": nb_netboots}})

def render_template(template_file, metadata):
    jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(settings.TEMPLATE_DIR),
            autoescape=jinja2.select_autoescape(),
            )
    template = jinja_env.get_template(template_file)
    rendered = template.render(**metadata)
    return rendered

def clear_netboot(values):
    r.expire("netboot:%s" % values["hex_ip"], 10)

def get_ks_url(hex_ip):
    ks_host = "inst.ks=http://{0}:{1}/kickstarts/{2}".format(settings.LAB_HOST,
                                                             settings.LAB_PORT,
                                                             hex_ip)
    return ks_host

def render_kickstart(osmajor, kickstart_values):
    candidates = [
        'kickstarts/%s' % osmajor,
        'kickstarts/%s' % osmajor.rstrip(string.digits),
        'kickstarts/default',
    ]
    for candidate in candidates:
        try:
            return render_template(candidate, kickstart_values)
        except jinja2.TemplateNotFound:
            continue
    raise ValueError('No kickstart template found for %s, tried: %s'
                     % (osmajor, ', '.join(candidates)))

@app.route("/kickstarts/<hex_ip>", methods=["GET"])
def kickstart(hex_ip):
    kickstart_values = decode_values(r.hgetall("kickstart:%s" % hex_ip))
    if kickstart_values:
        osmajor = kickstart_values.get("osmajor")
        # de-serialize repos and ssh_pub_keys
        repos = json.loads(kickstart_values.get("repos"))
        ssh_pub_keys = json.loads(kickstart_values.get("ssh_pub_keys"))
        # update with de-serialized versions
        kickstart_values.update({'repos': repos,
                                 'ssh_pub_keys': ssh_pub_keys,
                                 'root_pw': settings.ROOT_PW
                                 })
        return render_kickstart(osmajor, kickstart_values)
    return flask.Response(
        json.dumps(
            {
                "message": f"{hex_ip} kickstart does not exist."
            }
        ),
        status=404,
        content_type="application/json",
    )

@app.route("/netboots/<hex_ip>/image", methods=["GET"])
def netboot_image(hex_ip):
    image = ""
    netboot_values = decode_values(r.hgetall("netboot:%s" % hex_ip))
    if netboot_values:
        if netboot_values.get('use_boot_image') == "True":
            image = '{0}/image'.format(hex_ip)
        else:
            image = '{0}-image'.format(netboot_values['arch'])
    if image:
        return flask.send_from_directory(settings.TFTP_ROOT, image)
    else:
        return image, 404

@app.route("/netboots/<hex_ip>/pxe", methods=["GET"])
def netboot_pxe(hex_ip):
    template = "netboot/pxe_default.j2"
    netboot_values = decode_values(r.hgetall("netboot:%s" % hex_ip))
    if netboot_values:
        netboot_values.update({'ks_host': get_ks_url(hex_ip)})
        clear_netboot(netboot_values)
        template = "netboot/pxe_boot.j2"
    return render_template(template, netboot_values)

@app.route("/netboots/<hex_ip>/petitboot", methods=["GET"])
def netboot_petitboot(hex_ip):
    template = "netboot/petitboot.j2"
    if netboot_values:
        netboot_values.update({'ks_host': get_ks_url(hex_ip)})
        clear_netboot(netboot_values)
        return render_template(template, netboot_values)
    else:
        return "", 404

@app.route("/netboots/<hex_ip>/grub2", methods=["GET"])
def netboot_grub2(hex_ip):
    template = "netboot/grub2_default.j2"
    netboot_values = decode_values(r.hgetall("netboot:%s" % hex_ip))
    if netboot_values:
        # devicetree is needed for some aarch64 systems
        kernel_options = netboot_values.get("kernel_options", "")
        devicetree, kernel_options = extract_arg('devicetree=', kernel_options)
        if devicetree:
            devicetree = 'devicetree %s' % devicetree
        netboot_values.update({'ks_host': get_ks_url(hex_ip),
                               'devicetree': devicetree,
                               'kernel_options': kernel_options
                               })
        clear_netboot(netboot_values)
        template = "netboot/grub2_boot.j2"
    return render_template(template, netboot_values)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.LAB_PORT, debug=True)

