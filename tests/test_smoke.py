from comercial_andina import __version__


def test_package_version() -> None:
    """The project package exposes a valid initial version."""
    assert __version__ == "0.1.0"
