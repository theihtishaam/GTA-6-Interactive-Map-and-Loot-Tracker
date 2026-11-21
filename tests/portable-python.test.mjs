import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { findUnixPython } from "../bin/portable-python.mjs";

const offline = () => assert.fail("The system or cached Python should avoid the network.");
const diagnostic = { stdout: "glibc 2.36\n", stderr: "" };

async function dataDir(t) {
  const dir = await mkdtemp(join(tmpdir(), "loot-python-test-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

test("probes python3 before python and checks SQLite and TLS support", async (t) => {
  const attempted = [];
  const python = await findUnixPython(await dataDir(t), {
    platform: "linux", arch: "x64", fetcher: offline,
    run: async (name, args) => {
      attempted.push(name);
      assert.deepEqual(args.slice(0, 3), ["-I", "-B", "-c"]);
      assert.match(args[3], /sqlite3.+ssl/);
      if (name === "python3") throw new Error("Incompatible Python.");
    },
  });
  assert.equal(python, "python");
  assert.deepEqual(attempted, ["python3", "python"]);
});

test("avoids Apple's developer-tools shim when it would open an installer", async (t) => {
  const attempted = [];
  const python = await findUnixPython(await dataDir(t), {
    platform: "darwin", arch: "arm64", fetcher: offline,
    run: async (name) => {
      attempted.push(name);
      if (name === "which") return { stdout: "/usr/bin/python3\n" };
      if (name === "/usr/bin/xcode-select") throw new Error("Command line tools unavailable.");
      if (name === "python3") assert.fail("Probing the stub would request an install.");
      return { stdout: "" };
    },
  });
  assert.equal(python, "python");
  assert.deepEqual(attempted, ["which", "/usr/bin/xcode-select", "python"]);
});

test("uses the cached verified native interpreter before attempting any download", async (t) => {
  const base = await dataDir(t);
  const version = join(base, "runtime", "python-3.12.16-20261110-x86_64-unknown-linux-gnu");
  await mkdir(version, { recursive: true });
  await writeFile(join(version, ".loot-atlas-runtime-sha256"),
                  "6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39\n");
  const expected = join(version, "bin", "python3");
  const found = await findUnixPython(base, {
    platform: "linux", arch: "x64", fetcher: offline,
    run: async (name) => {
      if (name === "getconf") return diagnostic;
      if (name === expected) return {};
      throw new Error("No system interpreter.");
    },
  });
  assert.equal(found, expected);
});

test("uses the pinned musl build on ARM64 and rejects a response outside the size bound", async (t) => {
  let downloads = 0;
  await assert.rejects(findUnixPython(await dataDir(t), {
    platform: "linux", arch: "arm64", notify: () => {},
    run: async (name) => {
      if (name === "ldd") throw Object.assign(new Error("libc info"), { stderr: "musl libc (aarch64)" });
      if (name === "tar") assert.fail("Unverified bytes must not be extracted.");
      throw new Error("Not installed.");
    },
    fetcher: async (url, opts) => {
      downloads++;
      assert.match(url.href, /aarch64-unknown-linux-musl-install_only_stripped\.tar\.gz$/);
      assert.equal(opts.redirect, "manual");
      assert.equal(opts.signal.aborted, false);
      return new Response("short", { headers: { "Content-Length": "5" } });
    },
  }), /expected size/);
  assert.equal(downloads, 1);
});

test("does not follow release redirects to arbitrary hosts", async (t) => {
  let hops = 0;
  await assert.rejects(findUnixPython(await dataDir(t), {
    platform: "darwin", arch: "x64", notify: () => {},
    run: async () => { throw new Error("Not installed."); },
    fetcher: async (url) => {
      hops++;
      assert.equal(url.hostname, "github.com");
      return new Response(null, { status: 302, headers: { Location: "https://unsupported.example/archive" } });
    },
  }), /approved GitHub release hosts/);
  assert.equal(hops, 1);
});

test("rejects an invalid payload before attempting to extract it", async (t) => {
  const attempted = [];
  await assert.rejects(findUnixPython(await dataDir(t), {
    platform: "darwin", arch: "arm64", notify: () => {},
    run: async (name) => {
      attempted.push(name);
      throw new Error("Not installed.");
    },
    fetcher: async () => new Response(new Uint8Array([1, 2, 3])),
  }), /SHA-256 verification/);
  assert(!attempted.includes("tar"));
});

test("reports unsupported systems and old glibc with recovery guidance", async (t) => {
  const base = await dataDir(t);
  const missing = async () => { throw new Error("Not installed."); };
  await assert.rejects(findUnixPython(base, {
    platform: "freebsd", arch: "x64", run: missing, fetcher: offline,
  }), /freebsd\/x64.+sqlite3 and ssl/);
  await assert.rejects(findUnixPython(base, {
    platform: "linux", arch: "arm64", fetcher: offline,
    run: (name) => name === "getconf" ? { stdout: "glibc 2.16" } : missing(),
  }), /requires glibc 2\.17/);
});
