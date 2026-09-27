"""Application identity and installed package metadata."""

from importlib.metadata import metadata


DISTRIBUTION_NAME = "photo-album"
APPLICATION_NAME = "Photo Album"
USER_AGENT_NAME = "PhotoAlbum"

_metadata = metadata(DISTRIBUTION_NAME)

VERSION = _metadata["Version"]
AUTHOR = _metadata["Author"]
ORGANIZATION_NAME = AUTHOR


def user_agent() -> str:
    """Return the HTTP User-Agent used by Photo Album."""
    return f"{USER_AGENT_NAME}/{VERSION}"
