import sys
import json
import argparse

parser = argparse.ArgumentParser(
    description='conda build upload',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-r", "--cdat_release",
                    help="cdat_release_version, ex: 8.2.1")
parser.add_argument("-t", "--package_type",
                    help="'cdat' or 'conda-forge' package")
parser.add_argument("-p", "--package_name",
                    help="Package name to build")
parser.add_argument("-f", "--release_info_json_file_name",
                    help="release_info.json full path name")

args = parser.parse_args(sys.argv[1:])

cdat_release = args.cdat_release
package_type = args.package_type
package_name = args.package_name
release_info_file = args.release_info_json_file_name


with open(release_info_file) as json_file:
    release_info = json.load(json_file)
    pkg_info = release_info[cdat_release][package_type][package_name]
    version = pkg_info['version']
    build = pkg_info['build']
    type = pkg_info['type']
    ret_info = "{v}:{b}:{t}".format(v=version, b=build, t=type)
    print(ret_info)

