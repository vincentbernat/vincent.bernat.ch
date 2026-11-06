{
  // Same values as in bunny-dns-map.svg
  const W = 1000;
  const H = 440;
  const LAT_TOP = 75;
  // Artworks linking to their author: position and area around it
  const CREDITS = [
    {
      title: "Pirate ship from Vecteezy.com",
      href: "https://www.vecteezy.com/vector-art/88021805-pirate-ship-with-a-flag-on-a-white-background",
      lat: -28,
      lon: -18,
      area: [-29, -40, 58, 49],
    },
    {
      title: "Whale from Public Domain Vectors",
      href: "https://publicdomainvectors.org/en/free-clipart/Cute-Blue-Whale-Vector-Illustration/93130.html",
      lat: 10,
      lon: -132,
      area: [-31, -20, 62, 34],
    },
    {
      title: "Shark fins by Claude Opus 5.5",
      href: "https://claude.com/",
      lat: -32,
      lon: 78,
      area: [-37, -22, 55, 32],
    },
  ];
  const PROVIDERS = {
    Sapinet: "https://sapi.net/",
    Hetzner: "https://www.hetzner.com/",
    Vultr: "https://www.vultr.com/",
  };
  const SCALE = 2; // canvas pixels for one SVG unit
  const STRIPE = 16; // canvas pixels between two stripes
  const STRIPE_WIDTH = 5;
  const EARTH_RADIUS = 3958.8; // miles, like GeoDistance.calculate()

  const servers = [
    {
      name: "web02",
      provider: "Sapinet",
      lat: 48.88,
      lon: 2.22,
    },
    {
      name: "web04",
      provider: "Hetzner",
      lat: 49.45,
      lon: 11.01,
    },
    {
      name: "web05",
      provider: "Hetzner",
      lat: 39.02,
      lon: -77.47,
    },
    {
      name: "web06",
      provider: "Vultr",
      lat: 1.35,
      lon: 103.82,
    },
    {
      name: "web07",
      provider: "Vultr",
      lat: 37.34,
      lon: -121.89,
    },
    {
      name: "web09",
      provider: "Vultr",
      lat: -23.55,
      lon: -46.63,
    },
    {
      name: "web10",
      provider: "Vultr",
      lat: -33.87,
      lon: 151.21,
    },
  ];

  // Miller projection
  const RAD = Math.PI / 180;
  const K = W / (2 * Math.PI);
  const miller = (phi) => 1.25 * Math.log(Math.tan(Math.PI / 4 + 0.4 * phi));
  const Y0 = K * miller(LAT_TOP * RAD);
  const project = (lat, lon) => [
    W / 2 + K * lon * RAD,
    Y0 - K * miller(lat * RAD),
  ];
  const invert = (x, y) => [
    (2.5 * Math.atan(Math.exp((0.8 * (Y0 - y)) / K)) - 0.625 * Math.PI) / RAD,
    (x - W / 2) / K / RAD,
  ];

  // Points on the unit sphere
  const vector = (lat, lon) => {
    const phi = lat * RAD,
      lambda = lon * RAD;
    return [
      Math.cos(phi) * Math.cos(lambda),
      Math.cos(phi) * Math.sin(lambda),
      Math.sin(phi),
    ];
  };
  const miles = (dot) =>
    EARTH_RADIUS * Math.acos(Math.max(-1, Math.min(1, dot)));

  // Colors come from OKLCH, where the same step looks the same everywhere.
  // The hues are evenly spaced, without the hues of the sea, and the
  // lightness alternates between two values. Each server takes the free color
  // the most different from the ones of the servers near it.
  const CHROMA = 0.11;
  const palette = servers.map((_, k) => {
    const hue = (275 + ((k + 0.5) * 265) / servers.length) * RAD;
    return [k % 2 ? 0.7 : 0.85, CHROMA * Math.cos(hue), CHROMA * Math.sin(hue)];
  });
  const srgb = ([lightness, a, b]) => {
    const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3,
      m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3,
      s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
    return [
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ].map((v) => {
      v = Math.max(0, Math.min(1, v));
      v = v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055;
      return Math.round(v * 255);
    });
  };
  // Stripes of two colors are easier to read with different lightness
  const distance = (p, q) =>
    Math.hypot(1.5 * (p[0] - q[0]), p[1] - q[1], p[2] - q[2]);
  for (const s of servers) {
    s.enabled = true;
    s.vector = vector(s.lat, s.lon);
    let bestScore = Infinity;
    for (const lab of palette) {
      let score = 0;
      for (const o of servers) {
        if (o === s || !o.lab) continue;
        const dot = s.vector.reduce((sum, v, i) => sum + v * o.vector[i], 0);
        const near = 1 / (1 + miles(dot) / 1000);
        score = Math.max(score, near / distance(lab, o.lab));
      }
      if (score < bestScore) {
        bestScore = score;
        s.lab = lab;
      }
    }
    palette.splice(palette.indexOf(s.lab), 1);
    const [r, g, b] = srgb(s.lab);
    s.color = `rgb(${r},${g},${b})`;
    // ABGR, for a little-endian Uint32Array over the image data
    s.pixel = (0xff000000 | (b << 16) | (g << 8) | r) >>> 0;
  }

  // Same logic as the Bunny DNS script: the two closest servers, or only the
  // closest one when the second one is too far.
  let first, second;
  const closest = (x, y, z) => {
    let firstDot = -2,
      secondDot = -2;
    first = second = null;
    for (const s of servers) {
      if (!s.enabled) continue;
      const dot = s.vector[0] * x + s.vector[1] * y + s.vector[2] * z;
      if (dot > firstDot) {
        second = first;
        secondDot = firstDot;
        first = s;
        firstDot = dot;
      } else if (dot > secondDot) {
        second = s;
        secondDot = dot;
      }
    }
    if (second) {
      const d1 = miles(firstDot);
      const d2 = miles(secondDot);
      if (d2 > 2 * d1 && d2 - d1 > 1000) second = null;
    }
  };
  const answer = (x, y, z) => {
    closest(x, y, z);
    const selected = [first, second].filter(Boolean);
    const distances = selected.map((s) =>
      miles(s.vector[0] * x + s.vector[1] * y + s.vector[2] * z),
    );
    return { selected, distances, ttl: second ? 3600 : 120 };
  };

  const img = document.querySelector("#lf1-map img");
  const inner = img && img.closest(".lf-media-inner");
  if (inner) {
    const canvas = document.createElement("canvas");
    canvas.className = "lf1-bunny-canvas";
    canvas.width = W * SCALE;
    canvas.height = H * SCALE;
    canvas.setAttribute("aria-hidden", "true");
    inner.insertBefore(canvas, img);
    const ctx = canvas.getContext("2d");

    // Unit vectors for each column and each row
    const cols = canvas.width,
      rows = canvas.height;
    const lonCos = new Float64Array(cols),
      lonSin = new Float64Array(cols);
    for (let i = 0; i < cols; i++) {
      const lambda = invert((i + 0.5) / SCALE, 0)[1] * RAD;
      lonCos[i] = Math.cos(lambda);
      lonSin[i] = Math.sin(lambda);
    }
    const latCos = new Float64Array(rows),
      latSin = new Float64Array(rows);
    for (let j = 0; j < rows; j++) {
      const phi = invert(0, (j + 0.5) / SCALE)[0] * RAD;
      latCos[j] = Math.cos(phi);
      latSin[j] = Math.sin(phi);
    }

    const render = () => {
      const image = ctx.createImageData(cols, rows);
      const pixels = new Uint32Array(image.data.buffer);
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          closest(latCos[j] * lonCos[i], latCos[j] * lonSin[i], latSin[j]);
          if (!first) continue;
          const stripe = second && (i + j) % STRIPE < STRIPE_WIDTH;
          pixels[j * cols + i] = (stripe ? second : first).pixel;
        }
      }
      ctx.putImageData(image, 0, 0);
    };

    // Servers on top of the map. The icon of a provider is a view of the
    // image, like #hetzner. When another server is close, icon and label go
    // on the side away from it.
    const SVGNS = "http://www.w3.org/2000/svg";
    const ICON_BOX = 22;
    const NEAR = 40;
    const src = img.src.split("#")[0];
    const svg = (name, attributes, parent) => {
      const el = document.createElementNS(SVGNS, name);
      for (const key in attributes) el.setAttribute(key, attributes[key]);
      parent.appendChild(el);
      return el;
    };
    // Animated artworks on top of the image, which stays still: an animation
    // in an image redraws the whole image at each frame
    const sprites = document.createElement("object");
    sprites.className = "lf1-bunny-sprites";
    sprites.type = "image/svg+xml";
    sprites.setAttribute("aria-hidden", "true");
    inner.appendChild(sprites);
    const dark = matchMedia("(prefers-color-scheme: dark)");
    const theme = () => {
      sprites.data = `${src}#${dark.matches ? "sprites-dark" : "sprites"}`;
    };
    theme();
    dark.addListener(theme);

    const overlay = svg(
      "svg",
      { class: "lf1-bunny-servers", viewBox: `0 0 ${W} ${H}` },
      inner,
    );
    const markers = servers.map((s) => {
      const [x, y] = project(s.lat, s.lon);
      let side = null;
      for (const o of servers) {
        const [ox, oy] = project(o.lat, o.lon);
        if (o !== s && Math.hypot(ox - x, oy - y) < NEAR) {
          side = ox > x ? "left" : "right";
        }
      }
      const g = svg("g", {}, overlay);
      const link = svg("a", { href: PROVIDERS[s.provider] }, g);
      svg("title", {}, link).textContent = s.provider;
      const icon = svg(
        "image",
        {
          width: ICON_BOX,
          height: ICON_BOX,
          x: side
            ? side === "left"
              ? x - ICON_BOX - 3
              : x + 3
            : x - ICON_BOX / 2,
          y: side ? y - ICON_BOX / 2 - 9 : y - ICON_BOX - 3,
        },
        link,
      );
      const href = `${src}#${s.provider.toLowerCase()}`;
      icon.setAttribute("href", href);
      icon.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", href);
      svg("path", { d: `M${x - 3.5},${y - 3.5}l7,7m0,-7l-7,7` }, g);
      const label = svg(
        "text",
        {
          x: side ? (side === "left" ? x - 7 : x + 7) : x,
          y: side ? y + 15 : y + 17,
          "text-anchor": side ? (side === "left" ? "end" : "start") : "middle",
        },
        g,
      );
      label.textContent = s.name;
      return g;
    });

    for (const c of CREDITS) {
      const [x, y] = project(c.lat, c.lon);
      const [left, top, width, height] = c.area;
      const link = svg("a", { href: c.href }, overlay);
      svg("title", {}, link).textContent = c.title;
      svg("rect", { x: x + left, y: y + top, width, height }, link);
    }

    // Checkboxes below the map
    const legend = document.createElement("div");
    legend.className = "lf1-bunny-legend";
    servers.forEach((s, index) => {
      const label = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = true;
      box.addEventListener("change", () => {
        s.enabled = box.checked;
        markers[index].style.display = s.enabled ? "" : "none";
        render();
      });
      const swatch = document.createElement("span");
      swatch.className = "lf1-bunny-swatch";
      swatch.style.background = s.color;
      label.appendChild(box);
      label.appendChild(swatch);
      label.appendChild(document.createTextNode(s.name));
      legend.appendChild(label);
    });
    const anchor = img.closest("figure") || img.closest(".lf-media-outer");
    anchor.insertAdjacentElement("afterend", legend);

    // Answer for the point under the pointer
    const tip = document.createElement("div");
    tip.className = "lf1-bunny-tip";
    tip.hidden = true;
    inner.appendChild(tip);
    const show = (event) => {
      const rect = img.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * W;
      const y = ((event.clientY - rect.top) / rect.height) * H;
      if (x < 0 || x > W || y < 0 || y > H) {
        tip.hidden = true;
        return;
      }
      const [lat, lon] = invert(x, y);
      const r = answer(...vector(lat, lon));
      const fmt = (v, pos, neg) =>
        `${Math.abs(v).toFixed(1)}° ${v < 0 ? neg : pos}`;
      tip.innerHTML = "";
      const line = (text, color) => {
        const div = document.createElement("div");
        if (color) {
          const swatch = document.createElement("span");
          swatch.className = "lf1-bunny-swatch";
          swatch.style.background = color;
          div.appendChild(swatch);
        }
        div.appendChild(document.createTextNode(text));
        tip.appendChild(div);
      };
      line(`${fmt(lat, "N", "S")}, ${fmt(lon, "E", "W")}`);
      r.selected.forEach((s, i) =>
        line(
          `${s.name}: ${Math.round(r.distances[i]).toLocaleString("en")} mi`,
          s.color,
        ),
      );
      if (r.selected.length) line(`TTL ${r.ttl === 120 ? "2 min" : "1 h"}`);
      else line("No answer");
      tip.hidden = false;
      const left = event.clientX - rect.left + 12;
      tip.style.left = `${Math.max(0, Math.min(left, rect.width - tip.offsetWidth))}px`;
      tip.style.top = `${event.clientY - rect.top + 12}px`;
    };
    img.addEventListener("mousemove", show);
    img.addEventListener("click", show);
    img.addEventListener("mouseleave", () => {
      tip.hidden = true;
    });

    render();
  }
}

// Server that sent this page, from the "Server-Timing: served-by;desc=web04"
// header
{
  const servedBy = document.getElementById("lf1-served-by");
  const entry =
    window.performance &&
    performance.getEntriesByType &&
    performance.getEntriesByType("navigation")[0];
  const timing =
    entry &&
    entry.serverTiming &&
    entry.serverTiming.find((t) => t.name === "served-by");
  if (servedBy) {
    servedBy.querySelector("code").textContent =
      (timing && timing.description) || "???";
  }
}
