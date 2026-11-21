# Portable Python for the npm launcher

The macOS and Linux launcher checks for Python 3.10 or newer on PATH. It tries python3 first and then python, and tests SQLite and SSL support. macOS skips Apple’s python3 shim if the command-line developer tools are absent.

When neither system command works, the launcher downloads the matching CPython 3.12.16 archive from Astral's pinned November 10, 2026 release. The supported fallback targets are Intel and Apple Silicon Macs, and Linux x64 or ARM64 with glibc 2.17 or later or musl. Each download is about 25–35 MB. The launcher checks the expected byte length and SHA-256 before extraction, probes the extracted interpreter, and atomically places the complete tree under the application data directory’s runtime folder. The first fallback setup needs an internet connection to GitHub and a system tar command with gzip support. Subsequent launches reuse the compatible cached interpreter. [Pinned Astral release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110) · [Upstream runtime requirements](https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.rst)

The launcher asks for a compatible system Python on an unsupported target or when installation fails. Each runtime archive carries its upstream license files. The npm package itself carries the bootstrap code and official checksums.

Checks on the Windows development host verified all six digests against GitHub release metadata. A Node download of the Linux x64 archive passed its size and SHA-256 checks, contained the expected interpreter layout and license file, and was reused from cache. The Unix executable was inspected without running it. The focused unit tests cover platform selection, system probes, cache use, verification failures, and redirect restrictions.

    node --test tests/portable-python.test.mjs
