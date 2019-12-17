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

p = subprocess.Popen(["git", "rev-parse", "--short", "HEAD"], stdout=subprocess.PIPE)
git_rev_parse = p.stdout.read().decode('utf-8')
git_rev = "g{0}".format(git_rev_parse).strip()

if "VERSION" in os.environ.keys():
    last_stable=os.environ['VERSION']
else:
    last_stable = "8.2"

l = time.localtime()
today = "%s.%.2i.%.2i.%.2i.%.2i.%.2i.%s" % (last_stable, l.tm_year, l.tm_mon, l.tm_mday, l.tm_hour, l.tm_min, git_rev)

cwd = os.getcwd()

#
# This script can be used to build conda-forge packages or non conda-forge packages 
# (i.e. those packages that goes to cdat/label/<LABEL>)
# This script should be run in the project repository top directory.
#
# For conda-forge packages:
# + clone the fork (fork_repo) of the feedstock to <workdir>/<pkg_name>-feedstock directory.
# + clone the project repo to <workdir>/<repo_name> directory.
# + if project repo has recipe/meta.yaml.in, will build using the project repo recipe.
#   This should be the case when the project branch is modifying the recipe
#   (i.e. different from the feedstock's recipe).
#   IMPORTANT: when we release the package to conda-forge, we have to remove
#   the project repo's recipe.
#
# For non conda-forge packages (packages that are uploaded to cdat/label/nightly
# or cdat/label/<release>:
# 
#

parser = argparse.ArgumentParser(
    description='conda build upload',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-p", "--package_name",
                    help="Package name to build")
parser.add_argument("-r", "--repo_name",
                    help="repo name to build")
parser.add_argument("-b", "--branch", default='master', help="branch to build")
parser.add_argument("-v", "--version", default=today,
                    help="version are we building for")
parser.add_argument("-l", "--last_stable", default=last_stable,
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
last_stable = args.last_stable
workdir = args.workdir
build = args.build
do_conda_clean = args.conda_clean

if args.repo_name:
    repo_name = args.repo_name
else:
    repo_name = pkg_name

today2 = "%s.%.2i.%.2i.%.2i.%.2i.%.2i.%s" % (args.last_stable, l.tm_year, l.tm_mon, l.tm_mday, l.tm_hour, l.tm_min, git_rev)
if args.version != today:
    # we are building for a release of a non conda-forge package
    version = args.version
else:
    # we are building for nightly
    version = today2

# github organization of projects
organization = "CDAT"

# for calling run_cmds
join_stderr = True
shell_cmd = False
verbose = True

def prep_conda_env():
    if do_conda_clean:
        cmd = "conda clean --all"
        ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, workdir)

    pkgs = "conda-build anaconda-client conda-smithy conda-verify conda-forge-pinning conda-forge-build-setup conda-forge-ci-setup"
    cmds = [
        "conda update -y -q conda",
        "conda config --add channels conda-forge --force",
        "conda config --set channel_priority strict",
        "conda install -n base -c conda-forge {p}".format(p=pkgs),
        "conda config --set anaconda_upload no"
        ]
    ret = run_cmds(cmds)
    return ret

def check_if_conda_forge_pkg(pkg_name):
    url = "https://www.github.com/conda-forge/{pkg}-feedstock".format(pkg=pkg_name)
    try:
        request = requests.get(url)
        if request.status_code == 200:
            print("{p} is a conda-forge package".format(p=pkg_name))
            return True
        else:
            print("{p} is not a conda-forge package".format(p=pkg_name))
            return False
    except requests.ConnectionError:
        print("Web site does not exist")
        print("{p} is not a conda-forge package".format(p=pkg_name))
        return False

def clone_feedstock(pkg_name, workdir):
    pkg_feedstock = "{p}-feedstock".format(p=pkg_name)
    conda_forge_pkg_feedstock = "conda-forge/{p}".format(p=pkg_feedstock)

    feedstock_repo_dir = os.path.join(workdir, pkg_feedstock)
    if os.path.exists(feedstock_repo_dir):
        print("REMOVING existing {d}".format(d=feedstock_repo_dir))
        shutil.rmtree(feedstock_repo_dir)

    cmd = "git clone git@github.com:{c}.git".format(c=conda_forge_pkg_feedstock)
    ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, workdir)

    return ret

