import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

function readFlag(name, fallback) {
  const index = process.argv.indexOf(name);

  if (index === -1 || index === process.argv.length - 1) {
    return fallback;
  }

  return process.argv[index + 1];
}

const workspaceRoot = process.cwd();
const backendHost = readFlag("--host", "127.0.0.1");
const backendPort = readFlag("--port", "18000");
const backendEnvFile = "backend/.env";

const args = [
  "run",
  "--project",
  "backend",
  "uvicorn",
  "hot_backend.app:app",
  "--app-dir",
  "backend/src",
];

if (existsSync(join(workspaceRoot, backendEnvFile))) {
  args.push("--env-file", backendEnvFile);
}

args.push("--host", backendHost, "--port", backendPort, "--reload");

const child = spawn("uv", args, {
  cwd: workspaceRoot,
  env: process.env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  }

  process.exit(code ?? 0);
});
