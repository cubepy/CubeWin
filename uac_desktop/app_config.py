from . import __version__


# The repository was renamed from UAC-SNI-Spoofer-Windows. GitHub still
# redirects the old path, but its API answers with the new name — keep this
# in step with the rename or every update check fails validation.
UPDATE_REPOSITORY_URL = "https://github.com/cubepy/CubeWin"
CURRENT_VERSION = __version__


GITHUB_RELEASES_URL = f"{UPDATE_REPOSITORY_URL.rstrip('/')}/releases"
PROJECT_URL = UPDATE_REPOSITORY_URL

# Removed: PORTABLE_DOWNLOAD_URL, LATEST_VERSION_URL, UPDATE_CHECK_ENDPOINT and
# github_latest_release_api(). Nothing referenced them, and the download URL
# was built from the version constant into a filename the release workflow
# never produces (it packages CubeVPN-windows-x64.zip), so anyone who wired it
# up would have got a 404. update_checker.GitHubRepository derives the real API
# and release URLs from UPDATE_REPOSITORY_URL.

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
