#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const project = dirname(dirname(fileURLToPath(import.meta.url)));
const help = [
  "GTA 6 Loot Map by theihtishaam",
  "",
  "  gta6-loot-map          Open the map in your browser",
  "  gta6-loot-map status   Show this player's server address",
  "  gta6-loot-map stop     Stop the local server",
  "",
  "Start options: --no-open, --bundled-only, --port NUMBER",
  "You can also use Settings > Stop server or Ctrl+C.",
].join("\n");

function playerDirectory() {
  if (process.env.GTA6_LOOT_MAP_DATA) return resolve(process.env.GTA6_LOOT_MAP_DATA);
  if (process.platform === "win32")
    return join(process.env.LOCALAPPDATA || join(homedir(),"AppData","Local"),"GTA6LootMap");
  if (process.platform === "darwin") return join(homedir(),"Library","Application Support","GTA6LootMap");
  return join(process.env.XDG_DATA_HOME || join(homedir(),".local","share"),"gta6-loot-map");
}

function parse(args) {
  const raw = [...args];
  let action = "start";
  if (["start","stop","status","--stop","--status"].includes(raw[0])) action = raw.shift().replace(/^--/,"");
  const options = [];
  while (raw.length) {
    const word = raw.shift();
    if (action === "start" && ["--no-open", "--bundled-only"].includes(word)) options.push(word);
    else if (action === "start" && word === "--port" && /^\d{1,5}$/.test(raw[0]) && Number(raw[0]) <= 65535)
      options.push("--port",raw.shift());
    else throw Error("Unknown or invalid option: "+word+". Run gta6-loot-map --help.");
  }
  return {action,options};
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help") || args[0] === "help" || args[0] === "-h") { console.log(help); return 0; }
  if (args.includes("--version") || args[0] === "-v") { console.log(readFileSync(join(project,"VERSION"),"utf8").trim()); return 0; }
  const {action,options} = parse(args);
  const dataDir = playerDirectory();
  if (action !== "start" && !existsSync(join(dataDir,"launcher.lock"))) {
    console.log("GTA 6 Loot Map is already stopped.");
    return 0;
  }
  let executable, parameters;
  if (process.platform === "win32") {
    executable = join(process.env.SystemRoot || "C:\\Windows","System32","WindowsPowerShell","v1.0","powershell.exe");
    parameters = ["-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",join(project,"tools","WindowsLauncher.ps1"),"-Action",action];
    for (const value of options)
      parameters.push(({"--no-open":"-NoOpen","--bundled-only":"-BundledOnly","--port":"-Port"})[value] || value);
  } else {
    const {findUnixPython} = await import("./portable-python.mjs");
    executable = await findUnixPython(dataDir);
    parameters = [join(project,"app.py"), ...(action === "start" ? options : ["--"+action])];
  }
  const child = spawnSync(executable, parameters, {
    stdio:"inherit", env:{...process.env,GTA6_LOOT_MAP_DATA:dataDir,PYTHONDONTWRITEBYTECODE:"1"},
  });
  if (child.error) throw child.error;
  return child.status ?? (child.signal === "SIGINT" ? 0 : 1);
}
try { process.exitCode = await main(); }
catch (err) { console.error("GTA 6 Loot Map: " + err.message); process.exitCode = 1; }
