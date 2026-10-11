// Drive Firefox with WebDriver BiDi. Read one request per line as JSON, write
// one answer per line as JSON.
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

const [profile] = process.argv.slice(2);

// Firefox is killed when this process dies
const firefox = spawn(
  "setpriv",
  [
    "--pdeathsig",
    "KILL",
    "firefox",
    "--headless",
    "--no-remote",
    "--profile",
    profile,
    "--remote-debugging-port",
    "0",
  ],
  { stdio: ["ignore", process.stderr, "pipe"] },
);

// Firefox writes the address to connect to on its error output
const address = await new Promise((resolve, reject) => {
  const lines = createInterface({ input: firefox.stderr });
  lines.on("line", (line) => {
    const match = line.match(/^WebDriver BiDi listening on (ws:\S+)/);
    if (match) resolve(match[1]);
    else process.stderr.write(line + "\n");
  });
  firefox.on("exit", (code) => reject(new Error(`Firefox exited (${code})`)));
});

// Stop process when Firefox exits
firefox.on("exit", () => process.exit(1));

// Socket handling
const socket = new WebSocket(`${address}/session`);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = () => reject(new Error("cannot connect to Firefox"));
});
socket.onclose = () => process.exit(1);
let next = 0;
const waiting = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  const promise = waiting.get(message.id);
  if (!promise) return;
  waiting.delete(message.id);
  if (message.type === "error")
    promise.reject(new Error(`${promise.method}: ${message.message}`));
  else promise.resolve(message.result);
};
function send(method, params) {
  const id = ++next;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) =>
    waiting.set(id, { resolve, reject, method }),
  );
}

await send("session.new", { capabilities: {} });
const { context } = await send("browsingContext.create", { type: "tab" });

// Screenshot of the first element matching a selector
async function screenshot({ url, width, height, selector }) {
  await send("browsingContext.setViewport", {
    context,
    viewport: { width, height },
  });
  await send("browsingContext.navigate", { context, url, wait: "complete" });
  const found = await send("browsingContext.locateNodes", {
    context,
    locator: { type: "css", value: selector },
    maxNodeCount: 1,
  });
  if (!found.nodes.length) throw new Error(`no ${selector} in ${url}`);
  const image = await send("browsingContext.captureScreenshot", {
    context,
    origin: "document",
    clip: { type: "element", element: { sharedId: found.nodes[0].sharedId } },
  });
  return { png: image.data };
}

// Read requests on stdin
const input = createInterface({ input: process.stdin });
input.on("line", async (line) => {
  let answer;
  try {
    answer = await screenshot(JSON.parse(line));
  } catch (e) {
    answer = { error: e.message };
  }
  process.stdout.write(JSON.stringify(answer) + "\n");
});
input.on("close", () => {
  firefox.kill("SIGKILL");
  process.exit(0);
});
