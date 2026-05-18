const { optimize } = require("svgo");
const sax = require("sax");
sax.MAX_BUFFER_LENGTH = Infinity;

/* Same as in root.css */
const SANS_STACK =
    'Seravek, "Gill Sans Nova", "Source Sans Pro", source-sans-pro, ' +
    'Cantarell, Ubuntu, "DejaVu Sans", sans-serif';
/* See https://github.com/system-fonts/modern-font-stacks#monospace-code */
const MONO_STACK =
    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, " +
    "'DejaVu Sans Mono', monospace";

const SANS_TRIGGERS = new Set(
    [
        "sans-serif",
        "bitstream vera sans",
        "helvetica",
        "roboto",
        "roboto medium",
        "verdana",
        "source sans pro",
        "droid sans",
        "liberation sans",
    ].map((s) => s.toLowerCase()),
);
const MONO_TRIGGERS = new Set(
    ["monospace", "iosevka", "inconsolata"].map((s) => s.toLowerCase()),
);

const stripQuotes = (s) =>
    s.replace(/^\s*['"]?\s*/, "").replace(/\s*['"]?\s*$/, "");

const replacementFor = (value) => {
    const key = stripQuotes(value).toLowerCase();
    if (SANS_TRIGGERS.has(key)) return SANS_STACK;
    if (MONO_TRIGGERS.has(key)) return MONO_STACK;
    return null;
};

// Rewrites font-family declarations and drops -inkscape-font-specification.
// Works for both inline style="..." attributes (terminated by ;) and CSS inside
// <style> elements (terminated by ; or }). SVGO's serializer escapes embedded
// double quotes for attribute output.
const rewriteCSS = (css) => {
    let out = css.replace(/font-family\s*:\s*([^;}]+)/g, (match, value) => {
        const stack = replacementFor(value.trim());
        return stack ? `font-family: ${stack}` : match;
    });
    out = out.replace(/\s*-inkscape-font-specification\s*:\s*[^;}]*;?/gi, "");
    return out;
};

const replaceFontFamily = {
    name: "replaceFontFamily",
    fn: () => ({
        element: {
            enter: (node) => {
                const ff = node.attributes["font-family"];
                if (ff) {
                    const stack = replacementFor(ff);
                    if (stack) node.attributes["font-family"] = stack;
                }
                const style = node.attributes.style;
                if (style) {
                    node.attributes.style = rewriteCSS(style);
                }
                if (node.name === "style" && node.children) {
                    for (const child of node.children) {
                        if (
                            (child.type === "text" || child.type === "cdata") &&
                            typeof child.value === "string"
                        ) {
                            child.value = rewriteCSS(child.value);
                        }
                    }
                }
            },
        },
    }),
};

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("readable", () => {
    const chunk = process.stdin.read();
    if (chunk) input += chunk;
});
process.stdin.on("end", () => {
    const result = optimize(input, {
        plugins: [replaceFontFamily],
    });
    process.stdout.write(result.data);
});
