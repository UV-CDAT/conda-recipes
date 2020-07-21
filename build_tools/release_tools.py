
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

def get_git_rev(repo_dir):
    cmd = "git rev-parse --short HEAD"
    ret_code, out = run_cmd_capture_output(cmd, join_stderr, shell_cmd, not_verbose, repo_dir)
    git_rev = "g{r}".format(r=out[0])
    return(git_rev)

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

def prep_conda_env(conda_activate, conda_rc, conda_env, extra_channels, to_do_conda_clean=False, **kwargs):
    # Remove existing condarc so environment is always fresh
    if os.path.exists(conda_rc):
        os.remove(conda_rc)

    env = {"CONDARC": conda_rc}

    base_config_cmd = "conda config --file {}".format(conda_rc)

    cmds = [
        "{} --set always_yes yes".format(base_config_cmd),
        "{} --set channel_priority strict".format(base_config_cmd),
        "{} --set anaconda_upload no".format(base_config_cmd),
        "{} --add channels conda-forge --force".format(base_config_cmd),
    ]

    channels = ["{} --add channels {} --force".format(base_config_cmd, x) for x in reversed(extra_channels)]

    ret = run_cmds(cmds+channels)

    cmd = "source {} {}; conda info".format(conda_activate, conda_env)
    ret = run_cmd(["/bin/bash", "-c", cmd], env=env)

    if conda_env != "base":
        cmd = "source {} base; conda env remove -n {} -y".format(conda_activate, conda_env)
        ret = run_cmd(["/bin/bash", "-c", cmd], env=env)

    pkgs = "conda-build anaconda-client conda-smithy conda-verify conda-forge-pinning conda-forge-build-setup conda-forge-ci-setup"

    if conda_env == "base":
        cmd = "source {} base; conda install -y {}".format(conda_activate, pkgs)
        ret = run_cmd(["/bin/bash", "-c", cmd], env=env)
    else:
        cmd = "source {} base; conda create -n {} -y {}".format(conda_activate, conda_env, pkgs)
        ret = run_cmd(["/bin/bash", "-c", cmd], env=env)

    if to_do_conda_clean:
        cmd = "source {} {}; conda clean --all".format(conda_activate, conda_env)
        ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, workdir, env=env)

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

def clone_feedstock(package_name, workdir, **kwargs):
    pkg_feedstock = "{p}-feedstock".format(p=package_name)
    conda_forge_pkg_feedstock = "conda-forge/{p}".format(p=pkg_feedstock)

    feedstock_repo_dir = os.path.join(workdir, pkg_feedstock)
    if os.path.exists(feedstock_repo_dir):
        print("REMOVING existing {d}".format(d=feedstock_repo_dir))
        shutil.rmtree(feedstock_repo_dir)

    cmd = "git clone https://github.com/{c}.git".format(c=conda_forge_pkg_feedstock)
    ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, workdir)

    return ret

def clone_repo(organization, repo_name, branch, workdir, **kwargs):
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

def prepare_recipe_in_local_feedstock_repo(package_name, organization, repo_name, branch, pkg_version, build, repo_dir, workdir, local_repo, **kwargs):
    repo_url = "https://github.com/{o}/{r}.git\n\n".format(o=organization,r=repo_name)

    pkg_feedstock = "{p}-feedstock".format(p=package_name)
    feedstock_dir = os.path.join(workdir, pkg_feedstock)
    recipe_file = os.path.join(feedstock_dir, 'recipe', 'meta.yaml')

    #
    # if repo has a recipe/meta.yaml.in, this means the branch is updating
    # the recipe, use this recipe to build.
    # NOTE: when we build the package for conda-forge, we will need to
    # merge this recipe to feedstock and delete the recipe from the repo.
    #
    repo_recipe = os.path.join(repo_dir, "recipe", "meta.yaml.in")

    #
    # if branch name starts with 'for_release', we are building a non conda-forge
    # package for a release, and the branch should have the recipe ready for
    # rerender, so just copy over to the fake feedstock.
    #
    for_release = branch.startswith("for_release")
    if for_release:
        shutil.copyfile(repo_recipe, recipe_file)
        return SUCCESS

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

    start_copy = True
    lines = orig_fh.readlines()
    for l in lines:
        match_obj = re.match("package:", l)
        if match_obj:
            start_copy = False
            output_fh.write("package:\n")
            output_fh.write("  name: {n}\n".format(n=package_name))
            output_fh.write("  version: {v}\n\n".format(v=pkg_version))

            output_fh.write("source:\n")

            if local_repo is None:
                output_fh.write("  git_rev: {b}\n".format(b=branch))
                output_fh.write("  git_url: {r}\n".format(r=repo_url))
            else:
                output_fh.write("  path: {}\n".format(local_repo))

            continue

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

