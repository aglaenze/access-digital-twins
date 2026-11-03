"""NICOS setup package of the ACCESS digital twins (one sub-package per instrument, e.g. nicos_twin.odin)."""


def determine_instrument(setup_package_path):
    """Default instrument when INSTRUMENT only names the package."""
    return 'odin'
