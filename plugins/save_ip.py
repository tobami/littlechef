"""Gets the IP and adds or updates the ipaddress attribute of a node"""
import subprocess
import os
import re

from fabric.api import env

from littlechef import chef


def parse_ip(text):
    """Extract an IPv4 IP from a text string
    Uses an IP Address Regex: http://www.regular-expressions.info/examples.html

    """
    ip_matches = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', text)
    ip = ip_matches[0] if ip_matches else None
    return ip


def execute(node):
    proc = subprocess.Popen(['ping', '-c', '1', node['name']],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    resp, error = proc.communicate()
    if not error:
        # Split output into lines and parse the first line to get the IP
        ip = parse_ip(resp.split("\n")[0])
        if not ip:
            print "Warning: could not get IP address from node {0}".format(
                node['name'])
        print "Node {0} has IP {1}".format(node['name'], ip)
        # Update with the ipaddress field in the corresponding node.json
        node['ipaddress'] = ip
        os.remove(chef.save_config(node, ip))
    else:
        print "Warning: could not resolve node {0}".format(node['name'])
