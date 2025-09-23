# filename_pattern.py
# holds helper to create a regex pattern for all supported distros.
# If you want to implement another distros image you need to create a pattern
# to match the image filename to extract metadata information or simply check
# if the image exists and build its url

import re


def get_filename_pattern(image_data: dict, log_prefix: str) -> re.Pattern:
    """ Creates a regex pattern to match a specific image.
        If there is no image defined for image_data['distro'] an exception
        will be raised.
    """
    if image_data["distro"] in ["AlmaLinux", "Rocky"]:
        # Example: Rocky-8-GenericCloud-Base-8.10-20240528.0.x86_64.qcow2
        # Example: AlmaLinux-9-GenericCloud-9.6-20250522.x86_64.qcow2
        return re.compile(
            fr"{image_data['distro']}-(\d+)-"
            fr"{image_data['usage']}-"
            fr"(\d+)\.(\d+)-((\d+)|(\d+)\.(\d+))\."
            fr"{image_data['arch']}\."
            fr"{image_data['extension']}$"
        )
    elif image_data["distro"] == "debian":
        # Example: debian-11-genericcloud-amd64-20250801-2191.qcow2
        return re.compile(
            fr"{image_data['distro']}-(\d+)-"
            fr"{image_data['usage']}-{image_data['arch']}-"
            fr"((\d{8})-\d+)\.{image_data['extension']}$"
        )
    elif image_data["distro"] == "ubuntu":
        # Example: ubuntu-24.04-server-cloudimg-amd64.img
        return re.compile(
            fr"{image_data['distro']}-{image_data['version']}-"
            fr"{image_data['usage']}-{image_data['arch']}\."
            fr"{image_data['extension']}$"
        )
    elif image_data["distro"] == "flatcar":
        # Example: flatcar_production_openstack_image.img.bz2
        return re.compile(
            fr"{image_data['distro']}_{image_data['version']}_"
            fr"{image_data['usage']}\.{image_data['extension']}$"
        )
    elif image_data["distro"] == "Fedora":
        # Example: Fedora-Cloud-Base-Generic-42-1.1.x86_64.qcow2
        return re.compile(
            fr"{image_data['distro']}-{image_data['usage']}-"
            fr"((\d+)-(\d+)\.(\d+)\.{image_data['arch']}\."
            fr"{image_data['extension']}$"
        )
    else:
        raise NotImplementedError(
            f"{log_prefix} filename pattern not implemented!"
        )


def get_release_folder_pattern(image_data: dict, log_prefix: str) -> re.Pattern:
    """ Creates a regex pattern to match the dated release folders of a release
        if you want to search for it instead of using fixed release folder.
    """
    if image_data["distro"] == "flatcar":
        # Example: ./4230.2.3/
        return re.compile(r".*?(\d+\.\d+\.\d+)\/$")
    elif image_data["distro"] == "debian":
        # Example: 20250909-2230/
        return re.compile(r".*?(\d{8})-(\d+)\/$")
    elif image_data["distro"] == "ubuntu":
        # Example: 20250801-2191/
        return re.compile(r".*?release-(\d{8})\/$")
    else:
        raise NotImplementedError(
            f"{log_prefix} folder pattern not implemented!"
        )


def get_checksum_search_pattern(
    image_data: dict, distribution: str
) -> re.Pattern:
    """ Create regex pattern to match correct checksum line in checksum file
    """
    if image_data["distro"] == "Fedora":
        # Example: Fedora-Cloud-Base-Generic-42-1.1.x86_64.qcow2
        return re.compile(
            fr"^[^#].*?{image_data['distro']}.*?{image_data['usage']}"
            fr".*?{image_data['arch']}.*?{image_data['extension']}.*?$"
        )
    elif image_data["distro"] == "flatcar":
        # Example: flatcar_production_openstack_image.img.gz
        return re.compile(
            fr"^[^#].*?{image_data['distro']}.*?{image_data['version']}"
            fr".*?{image_data['usage']}.*?{image_data['extension']}.*?$"
        )
    elif image_data["distro"] in ["AlmaLinux", "Rocky"]:
        # Example: Rocky-8-GenericCloud-Base.latest.x86_64.qcow2
        return re.compile(
            fr"^[^#].*?{image_data['distro']}.*?{image_data['version']}"
            fr".*?{image_data['usage']}.*?{image_data['version']}"
            fr".*?{image_data['arch']}.*?{image_data['extension']}.*?$"
        )
    elif image_data["distro"] in ["debian", "ubuntu"]:
        # Example: debian-12-genericcloud-amd64-20250909-2230.qcow2'
        return re.compile(
            fr"^[^#].*?{image_data['distro']}.*?{image_data['version']}"
            fr".*?{image_data['usage']}.*?{image_data['arch']}"
            fr".*?{image_data['extension']}.*?$"
        )
    else:
        raise NotImplementedError(
            f"{distribution} {image_data['name']} checksum pattern not "
            "implemented!"
        )


def get_checksum_pattern(algorithm: str) -> re.Pattern:
    """ Create regex pattern to match for a checksum.
        the checksum depends on the length which depends on the algorithm
    """
    if algorithm == "md5":
        # md5 hash is always 32 chars long
        checksum_length = 32
    elif algorithm == "sha256":
        # md5 hash is always 64 chars long
        checksum_length = 64
    elif algorithm == "sha512":
        # md5 hash is always 128 chars long
        checksum_length = 128
    else:
        raise NotImplementedError(
            f"{algorithm} not implemented. checksum_pattern not able to be "
            " created. Please make sure to implement"
        )
    # Uses {{{...}}} to create a pattern like [A-Fa-f0-9]{64}
    # double { and } are used to escape { and } in f-strings
    return re.compile(fr".*?([A-Fa-f0-9]{{{checksum_length}}}).*?$")
