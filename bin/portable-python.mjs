import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { createWriteStream } from "node:fs";
import { access, lstat, mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { promisify } from "node:util";

const runFile = promisify(execFile);
const VERSION = "3.12.16";
const RELEASE = "20261110";
const ASSETS = {
  "aarch64-apple-darwin": [25237581, "2f11b8aa3726bdbd87dd9eb76568412faddf4f47e26913fa45d6a2e424972acd"],
  "x86_64-apple-darwin": [24957926, "b78a4c479f1964ec484880bee567568266f68da102269fb93a05fe8716b45f91"],
  "aarch64-unknown-linux-gnu": [29440910, "b6a41defec4975d94b4ff1950236e7383e5c02ba40ea48c9ec33c66087a35aab"],
  "x86_64-unknown-linux-gnu": [34709145, "6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39"],
  "aarch64-unknown-linux-musl": [28552582, "64bb304e59d5d6ed5eaae24e95e743a2420a8897d2f6c854b1438ff9cb47e432"],
  "x86_64-unknown-linux-musl": [28193015, "e32685cf248d2f33b249816120774143b4b57578cb30de5b8dba3e54963765c3"],
};
const DOWNLOAD_HOSTS = new Set([
  "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
]);
const RUN_OPTIONS = { encoding: "utf8", timeout: 5000, maxBuffer: 65536, windowsHide: true };
const PROBE = [
  "import sqlite3, ssl, sys",
  "assert sys.version_info[:2] >= (3, 10)",
  "assert sqlite3.connect(':memory:').execute('SELECT 1').fetchone() == (1,)",
  "assert ssl.OPENSSL_VERSION",
].join("\n");
const RECOVERY = "Install Python 3.10 or later with sqlite3 and ssl, then make python3 available on PATH.";
const RECEIPT = ".loot-atlas-runtime-sha256";

async function compatible(command, run) {
  try {
    await run(command, ["-I", "-B", "-c", PROBE], RUN_OPTIONS);
    return true;
  } catch {
    return false;
  }
}

async function commandOutput(command, args, run) {
  try {
    const result = await run(command, args, RUN_OPTIONS);
    return [result.stdout, result.stderr].filter(Boolean).join("\n");
  } catch (error) {
    // musl's ldd reports its version on stderr and may return a nonzero status.
    return [error.stdout, error.stderr].filter(Boolean).join("\n");
  }
}

async function systemPython(platform, run) {
  for (const command of ["python3", "python"]) {
    if (platform === "darwin" && command === "python3") {
      const path = (await commandOutput("which", [command], run)).trim();
      if (path === "/usr/bin/python3" && !(await commandOutput("/usr/bin/xcode-select", ["-p"], run)).trim().startsWith("/"))
        continue;
    }
    if (await compatible(command, run)) return command;
  }
  return null;
}

async function targetFor(platform, arch, run) {
  const cpu = { x64: "x86_64", arm64: "aarch64" }[arch];
  if (!cpu || !["darwin", "linux"].includes(platform))
    throw new Error("No portable Python build is provided for " + platform + "/" + arch + ". " + RECOVERY);
  if (platform === "darwin") return cpu + "-apple-darwin";

  const conf = await commandOutput("getconf", ["GNU_LIBC_VERSION"], run);
  const [, major, minor] = conf.match(/glibc\s+(\d+)\.(\d+)/i) || [];
  if (major) {
    if (Number(major) === 2 && Number(minor) < 17)
      throw new Error("Portable Python requires glibc 2.17 or newer on this GNU/Linux host. " + RECOVERY);
    return cpu + "-unknown-linux-gnu";
  }
  const ldd = await commandOutput("ldd", ["--version"], run);
  if (/\bmusl\b/i.test(ldd)) return cpu + "-unknown-linux-musl";
  const [, oldMajor, oldMinor] = ldd.match(/(?:glibc|GNU libc|GNU C Library)[^\n]*?\b(\d+)\.(\d+)\b/i) || [];
  if (oldMajor) {
    if (Number(oldMajor) === 2 && Number(oldMinor) < 17)
      throw new Error("Portable Python requires glibc 2.17 or newer on this GNU/Linux host. " + RECOVERY);
    return cpu + "-unknown-linux-gnu";
  }
  try {
    await access("/lib/ld-musl-" + cpu + ".so.1");
    return cpu + "-unknown-linux-musl";
  } catch {
    throw new Error("The Linux C library could not be identified as glibc or musl. " + RECOVERY);
  }
}

async function downloadArchive(target, destination, fetcher) {
  const [expectedBytes, expectedHash] = ASSETS[target];
  const archive = "cpython-" + VERSION + "+" + RELEASE + "-" + target + "-install_only_stripped.tar.gz";
  let url = new URL("https://github.com/astral-sh/python-build-standalone/releases/download/" +
                    RELEASE + "/" + archive);
  const signal = AbortSignal.timeout(90000);
  for (let hop = 0; hop < 5; hop++) {
    if (url.protocol !== "https:" || url.port || url.username || url.password || !DOWNLOAD_HOSTS.has(url.hostname))
      throw new Error("Portable Python download was redirected outside approved GitHub release hosts.");
    const response = await fetcher(url, {
      signal, redirect: "manual", headers: { "Accept-Encoding": "identity", "User-Agent": "GTA6-Loot-Map" },
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      await response.body?.cancel();
      const location = response.headers.get("location");
      if (!location) throw new Error("GitHub did not supply a release-asset destination.");
      url = new URL(location, url);
      continue;
    }
    if (response.status !== 200 || !response.body) {
      await response.body?.cancel();
      throw new Error("GitHub returned HTTP " + response.status + " for the pinned Python archive.");
    }
    const contentLength = response.headers.get("content-length");
    if (contentLength !== null && Number(contentLength) !== expectedBytes) {
      await response.body.cancel();
      throw new Error("Portable Python download did not have the expected size.");
    }
    let bytes = 0;
    const sha = createHash("sha256");
    const meter = new Transform({
      transform(chunk, encoding, done) {
        bytes += chunk.length;
        if (bytes > expectedBytes) {
          done(new Error("Portable Python download exceeded the expected size."));
          return;
        }
        sha.update(chunk);
        done(null, chunk);
      },
    });
    await pipeline(Readable.fromWeb(response.body), meter,
                   createWriteStream(destination, { flags: "wx", mode: 0o600 }), { signal });
    if (bytes !== expectedBytes || sha.digest("hex") !== expectedHash)
      throw new Error("Portable Python archive failed SHA-256 verification.");
    return;
  }
  throw new Error("GitHub returned too many release-asset redirects.");
}

const interpreter = (directory) => join(directory, "bin", "python3");

async function usableInstall(directory, hash, run) {
  try {
    if (!(await lstat(directory)).isDirectory()) return false;
    const path = join(directory, RECEIPT);
    const receipt = await lstat(path);
    if (!receipt.isFile() || receipt.size !== 65 || (await readFile(path, "utf8")) !== hash + "\n") return false;
    return compatible(interpreter(directory), run);
  } catch {
    return false;
  }
}

export async function findUnixPython(dataDir, {
  platform = process.platform, arch = process.arch, run = runFile, fetcher = fetch,
  notify = (message) => process.stderr.write(message + "\n"),
} = {}) {
  const system = await systemPython(platform, run);
  if (system) return system;

  const target = await targetFor(platform, arch, run);
  const [bytes, hash] = ASSETS[target];
  const root = join(resolve(dataDir), "runtime");
  const name = "python-" + VERSION + "-" + RELEASE + "-" + target;
  const installs = [join(root, name), join(root, name + "-recovery")];
  for (const directory of installs) {
    if (await usableInstall(directory, hash, run)) return interpreter(directory);
  }

  await mkdir(root, { recursive: true, mode: 0o700 });
  const staging = await mkdtemp(join(root, ".python-stage-"));
  try {
    const archive = join(staging, "runtime.tar.gz");
    notify("Downloading verified Python " + VERSION + " (" + Math.ceil(bytes / 1_000_000) + " MB) for " + target + ".");
    await downloadArchive(target, archive, fetcher);
    try {
      await run("tar", ["-xzf", archive, "-C", staging, "--no-same-owner"], {
        ...RUN_OPTIONS, timeout: 60000,
        env: { PATH: process.env.PATH, LANG: "C", LC_ALL: "C" },
      });
    } catch {
      throw new Error("Could not unpack the verified archive. The system tar command must support gzip.");
    }
    const unpacked = join(staging, "python");
    if (!(await compatible(interpreter(unpacked), run)))
      throw new Error("The downloaded interpreter cannot run with sqlite3 and ssl on this host.");
    await writeFile(join(unpacked, RECEIPT), hash + "\n", { flag: "wx", mode: 0o600 });

    // Concurrent processes may unpack separately. Only complete, verified trees enter the cache.
    for (const directory of installs) {
      try {
        await rename(unpacked, directory);
        return interpreter(directory);
      } catch (error) {
        if (await usableInstall(directory, hash, run)) return interpreter(directory);
        if (!["EEXIST", "ENOTEMPTY"].includes(error.code)) throw error;
      }
    }
    throw new Error("The managed runtime folders already exist but could not be used.");
  } catch (error) {
    throw new Error("Portable Python setup failed. " + error.message + " " + RECOVERY, { cause: error });
  } finally {
    await rm(staging, { recursive: true, force: true }).catch(() => {});
  }
}