def prepare_recipe_in_local_repo(branch, build, version, repo_dir, local_repo, **kwargs):
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

    if local_repo is not None:
        s = re.sub(".*git_.*", "", s)
        s = re.sub("source:.*", "source:\n  path: {}\n".format(local_repo), s)

    # write it out to recipe/meta.yaml file
    with open(recipe_file, "w") as f:
        f.write(s)

    cmd = "cat {f}".format(f=recipe_file)
    print("CMD: {c}".format(c=cmd))
    os.system(cmd)

    return SUCCESS

def copy_file_from_repo(package_name, repo_dir, workdir, filename, **kwargs):

    print("...copy_file_from_repo(), filename: {f}".format(f=filename))
    ret = SUCCESS
    the_file = os.path.join(repo_dir, filename)
    print("...the_file: {f}".format(f=the_file))
    if os.path.isfile(the_file):
        print("{f} exists in repo".format(f=the_file))
        pkg_feedstock = "{p}-feedstock".format(p=package_name)
        feedstock_dest_dir = os.path.dirname(os.path.join(workdir, pkg_feedstock, filename))
        if not os.path.exists(feedstock_dest_dir):
            print("...making {d}".format(d=feedstock_dest_dir))
            os.makedirs(feedstock_dest_dir)

        cmd = "cp {f} {d}".format(f=the_file,
                                  d=feedstock_dest_dir)
        #print("CMD: {c}".format(c=cmd))
        #os.system(cmd)
        ret = run_cmd(cmd, join_stderr, shell_cmd, verbose, workdir)
    else:
        print("No {f} in repo".format(f=the_file))
    return ret

def copy_files_from_repo(package_name, repo_dir, workdir, filenames, **kwargs):

    print("...copy_files_from_repo()...")
    for f in filenames:
        print("DEBUG...file: {f}".format(f=f))
        ret = copy_file_from_repo(package_name, repo_dir, workdir, f, **kwargs)
        if ret != SUCCESS:
            print("FAIL in copying {f}".format(f=f))
            return ret

    return SUCCESS

def rerender(conda_activate, conda_env, conda_rc, dir, **kwargs):
    # pkg_feedstock = "{p}-feedstock".format(p=pkg_name)
    # repo_dir = "{w}/{p}".format(w=workdir, p=pkg_feedstock)

    env = {"CONDARC": conda_rc}

    print("Doing...'conda smithy rerender'...under {d}".format(d=dir))
    cmd = "source {} {}; conda info; conda smithy rerender".format(conda_activate, conda_env)
    if kwargs["ignore_conda_missmatch"]:
        cmd = "{!s} --no-check-uptodate".format(cmd)
    ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, dir, env=env)

    if ret != SUCCESS:
        sys.exit(ret)

    cmd = "ls -l {d}".format(d=os.path.join(dir, ".ci_support"))
    run_cmd(cmd, join_stderr, shell_cmd, verbose, dir)
    return ret

