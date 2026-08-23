// Minimal Chrome DevTools Protocol client. Node 24 has a global WebSocket, so
// this needs no dependency.

const RPC_TIMEOUT = 90000;

class Session {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener("message", (ev) => this.dispatch(JSON.parse(ev.data)));
  }

  dispatch(msg) {
    if (msg.id !== undefined) {
      const waiter = this.pending.get(msg.id);
      if (!waiter) return;
      this.pending.delete(msg.id);
      if (msg.error)
        waiter.reject(new Error(`${msg.error.message} (${msg.error.code})`));
      else waiter.resolve(msg.result);
      return;
    }
    for (const fn of this.listeners.get(msg.method) ?? []) fn(msg.params);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out`));
      }, RPC_TIMEOUT);
      this.pending.set(id, {
        resolve: (v) => (clearTimeout(timer), resolve(v)),
        reject: (e) => (clearTimeout(timer), reject(e)),
      });
    });
  }

  on(method, fn) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(fn);
    return () => {
      const all = this.listeners.get(method);
      all.splice(all.indexOf(fn), 1);
    };
  }

  // Resolve on the next occurrence of an event.
  once(method) {
    return new Promise((resolve) => {
      const off = this.on(method, (params) => (off(), resolve(params)));
    });
  }

  close() {
    this.ws.close();
  }
}

async function connect(url) {
  const ws = new WebSocket(url);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener(
      "error",
      () => reject(new Error(`cannot connect to ${url}`)),
      {
        once: true,
      },
    );
  });
  return new Session(ws);
}

// Talk to the browser itself, to open and close tabs.
export async function browser(
  port = Number(process.env.MSTP_CDP_PORT ?? 9222),
) {
  let version;
  try {
    version = await (
      await fetch(`http://127.0.0.1:${port}/json/version`, {
        signal: AbortSignal.timeout(4000),
      })
    ).json();
  } catch {
    throw new Error(
      `no browser on port ${port}. Start one with:\n` +
        `  flatpak run --command=chromium io.github.ungoogled_software.ungoogled_chromium \\\n` +
        `    --headless=new --remote-debugging-port=${port} --disable-gpu \\\n` +
        `    --user-data-dir=/tmp/stp-video-profile --hide-scrollbars \\\n` +
        `    --force-device-scale-factor=1 --window-size=1920,1080`,
    );
  }
  const session = await connect(version.webSocketDebuggerUrl);
  return {
    version,
    session,
    async open(url) {
      const { targetId } = await session.send("Target.createTarget", { url });
      const page = await connect(
        `ws://127.0.0.1:${port}/devtools/page/${targetId}`,
      );
      page.targetId = targetId;
      page.close = async () => {
        await session.send("Target.closeTarget", { targetId });
      };
      return page;
    },
    // Pages currently open, so a run can clear what an interrupted one left.
    async pages() {
      const list = await (
        await fetch(`http://127.0.0.1:${port}/json/list`, {
          signal: AbortSignal.timeout(4000),
        })
      ).json();
      return list
        .filter((t) => t.type === "page")
        .map((t) => ({ id: t.id, url: t.url }));
    },
    closeTarget: (targetId) => session.send("Target.closeTarget", { targetId }),
    close: () => session.close(),
  };
}
