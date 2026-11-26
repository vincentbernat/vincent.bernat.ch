// Controls for the line-breaking SVG. The fragment of its URL selects an
// animation. An animation plays each combination of features one after another
// on its own. Once a box is changed, it loops over the combination matching the
// checked boxes. The SVG may come from another origin, so the page and the SVG
// talk with messages.
luffy.do(() => {
  // Features of each animation
  const animations = {
    firefox: ["hyphens", "justify"],
    chrome: ["hyphens", "justify", "pretty"],
    webkit: ["hyphens", "justify", "pretty"],
    preprocess: ["justify"],
  };
  const labels = {
    hyphens: "<code>hyphens: auto</code>",
    justify: "<code>text-align: justify</code>",
    pretty: "<code>text-wrap: pretty</code>",
  };

  for (const object of document.querySelectorAll("object.lf1-line-break")) {
    const name = object.data.slice(object.data.lastIndexOf("#") + 1);
    if (!animations[name]) continue;
    const features = animations[name];

    // Chrome paints an opaque background behind an object whose color
    // scheme differs from the page
    object.style.colorScheme = "light";

    // Setup controls
    const controls = document.createElement("div");
    controls.className = "lf1-line-break-controls";
    const checkbox = (html) => {
      const label = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      label.appendChild(box);
      label.insertAdjacentHTML("beforeend", html);
      controls.appendChild(label);
      return box;
    };
    const boxes = features.map((feature) => checkbox(labels[feature]));
    const slow = checkbox("0.5× speed");
    slow.parentElement.className = "lf1-line-break-slow";
    const outer = object.closest(".lf-media-outer") || object;
    controls.style.width = outer.style.width;
    outer.parentNode.insertBefore(controls, outer.nextSibling);

    // Communication with SVG object through postMessage
    const send = (message) =>
      object.contentWindow?.postMessage({ lf1LineBreak: message }, "*");
    boxes.forEach((box) =>
      box.addEventListener("change", () => {
        const index = boxes.reduce((n, b, i) => n | (b.checked << i), 0);
        send({ index });
      }),
    );
    slow.addEventListener("change", () => send({ slow: slow.checked }));

    // Until a box is changed, the SVG plays all combinations and the boxes
    // follow it
    window.addEventListener("message", (event) => {
      if (event.source !== object.contentWindow) return;
      const index = event.data?.lf1LineBreak?.index;
      if (typeof index !== "number") return;
      boxes.forEach((box, i) => (box.checked = (index >> i) & 1));
    });
  }
});
