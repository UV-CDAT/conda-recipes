
import glob
import os
import re
import sys
import shutil
import requests


from Utils import run_cmd, run_cmds, run_cmd_capture_output
from Utils import SUCCESS, FAILURE

# for calling run_cmds
join_stderr = True
shell_cmd = False
verbose = True
not_verbose = False

def get_latest_tag(repo_dir):
    cmd = "git ls-remote --tags origin"

    ret_code, out = run_cmd_capture_output(cmd, join_stderr, shell_cmd, not_verbose, repo_dir)

    latest_release = out[-1]
    print("latest_release: {l}".format(l=latest_release))
    # 2323019125e1e82820370105d5395cb67db2e276 refs/tags/v3.1.4
    match_obj = re.match(r'\S+\s+refs\/tags\/(\S+)', latest_release)
    latest_tag = match_obj.group(1)
    print("release tag: {r}".format(r=match_obj.group(1)))
    return(latest_tag)

def get_asset_sha(org_name, repo_name, tag, workdir):
    url = "https://api.github.com/repos/{o}/{r}/releases/latest".format(o=org_name,                                                                        r=repo_name)
    archive_url = "https://github.com/{o}/{r}/archive/".format(o=org_name,
                                                              r=repo_name)
    c1 = "curl --silent \"{u}\" | grep '\"tag_name\":' |  sed -E 's/.*\"([^\"]+)\".*/\\1/'".format(u=url)
    c2 = "| xargs -I {{}} curl -sOL \"{au}\"{{}}'.tar.gz'".format(au=archive_url)

    cmd = "cd {d} && {c1} {c2}".format(d=workdir, c1=c1, c2=c2)
    print("CMD: {c}".format(c=cmd))
    os.system(cmd)

    asset_file = "{f}.tar.gz".format(f=os.path.join(workdir, tag))
    if os.path.isfile(asset_file):
        print("Successfully downloaded {f}".format(f=asset_file))
    else:
        print("FAIL to download the asset file")
        return FAILURE

    cmd = "shasum -a 256 {f}".format(f=asset_file)
    ret_code, output = run_cmd_capture_output(cmd)
    if ret_code != SUCCESS:
        return ret_code
    sha = output[0]
    print("sha: {v}".format(v=sha))
    return sha

def prep_conda_env(to_do_conda_clean=False):
    if to_do_conda_clean:
        cmd = "conda clean --all"
        ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, workdir)

    pkgs = "conda-build anaconda-client conda-smithy conda-verify conda-forge-pinning conda-forge-build-setup conda-forge-ci-setup"
    cmds = [
        #"conda update -y -q conda",
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

def clone_repo(organization, repo_name, branch, workdir):
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

def prepare_recipe_in_local_feedstock_repo(pkg_name, organization, repo_name, branch, pkg_version, build, repo_dir, workdir):
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
    output_fh.write("  version: {v}\n\n".format(v=pkg_version))

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

    cmd = "cat {f}".format(f=recipe_file)
    print("CMD: {c}".format(c=cmd))
    os.system(cmd)

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
    print("...do_build...")
    ret = SUCCESS
    variant_files_dir = os.path.join(dir, ".ci_support")
    if py_version == "noarch":
        variant_file = os.path.join(variant_files_dir, "linux_.yaml")
        cmd = "conda build -m {v} recipe/".format(v=variant_file)
        ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, dir)
    else:
        if sys.platform == 'darwin':
            variant_files = glob.glob("{d}/.ci_support/osx*{v}*.yaml".format(d=dir, v=py_version))
        else:
            variant_files = glob.glob("{d}/.ci_support/linux*{v}*.yaml".format(d=dir, v=py_version))
 
        for variant_file in variant_files:
            cmd = "conda build -m {v} recipe/".format(v=variant_file)
            ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, dir)
            if ret != SUCCESS:
                print("FAIL: {c}".format(c=cmd))
                break

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

    print("...build_in_local_repo...")
    ret = do_build(repo_dir, py_version)
    return ret



#latest_tag = get_latest_tag("/Users/muryanto1/work/release/cdms")
#print("xxx latest_tag: {t}".format(t=latest_tag))

#ret_code = get_asset_sha("CDAT", "cdms", latest_tag, "/Users/muryanto1/work/release/workdir")