def clone_repo(repo_name, branch, workdir):
    repo_dir = os.path.join(workdir, repo_name)
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)

    repo_url = "https://github.com/{o}/{r}.git\n\n".format(o=organization,
                                                           r=repo_name)
    if branch == "master":
        cmd = "git clone {u}".format(u=repo_url)
    else:
        cmd = "git clone -b {b} {u}".format(b=branch, u=repo_url)
    ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, workdir)

    return ret, repo_dir

def prepare_recipe_in_local_feedstock_repo(pkg_name, repo_name, branch, repo_dir, workdir):
    repo_url = "https://github.com/{o}/{r}.git\n\n".format(o=organization,r=repo_name)

    pkg_feedstock = "{p}-feedstock".format(p=pkg_name)
    feedstock_dir = os.path.join(workdir, pkg_feedstock)
    recipe_file = os.path.join(feedstock_dir, 'recipe', 'meta.yaml')

    #
    # if repo has a recipe/meta.yaml.in, this means the branch is updating
    # the recipe, use this recipe to build.
    # NOTE: when we build the package for conda-forge, we will need to
    # merge this recipe to feedstock and delete the recipe from the repo.
    #
    repo_recipe = os.path.join(repo_dir, "recipe", "meta.yaml.in")
    if os.path.isfile(repo_recipe):
        print("\nNOTE: {r} exists, we will build using this recipe.\n".format(r=repo_recipe))
        recipe_file_source = repo_recipe
    else:
        print("\nNOTE: building with feedstock recipe with modified package source\n")
        recipe_file_source = os.path.join(feedstock_dir, 'recipe', 'meta.yaml.SRC')

        cmd = "mv {src} {dest}".format(src=recipe_file, dest=recipe_file_source)
        ret = run_cmd(cmd, join_stderr, shell_cmd, verbose)
        if ret != SUCCESS:
            return ret

    orig_fh = open(recipe_file_source, "r")
    output_fh = open(recipe_file, "w")

    output_fh.write("package:\n")
    output_fh.write("  name: {n}\n".format(n=pkg_name))
    output_fh.write("  version: {v}\n\n".format(v=version))

    output_fh.write("source:\n")
    output_fh.write("  git_rev: {b}\n".format(b=branch))
    output_fh.write("  git_url: {r}\n".format(r=repo_url))

    start_copy = False
    lines = orig_fh.readlines()
    for l in lines:
        match_obj = re.match("build:", l)
        if match_obj:
            start_copy = True
        
        match_build_number = re.match("\s+number:", l)
        if match_build_number:
            output_fh.write("  number: {b}\n".format(b=build))
            continue
        if start_copy:
            output_fh.write(l)
        else:
            continue
    output_fh.close()
    orig_fh.close()

    cmd = "cat {f}".format(f=recipe_file)
    #ret = run_cmd(cmd, join_stderr, shell_cmd, verbose)
    print("CMD: {c}".format(c=cmd))
    os.system(cmd)

    return SUCCESS

def prepare_recipe_in_local_repo(branch, build, version, repo_dir):
    
    recipe_in_file = os.path.join(repo_dir, "recipe", "meta.yaml.in")
    recipe_file = os.path.join(repo_dir, "recipe", "meta.yaml")
    if not os.path.isfile(recipe_in_file):
        print("Cannot find {r} file".format(r=recipe_in_file))
        return FAILURE

    with open(recipe_in_file, "r") as recipe_in_fh:
        s = recipe_in_fh.read()
    s = s.replace("@UVCDAT_BRANCH@", branch)
    s = s.replace("@BUILD_NUMBER@", build)    
    s = s.replace("@VERSION@", version)

    # write it out to recipe/meta.yaml file
    with open(recipe_file, "w") as f:
        f.write(s)

    return SUCCESS

def rerender(dir):
    # pkg_feedstock = "{p}-feedstock".format(p=pkg_name)
    # repo_dir = "{w}/{p}".format(w=workdir, p=pkg_feedstock)

    cmd = "conda smithy rerender"
    ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, dir)
    if ret != SUCCESS:
        return ret
    return ret

