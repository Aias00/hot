import { spawn } from "node:child_process";

function readFlag(name, fallback) {
  const index = process.argv.indexOf(name);

  if (index === -1 || index === process.argv.length - 1) {
    return fallback;
  }

  return process.argv[index + 1];
}

const frontendHost = readFlag("--host", "127.0.0.1");
const frontendPort = readFlag("--port", "5173");
const backendHost = readFlag("--backend-host", "127.0.0.1");
const backendPort = readFlag("--backend-port", "18000");
const workspaceRoot = process.cwd();

const children = [];

function startProcess(command, args, env = {}) {
  const child = spawn(command, args, {
    cwd: workspaceRoot,
    env: { ...process.env, ...env },
    stdio: "inherit",
  });

  children.push(child);
  return child;
}

function shutdown(signal = "SIGTERM") {
  for (const child of children) {
    if (!child.killed) {
      child.kill(signal);
    }
  }
}

process.on("SIGINT", () => {
  shutdown("SIGINT");
  process.exit(130);
});

process.on("SIGTERM", () => {
  shutdown("SIGTERM");
  process.exit(143);
});

const backend = startProcess(process.execPath, [
  "scripts/dev-backend.mjs",
  "--host",
  backendHost,
  "--port",
  backendPort,
  "--reload",
]);

backend.on("exit", (code) => {
  if (code && code !== 0) {
    shutdown("SIGTERM");
    process.exit(code);
  }
});

const frontend = startProcess(
  "npm",
  ["run", "dev:frontend", "--", "--host", frontendHost, "--port", frontendPort],
  { HOT_BACKEND_ORIGIN: `http://${backendHost}:${backendPort}` },
);

frontend.on("exit", (code) => {
  shutdown("SIGTERM");
  process.exit(code ?? 0);
});
