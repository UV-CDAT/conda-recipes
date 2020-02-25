import glob
import argparse
import os
import sys
import subprocess
import shlex
import shutil
import requests
import time
import re

from Utils import run_cmd, run_cmds, run_cmd_capture_output
from Utils import SUCCESS, FAILURE
from release_tools import prep_conda_env, check_if_conda_forge_pkg, clone_feedstock
from release_tools import clone_repo, prepare_recipe_in_local_feedstock_repo
from release_tools import prepare_recipe_in_local_repo, rerender, do_build
from release_tools import rerender_in_local_feedstock, build_in_local_feedstock
from release_tools import rerender_in_local_repo, build_in_local_repo, get_git_rev


l = time.localtime()
cwd = os.getcwd()

#
# This script is to be run under a CDAT project repo directory.
#
# This script can be used to build CDAT packages that go to cdat channel
# (ex: cdat/label/nightly) and CDAT packages that go to cdat channel
# but eventually will get uploaded to conda-forge (i.e. packages that have 
# conda-forge feedstock repo.
#
# For conda-forge packages:
# + clone the feedstock to <workdir>/<pkg_name>-feedstock directory.
# + clone the project repo to <workdir>/<repo_name> directory.
# + if project repo has recipe/meta.yaml.in, will build using the project repo recipe.
#   This should be the case when the project branch is modifying the recipe
#   (i.e. different from the feedstock's recipe).
#   IMPORTANT: when we release the package to conda-forge, we have to remove
#   the project repo's recipe.
#
# For non conda-forge packages (packages that are uploaded to cdat/label/nightly
# or cdat/label/<release>:
# + clone the project repo to <workdir>/<repo_name> directory.
#
# The need to reclone the project repo is because rerendering will
# overwrite .circleci/config.yml, and this is problematic if we are running
# this script in CircleCI.
#

parser = argparse.ArgumentParser(
    description='conda build upload',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-p", "--package_name",
                    help="Package name to build")
parser.add_argument("-o", "--github_organization_name",
                    help="github organization name", default="CDAT")
parser.add_argument("-r", "--repo_name",
                    help="repo name to build")
parser.add_argument("-b", "--branch", default='master', help="branch to build")
parser.add_argument("-v", "--version",
                    help="version are we building for")
parser.add_argument("-l", "--last_stable",
                    help="last stable (released) version, specify this when building for nightly")
parser.add_argument("-w", "--workdir", default=cwd, help="work full path directory")
parser.add_argument("-B", "--build", default="0", help="build number, this should be 0 for nightly")
parser.add_argument("-C", "--conda_clean", action='store_true', help="do 'conda clean --all'")
parser.add_argument("--do_rerender", action='store_true', help="do 'conda smithy rerender'")
parser.add_argument("--do_build", action='store_true', help="do 'conda build -m <variant file> ...'")
parser.add_argument("--build_version", default="3.7", help="specify python version to build 2.7, 3.7, 3.8")

args = parser.parse_args(sys.argv[1:])

pkg_name = args.package_name
branch = args.branch
workdir = args.workdir
build = args.build
do_conda_clean = args.conda_clean

if args.repo_name:
    repo_name = args.repo_name
else:
    repo_name = pkg_name

# github organization of projects
organization = args.github_organization_name

# for calling run_cmds
join_stderr = True
shell_cmd = False
verbose = True
version = None

def construct_pkg_ver(repo_dir, arg_version, arg_last_stable):
    git_rev = get_git_rev(repo_dir)
    if arg_version:
        # we are building for a release of a non conda-forge package
        version = arg_version
    else:
        # we are building for nightly
        today2 = "%s.%.2i.%.2i.%.2i.%.2i.%.2i.%s" % (arg_last_stable, l.tm_year, l.tm_mon, l.tm_mday, l.tm_hour, l.tm_min, git_rev)
        version = today2

    return version

#
# main
#

is_conda_forge_pkg = check_if_conda_forge_pkg(pkg_name)

if args.do_rerender:
    status = prep_conda_env()
    if status != SUCCESS:
        sys.exit(status)

    ret, repo_dir = clone_repo(organization, repo_name, branch, workdir)
    if ret != SUCCESS:
        sys.exit(ret)
    version = construct_pkg_ver(repo_dir, args.version, args.last_stable)
else:
    repo_dir = "{w}/{p}".format(w=workdir, p=repo_name)


if is_conda_forge_pkg:
    if args.do_rerender:
        status = clone_feedstock(pkg_name, workdir)
        if status != SUCCESS:
            sys.exit(status)

        status = prepare_recipe_in_local_feedstock_repo(pkg_name, organization, repo_name, branch, version, build, repo_dir, workdir)
        if status != SUCCESS:
            sys.exit(status)

        status = rerender_in_local_feedstock(pkg_name, workdir)

    if args.do_build:
        status = build_in_local_feedstock(pkg_name, workdir, args.build_version)

else:
    # non conda-forge package (does not have feedstock)
    repo_dir = os.path.join(workdir, repo_name)
    print("Building non conda-forge package")
    print("...branch: {b}".format(b=branch))
    print("...build: {b}".format(b=build))
    print("...repo_dir: {d}".format(d=repo_dir))

    if args.do_rerender:
        status = prepare_recipe_in_local_repo(branch, build, version, repo_dir)
        if status != SUCCESS:
            sys.exit(status)

        status = rerender_in_local_repo(repo_dir)

    if args.do_build:
        status = build_in_local_repo(repo_dir, args.build_version) 

sys.exit(status)


