const autoprefixer = require("autoprefixer");
const cssnano = require("cssnano");
const postcss = require("postcss");
const postcssCustomMedia = require("postcss-custom-media");
const postcssNesting = require("postcss-nesting");
const postcssMixins = require("@csstools/postcss-mixins");
const { calc: resolveCalc } = require("@csstools/css-calc");

// Resolve @apply --lf-font-size(X) into font-size and line-height declarations.
// The line-height is computed to maintain vertical rhythm:
//
//   ceil(fontFactor / lineHeight) * lineHeight / fontFactor
//
// The idea is to be have the first multiple of lineHeight / fontFactor which is
// >= 1.
const lfFontSize = {
    postcssPlugin: "lf-font-size",
    Once(root) {
        let lineHeight = 0;
        root.walkRules(":root", (rule) => {
            rule.walkDecls("--lf-line-height", (decl) => {
                lineHeight = parseFloat(decl.value);
            });
        });
        root.walkAtRules("apply", (atRule) => {
            const match = atRule.params.match(/^--lf-font-size\(([^)]+)\)$/);
            if (!match) return;
            const fontFactor = parseFloat(match[1]);
            const lh = Math.ceil(fontFactor / lineHeight) * (lineHeight / fontFactor);
            atRule.replaceWith(
                postcss.decl({
                    prop: "font-size",
                    value: `${fontFactor}rem`,
                }),
                postcss.decl({
                    prop: "line-height",
                    value: String(
                        Math.round(lh * 10000) / 10000,
                    ),
                }),
            );
        });
    },
};

// light-dark() fallback: for each rule with declarations using
// light-dark(a, b), insert a @supports fallback with the light value.
const lightDarkFallback = {
    postcssPlugin: "light-dark-fallback",
    Rule(rule) {
        const fallbackDecls = [];
        rule.each((node) => {
            if (node.type !== "decl") return;
            if (!node.value.includes("light-dark(")) return;
            const fallback = node.value.replace(
                /light-dark\(\s*([^,]+?)\s*,\s*[^)]+?\)/g,
                "$1",
            );
            if (fallback !== node.value) {
                fallbackDecls.push(node.clone({ value: fallback }));
            }
        });
        if (fallbackDecls.length > 0) {
            const supportsRule = postcss.atRule({
                name: "supports",
                params: "not (color: light-dark(red, red))",
            });
            const clonedRule = rule.clone();
            clonedRule.removeAll();
            clonedRule.append({
                prop: "color-scheme",
                value: "light",
                raws: { before: "\n  " },
            });
            fallbackDecls.forEach((d) => clonedRule.append(d));
            supportsRule.append(clonedRule);
            rule.parent.insertAfter(rule, supportsRule);
        }
    },
};

// Resolve CSS custom properties within calc() in media queries. Only :root
// variables are resolved. Percentage values from variables are converted to
// unitless numbers (e.g. 112.5% → 1.125) so that @csstools/css-calc can reduce
// the expression. The result is floored and rem is converted to em (equivalent
// in media queries, it seems safer).
const resolveCustomPropsInMediaCalc = {
    postcssPlugin: "resolve-custom-props-in-media-calc",
    Once(root) {
        const vars = {};
        root.walkRules(":root", (rule) => {
            rule.walkDecls(/^--/, (decl) => {
                vars[decl.prop] = decl.value.trim();
            });
        });
        root.walkAtRules((atRule) => {
            if (atRule.name !== "media" && atRule.name !== "custom-media")
                return;
            if (!atRule.params.includes("var(")) return;
            let params = atRule.params;
            let changed = true;
            while (changed) {
                changed = false;
                params = params.replace(
                    /var\(\s*(--[\w-]+)\s*\)/g,
                    (match, name) => {
                        if (vars[name] === undefined) return match;
                        changed = true;
                        // Convert percentage to unitless for calc compatibility
                        const pct = vars[name].match(/^(\d*\.?\d+)%$/);
                        if (pct) return String(parseFloat(pct[1]) / 100);
                        return vars[name];
                    },
                );
            }
            if (params.includes("var(")) return;
            // Resolve calc() expressions, floor, and convert rem to em
            atRule.params = resolveCalc(params).replace(
                /(\d*\.?\d+)rem\b/g,
                (_, n) => `${Math.floor(parseFloat(n))}em`,
            );
        });
    },
};

const minify = process.env.CSS_MINIFY === "true";
let input = "";

process.stdin.setEncoding("utf8");
process.stdin.on("readable", function () {
    const chunk = process.stdin.read();
    if (chunk) {
        input += chunk;
    }
});
process.stdin.on("end", function () {
    postcss([
        resolveCustomPropsInMediaCalc,
        postcssCustomMedia,
        lfFontSize,
        postcssMixins,
        lightDarkFallback,
        autoprefixer,
        postcssNesting,
        cssnano({
            preset: [
                "default",
                {
                    reduceIdents: false,
                    normalizeWhitespace: minify,
                },
            ],
        }),
    ])
        .process(input, { from: undefined })
        .then(function (result) {
            process.stdout.write(result.css.toString());
        });
});
