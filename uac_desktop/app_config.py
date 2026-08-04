from . import __version__


# The repository was renamed from UAC-SNI-Spoofer-Windows. GitHub still
# redirects the old path, but its API answers with the new name — keep this
# in step with the rename or every update check fails validation.
UPDATE_REPOSITORY_URL = "https://github.com/cubepy/CubeWin"
CURRENT_VERSION = __version__


def github_latest_release_api(repository_url: str) -> str:
    value = repository_url.rstrip("/")
    marker = "github.com/"
    slug = value.split(marker, 1)[1] if marker in value else "OWNER/REPOSITORY"
    return f"https://api.github.com/repos/{slug}/releases/latest"


GITHUB_RELEASES_URL = f"{UPDATE_REPOSITORY_URL.rstrip('/')}/releases"
LATEST_VERSION_URL = github_latest_release_api(UPDATE_REPOSITORY_URL)
UPDATE_CHECK_ENDPOINT = LATEST_VERSION_URL
PORTABLE_DOWNLOAD_URL = (
    f"{GITHUB_RELEASES_URL}/latest/download/"
    f"CubeVPN-v{CURRENT_VERSION}-Windows-x64-portable.zip"
)
PROJECT_URL = UPDATE_REPOSITORY_URL

# Base URL of the CubeVPN account API (see docs/api-contract.md in the CubeVPN
# Android repo — this client talks to the same three endpoints:
# requestcode.php / verifycode.php / accountme.php).
#
# Left empty in source control on purpose. The release workflow
# (.github/workflows/release-cubevpn-windows.yml) replaces the value below at
# build time from a repo secret, the same way the Android app injects
# API_BASE_URL from secrets.properties and the CubeVPN Windows/WPF client
# injects it into CubeApiConfig.cs.
CUBE_API_BASE_URL = ""
