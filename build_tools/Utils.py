import os
import subprocess
import shlex
import shutil
import time

SUCCESS = 0
FAILURE = 1

def run_command(cmd, join_stderr=True, shell_cmd=False, verbose=True, cwd=None):
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
                                                                                              
def run_cmd(cmd, join_stderr=True, shell_cmd=False, verbose=True, cwd=None):

    ret_code, output = run_command(cmd, join_stderr, shell_cmd, verbose, cwd)
    return(ret_code)

def run_cmds(cmds, join_stderr=True, shell_cmd=False, verbose=True, cwd=None):
    for cmd in cmds:
        ret_code, output = run_command(cmd, join_stderr, shell_cmd, verbose, cwd)
        if ret_code != SUCCESS:
            return ret_code
    return ret_code

def run_cmd_capture_output(cmd, join_stderr=True, shell_cmd=False, verbose=True, cwd=None):

    ret_code, output = run_command(cmd, join_stderr, shell_cmd, verbose, cwd)
    return(ret_code, output)

