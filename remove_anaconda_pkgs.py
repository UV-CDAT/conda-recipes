#!/usr/bin/env python                                                                                              
import argparse
import os
import sys
import re
import subprocess
import shlex
from datetime import datetime, timedelta


parser = argparse.ArgumentParser(
    description='remove your anaconda pkgs that are older than the specified constraint(s)',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-c", "--channel", action='append', help="conda channel, ex: cdat/label/unstable")
parser.add_argument("-p", "--packages", help="conda packages, ex: 'thermo cdutil'",
                    default=None)
parser.add_argument("-R", "--regex", default=None,
                    help="regex to match with substring in the pkg version, ex: '.*2016.*', '.*(2016|2017).*'")
parser.add_argument("-o", "--older_than", default=None,
                    help="look for packages older than specified constraints: days=<num>, hours=<num>, minutes=<num> or weeks=<num>")
parser.add_argument("-d", "--dryrun", default=False, action="store_true",
                    help="dry run do not actually do anything, just list out the packages to be removed")

parser.add_argument("-n", "--no_prompt", default=False, action="store_true",
                    help="prompt before really removing")

#
# Example runs: REMEMBER to use the '-d' option first to check if you really want to 
#    remove the files
#
# python ./remove_anaconda_pkgs.py -c cdat/label/linatest -R ".*(2018|2019).*" -d
# python ./remove_anaconda_pkgs.py -c cdat/label/linatest -o days=210 -d 
# python ./remove_anaconda_pkgs.py -c cdat/label/linatest -c cdat/label/unstable -c cdat/label/nightly -o days=5 --d
#

args = parser.parse_args(sys.argv[1:])

channels = args.channel
packages = args.packages
regex = args.regex
if regex:
    regex = re.compile(args.regex.replace("\!","!"))

regex=args.regex
older_than= args.older_than
dryrun = args.dryrun
no_prompt = args.no_prompt

def run_command(cmd, join_stderr=True, shell_cmd=False, verbose=True, cwd=None):
    if verbose:
        print("CMD: {c}".format(c=cmd))
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    if join_stderr:
        stderr_setting = subprocess.STDOUT
    else:
        stderr_setting = subprocess.PIPE

    if cwd is None:
        current_wd = os.getcwd()
    else:
        current_wd = cwd

    P = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr_setting,
        bufsize=0, cwd=current_wd, shell=shell_cmd)
    out = []
    while P.poll() is None:
        read = P.stdout.readline().rstrip()
        decoded_str = read.decode('utf-8')
        out.append(decoded_str)
        if verbose == True:
            print(decoded_str)

    ret_code = P.returncode
    return(ret_code, out)

def check_if_pkg_satisfies_constraint(pkg_version, older_than_time_delta):
    """
       checks if the specified <pkg_version> is older than the specified
       <older_than_time_delta>

    older_than_time_delta can one of these:
    days=<num>, minutes=<num>, hours=<num>, weeks=<num>
    pkg_version ex: 8.0.2018.07.30.22.03.g70b6163 py36_0
    """
    if older_than_time_delta is None:
        return True

    current_time = datetime.now()
    m = re.match(r'^\d+.\d+.\d+.(\d+).(\d+).(\d+).\d+.\d+.\S+$', pkg_version)
    if m is None:
        m = re.match(r'^\d+.\d+.(\d+).(\d+).(\d+).\d+.\d+.\S+$', pkg_version)
    
    if m is None:
        # this will be the case where the package's version is not
        # following the above formats.
        return False

    pkg_time = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    match_obj = re.match(r'(\S+)=(\d+)', older_than_time_delta)
    time_key = match_obj.group(1)
    time_val = match_obj.group(2)
    if time_key == 'days':
        delta = timedelta(days=int(time_val))
    elif time_key == 'hours':
        delta = timedelta(hours=int(time_val))
    elif time_key == 'minutes':
        delta = timedelta(minutes=int(time_val))
    elif time_key == 'weeks':
        delta = timedelta(weeks=int(time_val))
    
    if current_time - pkg_time > delta:
        return True
    else:
        return False

def get_packages(channels, packages, regex, constraint):
    """
    gets the list of the specified <packages> from the specified
    <channels>, and satisfy the <regex> and <constraint> if specified.
    """
    pkgs = []
    for channel in channels:
        cmd = "conda search --override -c {c}".format(c=channel)
        ret_code, out = run_command(cmd, True, False, True)

        for p in out[2:-1]:
            if packages is None and regex is None and constraint is None:
                pkgs.append(p)
                continue
            include_pkg = False
            if packages:
                m = re.search(r"^{pkgs}\s+\S+\s+\S+\s+\S+".format(pkgs=packages), p)
                if m:
                    include_pkg = True
            if regex:
                m1 = re.match(r"^\S+\s+{r}\s+\S+\s+\S+".format(r=regex), p)
                if m1:
                    include_pkg = True

            if constraint:
                # check if it satisfies time contraint if specified
                m2 = re.match(r"^\S+\s+(\S+)\s+\S+\s+\S+", p)
                pkg_version = m2.group(1)
                satisfies_constraint = check_if_pkg_satisfies_constraint(pkg_version,
                                                                         constraint)
                if satisfies_constraint:
                    include_pkg = True

            if include_pkg:
                pkgs.append(p)

    return pkgs

def do_remove(pkgs):

    ret_code = 0
    for p in pkgs:
        m = re.match(r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', p)
        pkg = m.group(1)
        version = m.group(2)
        channel = m.group(4)
        m1 = re.match(r'(\S+)/\S+/\S+', channel)
        channel_name = m1.group(1)
        pkg_to_remove = "{c}/{p}/{v}".format(c=channel_name,
                                             p=pkg,
                                             v=version)
        print("\nFound: {p}".format(p=pkg_to_remove))
        if args.dryrun:
            continue

        # prompt user before really removing
        user_prompt = "Remove {p} ? enter ['y'|'n']: ".format(p=pkg_to_remove)
        user_input = input(user_prompt)
        if user_input == 'n':
            print("NOT REMOVING {p}".format(p=pkg_to_remove))
            continue
        
        print("Removing: {p}".format(p=pkg_to_remove))
        cmd = "anaconda remove -f {p}".format(p=pkg_to_remove)
        ret_code, out = run_command(cmd, True, False, True)

    return(ret_code)

pkgs = get_packages(channels, packages, regex, older_than)

do_remove(pkgs)


