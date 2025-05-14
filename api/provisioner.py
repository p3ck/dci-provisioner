import flask
import json
import redis
from jinja2 import Environment, FileSystemLoader, select_autoescape
import settings
import routine
import socket
from utils import decode_values
from rq.job import Job


app = flask.Flask(__name__)
r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

def pxe_basename(fqdn):
    # pxelinux uses upper-case hex IP address for config filename
    ipaddr = socket.gethostbyname(fqdn)
    return '%02X%02X%02X%02X' % tuple(int(octet) for octet in ipaddr.split('.'))

@app.route("/systems", methods=["GET"])
def systems_list():
    systems = [v.decode('utf-8').replace('system:','',1) for v in r.scan_iter('system:*')]
    nb_systems = len(systems)
    return flask.jsonify({"systems": systems, "_meta": {"count": nb_systems}})

@app.route("/systems/<fqdn>", methods=["GET"])
def system(fqdn):
    k_v = decode_values(r.hgetall("system:%s" % fqdn))
    hex_ip = pxe_basename(fqdn)
    netboot = decode_values(r.hgetall("netboot:%s" % hex_ip))
    kickstart = decode_values(r.hgetall("kickstart:%s" % hex_ip))
    if len(k_v) == 0:
        return flask.Response(
            json.dumps(
                {
                    "message": f"{fqdn} system does not exist. Please query GET /systems."
                }
            ),
            status=404,
            content_type="application/json",
        )
    else:
        # Include info about netboot and kickstart settings
        k_v.update({'netboot': bool(netboot),
                    'kickstart': bool(kickstart)})
        return flask.jsonify({fqdn: k_v})

@app.route("/systems/<fqdn>", methods=["POST"])
def system_create(fqdn):
    k_v = decode_values(r.hgetall("system:%s" % fqdn))
    if len(k_v) == 0:
        values = flask.request.json
        values.update({'fqdn': fqdn})
        r.hset("system:%s" % fqdn, mapping=values)
        return flask.Response(
            json.dumps(
                {
                    "status": "OK",
                    "message": f"{fqdn} system has been created.",
                }
            ),
            status=201,
            content_type="application/json",
        )
    else:
        return flask.Response(
            json.dumps(
                {
                    "message": f"{fqdn} system already exists."
                }
            ),
            status=409,
            content_type="application/json",
        )

@app.route("/systems/<fqdn>", methods=["PATCH"])
def system_update(fqdn):
    k_v = decode_values(r.hgetall("system:%s" % fqdn))
    if len(k_v) != 0:
        values = flask.request.json
        updates = dict(set(k_v.items()) ^ set(values.items()))
        k_v.update(values)
        r.hset("system:%s" % fqdn, mapping=k_v)
        return flask.jsonify({fqdn: updates})
    else:
        return flask.Response(
            json.dumps(
                {
                    "message": f"{fqdn} system doesn't exists."
                }
            ),
            status=204,
            content_type="application/json",
        )

@app.route("/systems/<fqdn>/actions", methods=["POST"])
def system_actions(fqdn):
    k_v = decode_values(r.hgetall("system:%s" % fqdn))
    if len(k_v) == 0:
        return flask.Response(
            json.dumps(
                {
                    "message": f"{fqdn} system does not exist. Please query GET /systems."
                }
            ),
            status=404,
            content_type="application/json",
        )
    else:
        values = flask.request.json
        action = values.pop("action", None)

        values['hex_ip'] = pxe_basename(fqdn)

        action_args = dict(system = k_v, action = values)

        if action in routine.actions:
            job = routine.get_jobs_queue(k_v["lab"]).enqueue(
                    getattr(routine, action), kwargs=action_args
                    )
            return flask.Response(
                    json.dumps(
                        {
                            "status": "OK",
                            "message": f"Action for {fqdn} has been started.",
                            "job": job.get_id(),
                        }
                    ),
                    status=201,
                    content_type="application/json",
            )
        else:
            return flask.Response(
                    json.dumps(
                        {
                            "message": f"Missing or invalid action. Please query GET /systems/{fqdn}/actions."
                        }
                    ),
                    status=404,
                    content_type="application/json",
                    )

@app.route("/jobs/<job_key>", methods=["GET"])
def job_details(job_key):
    job = Job.fetch(job_key, connection=r)
    status = '{0}'.format(job.get_status())
    if job.is_finished:
        return flask.jsonify({'results': job.result,
                              'status': status}), 200
    elif job.is_failed:
        return flask.jsonify({'exc_info': job.exc_info,
                              'status': status}), 500
    else:
        return flask.jsonify({'status': status}), 202

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

@app.route("/site-map")
def site_map():
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = rule.rule
            links.append((url, rule.endpoint))
    # links is now a list of url, endpoint tuples
    return flask.jsonify({'links': links})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PROVISIONER_PORT, debug=True)