def do_build(dir, py_version):
    ret = SUCCESS
    variant_files_dir = os.path.join(dir, ".ci_support")
    if sys.platform == 'darwin':
         variant_files = glob.glob("{d}/.ci_support/osx*{v}.yaml".format(d=dir, v=py_version))
    else:
         variant_files = glob.glob("{d}/.ci_support/linux*{v}.yaml".format(d=dir, v=py_version))

    cmd = "conda build -m {v} recipe/".format(v=variant_files[0])
    ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, dir)
    return ret

def rerender_in_local_feedstock(pkg_name, workdir):
    pkg_feedstock = "{p}-feedstock".format(p=pkg_name)
    repo_dir = os.path.join(workdir, pkg_feedstock)

    ret = rerender(repo_dir)
    if ret != SUCCESS:
        print("FAIL...rerender in {d}".format(d=repo_dir))
    return ret

def build_in_local_feedstock(pkg_name, workdir, py_version):
    pkg_feedstock = "{p}-feedstock".format(p=pkg_name)
    repo_dir = os.path.join(workdir, pkg_feedstock)

    ret = do_build(repo_dir, py_version)
    return ret

def update_variant_files(dir):
    if sys.platform == 'darwin':
        variant_config_files = glob.glob("{d}/.ci_support/osx*.yaml".format(d=dir))
    else:
        variant_config_files = glob.glob("{d}/.ci_support/linux*.yaml".format(d=dir))
    for f in variant_config_files:
        tmp_f = "{fname}.tmp".format(fname=f)
        tmp_fh = open(tmp_f, "w")
        orig_fh = open(f, "r")
        channel_source = False
        for l in orig_fh:
            match_obj = re.match("channel_sources:", l)
            if match_obj:
                channel_source = True
                tmp_fh.write(l)
                continue
            if channel_source:
                tmp_fh.write("- cdat/label/nightly,conda-forge,defaults\n")
                channel_source = False
                continue
            tmp_fh.write(l)
        orig_fh.close()
        tmp_fh.close()
        shutil.move(tmp_f, f)
    return SUCCESS

def rerender_in_local_repo(repo_dir):

    conda_forge_yml = os.path.join(repo_dir, "conda-forge.yml")
    fh = open(conda_forge_yml, "w")
    fh.write("recipe_dir: recipe\n")
    fh.close()

    ret = rerender(repo_dir)
    return ret

    ret = update_variant_files(repo_dir)
    return ret

def build_in_local_repo(repo_dir, py_version):

    ret = do_build(repo_dir, py_version)
    return ret

def rerender_and_build_in_local_repo(repo_dir):
    dir = os.getcwd()

    # since this is not a feedstock repo, we need conda-forge.yml for rerender
    conda_forge_yml = os.path.join(repo_dir, "conda-forge.yml")
    fh = open(conda_forge_yml, "w")
    fh.write("recipe_dir: recipe\n")
    fh.close()

    ret = rerender(repo_dir)
    if ret != SUCCESS:
        return ret

    ret = update_variant_files(repo_dir)

    ret = do_build(repo_dir)
    return ret

#
# main
# Note that when we rerender in a repo, it overwrites .circleci/config.yml in the repo,
# therefore I reclone the repo to be under workdir.
#

is_conda_forge_pkg = check_if_conda_forge_pkg(pkg_name)

if args.do_rerender:
    status = prep_conda_env()
    if status != SUCCESS:
        sys.exit(status)

    ret, repo_dir = clone_repo(repo_name, branch, workdir)
    if ret != SUCCESS:
        sys.exit(ret)

if is_conda_forge_pkg:
    if args.do_rerender:
        status = clone_feedstock(pkg_name, workdir)
        if status != SUCCESS:
            sys.exit(status)

        status = prepare_recipe_in_local_feedstock_repo(pkg_name, repo_name, branch, repo_dir, workdir)
        if status != SUCCESS:
            sys.exit(status)

        status = rerender_in_local_feedstock(pkg_name, workdir)

    if args.do_build:
        status = build_in_local_feedstock(pkg_name, workdir, args.build_version)

else:
    # non conda-forge package (does not have feedstock)

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