def do_build(conda_activate, conda_env, conda_rc, dir, py_version, copy_conda_package, extra_channels, **kwargs):
    print("...do_build..., py_version: {v}, dir: {d}".format(v=py_version,
                                                             d=dir))
    ret = SUCCESS
    env = {"CONDARC": conda_rc}
    variant_files_dir = os.path.join(dir, ".ci_support")
    if py_version == "noarch":
        variant_file = os.path.join(variant_files_dir, "linux_.yaml")
        cmd = "source {} {}; conda build {} -m {} recipe/".format(conda_activate, conda_env, extra_channels, variant_file)
        ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, dir, env=env)

        if copy_conda_package is not None:
            cmd = "source {} {}; output=$(conda build --output -m {} recipe/); cp $output {}".format(
                    conda_activate, conda_env, variant_file, copy_conda_package)
            ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, dir, env=env)
    else:
        if sys.platform == 'darwin':
            variant_files = glob.glob("{d}/.ci_support/osx*{v}*.yaml".format(d=dir, v=py_version))
        else:
            variant_files = glob.glob("{d}/.ci_support/linux*{v}*.yaml".format(d=dir, v=py_version))

        for variant_file in variant_files:
            cmd = "source {} {}; conda build {} -m {} recipe/".format(conda_activate, conda_env, extra_channels, variant_file)
            ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, dir, env=env)
            if ret != SUCCESS:
                print("FAIL: {c}".format(c=cmd))
                break
            if copy_conda_package is not None:
                cmd = "source {} {}; output=$(conda build --output -m {} recipe/); mkdir -p {}; cp $output {}".format(
                        conda_activate, conda_env, variant_file, copy_conda_package, copy_conda_package)
                ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, dir, env=env)

    return ret

def rerender_in_local_feedstock(package_name, workdir, **kwargs):
    pkg_feedstock = "{p}-feedstock".format(p=package_name)
    repo_dir = os.path.join(workdir, pkg_feedstock)

    ret = rerender(dir=repo_dir, **kwargs)
    if ret != SUCCESS:
        print("FAIL...rerender in {d}".format(d=repo_dir))
    return ret

def build_in_local_feedstock(package_name, workdir, build_version, **kwargs):
    pkg_feedstock = "{p}-feedstock".format(p=package_name)
    repo_dir = os.path.join(workdir, pkg_feedstock)

    ret = do_build(dir=repo_dir, py_version=build_version, **kwargs)
    return ret

def rerender_in_local_repo(repo_dir, **kwargs):

    conda_forge_yml = os.path.join(repo_dir, "conda-forge.yml")
    fh = open(conda_forge_yml, "w")
    fh.write("recipe_dir: recipe\n")
    fh.close()

    ret = rerender(dir=repo_dir, **kwargs)
    return ret

    ret = update_variant_files(repo_dir)
    return ret

def build_in_local_repo(repo_dir, build_version, **kwargs):

    print("...build_in_local_repo...")
    ret = do_build(dir=repo_dir, py_version=build_version, **kwargs)
    return ret

def find_conda_activate():
    activate = None

    if "CONDA_EXE" in os.environ:
        m = re.match("(.*/conda/bin)/conda", os.environ["CONDA_EXE"])

        if m is not None:
            activate = os.path.join(m.group(1), "activate")
    else:
        glob_paths = (os.path.join(os.path.expanduser("~"), "*conda*/bin/activate"), "/opt/*conda*/bin/activate")
        for x in glob_paths:
            result = glob.glob(x)

            if len(result) > 0:
                activate = result[0]

                break

    return activate

def create_fake_feedstock(conda_activate, conda_env, workdir, repo_dir, package_name, **kwargs):
    feedstock_dir = os.path.join(workdir, "{}-feedstock".format(package_name))

    if not os.path.exists(feedstock_dir):
        os.makedirs(feedstock_dir)

    cmd = "source {} {}; conda smithy ci-skeleton {}".format(conda_activate, conda_env, feedstock_dir)
    ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, feedstock_dir)

    cmd = "cp {}/recipe/* {}/recipe".format(repo_dir, feedstock_dir)
    ret = run_cmd(["/bin/bash", "-c", cmd], join_stderr, shell_cmd, verbose, repo_dir)

    return feedstock_dir

#latest_tag = get_latest_tag("/Users/muryanto1/work/release/cdms")
#print("xxx latest_tag: {t}".format(t=latest_tag))

#ret_code = get_asset_sha("CDAT", "cdms", latest_tag, "/Users/muryanto1/work/release/workdir")
