"""Container definition for the MariaDB database server and client."""

from pathlib import Path

from bci_build.package import ALL_NONBASE_OS_VERSIONS
from bci_build.package import CAN_BE_LATEST_OS_VERSION
from bci_build.package import DOCKERFILE_RUN
from bci_build.package import ApplicationStackContainer
from bci_build.package import BuildType
from bci_build.package import OsVersion
from bci_build.package import SupportLevel
from bci_build.package import generate_disk_size_constraints
from bci_build.package.helpers import generate_package_version_check
from bci_build.package.versions import get_pkg_version
from bci_build.package.versions import to_major_minor_version

_MARIADB_ENTRYPOINT = (Path(__file__).parent / "mariadb" / "entrypoint.sh").read_bytes()
_MARIADB_HEALTHCHECK = (
    Path(__file__).parent / "mariadb" / "healthcheck.sh"
).read_bytes()
_MARIADB_GOSU = b"""#!/bin/bash

u=$1
shift

if ! id -u $u > /dev/null 2>&1; then
    echo "Invalid user: $u"
    exit 1
fi

setpriv --reuid=$u --regid=$u --clear-groups -- /bin/bash "$@"
"""

MARIADB_CONTAINERS = []
MARIADB_CLIENT_CONTAINERS = []


for os_version in ALL_NONBASE_OS_VERSIONS:  # + [OsVersion.BASALT]:
    mariadb_version = to_major_minor_version(get_pkg_version("mariadb", os_version))
    if os_version in (OsVersion.BASALT, OsVersion.TUMBLEWEED):
        prefix = ""
        additional_names = []
    else:
        prefix = "rmt-"
        additional_names = ["mariadb"]

    version_check_lines = generate_package_version_check(
        "mariadb-client", mariadb_version
    )

    MARIADB_CONTAINERS.append(
        ApplicationStackContainer(
            package_name=f"{prefix}mariadb-image",
            additional_names=additional_names,
            os_version=os_version,
            is_latest=os_version in CAN_BE_LATEST_OS_VERSION,
            name=f"{prefix}mariadb",
            version=mariadb_version,
            version_in_uid=False,
            pretty_name="MariaDB Server",
            package_list=[
                "mariadb",
                "mariadb-tools",
                "gawk",
                "timezone",
                "util-linux",
                "findutils",
            ],
            entrypoint=["docker-entrypoint.sh"],
            extra_files={
                "docker-entrypoint.sh": _MARIADB_ENTRYPOINT,
                "healthcheck.sh": _MARIADB_HEALTHCHECK,
                "gosu": _MARIADB_GOSU,
                "_constraints": generate_disk_size_constraints(11),
            },
            support_level=SupportLevel.L3,
            build_recipe_type=BuildType.DOCKER,
            cmd=["mariadbd"],
            volumes=["/var/lib/mysql"],
            exposes_tcp=[3306],
            custom_end=rf"""{version_check_lines}

{DOCKERFILE_RUN} mkdir /docker-entrypoint-initdb.d

# docker-entrypoint from https://github.com/MariaDB/mariadb-docker.git
COPY docker-entrypoint.sh /usr/local/bin/
{DOCKERFILE_RUN} chmod 755 /usr/local/bin/docker-entrypoint.sh
{DOCKERFILE_RUN} ln -s usr/local/bin/docker-entrypoint.sh / # backwards compat

# healthcheck from https://github.com/MariaDB/mariadb-docker.git
COPY healthcheck.sh /usr/local/bin/
{DOCKERFILE_RUN} chmod 755 /usr/local/bin/healthcheck.sh

COPY gosu /usr/local/bin/gosu
{DOCKERFILE_RUN} chmod 755 /usr/local/bin/gosu

{DOCKERFILE_RUN} sed -i -e 's,$(pwgen .*),$(openssl rand -base64 36),' /usr/local/bin/docker-entrypoint.sh

# Ensure all logs goes to stdout
{DOCKERFILE_RUN} sed -i 's/^log/#log/g' /etc/my.cnf

# Disable binding to localhost only, doesn't make sense in a container
{DOCKERFILE_RUN} sed -i -e 's|^\(bind-address.*\)|#\1|g' /etc/my.cnf

{DOCKERFILE_RUN} mkdir /run/mysql
""",
        )
    )

    MARIADB_CLIENT_CONTAINERS.append(
        ApplicationStackContainer(
            package_name=f"{prefix}mariadb-client-image",
            os_version=os_version,
            is_latest=os_version in CAN_BE_LATEST_OS_VERSION,
            version_in_uid=False,
            name=f"{prefix}mariadb-client",
            additional_names=[f"{name}-client" for name in additional_names],
            version=mariadb_version,
            pretty_name="MariaDB Client",
            support_level=SupportLevel.L3,
            package_list=["mariadb-client"],
            build_recipe_type=BuildType.DOCKER,
            cmd=["mariadb"],
            custom_end=version_check_lines,
        )
    )
