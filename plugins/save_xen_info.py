"""Saves some virtualization attributes in case the node is a Xen host"""
import subprocess
import os
import json

from fabric.api import env, sudo, abort, hide

from littlechef import chef, lib


def execute(node):
    """Uses ohai to get virtualization information which is then saved to then
    node file

    """
    with hide('everything'):
        virt = json.loads(sudo('ohai virtualization'))
    if not len(virt) or virt[0][1] != "host":
        # It may work for virtualization solutions other than Xen
        print("This node is not a Xen host, doing nothing")
        return
    node['virtualization'] = {
        'role': 'host',
        'system': 'xen',
        'vms': [],
    }
    # VMs
    with hide('everything'):
        vm_list = sudo("xm list")
    for vm in vm_list.split("\n")[2:]:
        data = vm.split()
        if len(data) != 6:
            break
        node['virtualization']['vms'].append({
            'fqdn': data[0], 'RAM': data[2], 'cpus': data[3]})
    print("Found {0} VMs for this Xen host".format(
          len(node['virtualization']['vms'])))
    # Save node file and remove the returned temp file
    del node['name']
    os.remove(chef.save_config(node, True))
