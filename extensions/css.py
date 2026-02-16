# -*- coding: utf-8 -*-
"""
CSS plugins
"""

import subprocess
from hyde.plugin import Plugin


class CSSPrefixerPlugin(Plugin):
    """Run CSS prefixer"""

    def text_resource_complete(self, resource, text):
        if resource.source_file.kind != "css":
            return
        if self.site.config.mode == "development":
            minify = "false"
        else:
            minify = "true"
        p = subprocess.Popen(
            [
                "node",
                "-e",
                """
const autoprefixer = require("autoprefixer");
const cssnano = require("cssnano");
const postcss = require("postcss");
const postcssCustomMedia = require("postcss-custom-media");
const postcssNesting = require("postcss-nesting");
const postcssMixins = require("@csstools/postcss-mixins");

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
                /light-dark\\(\\s*([^,]+?)\\s*,\\s*[^)]+?\\)/g,
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
                prop: 'color-scheme',
                value: 'light',
                raws: {before: '\\n  '},
            });
            fallbackDecls.forEach((d) => clonedRule.append(d));
            supportsRule.append(clonedRule);
            rule.parent.insertAfter(rule, supportsRule);
        }
    },
};

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
        postcssCustomMedia,
        postcssMixins,
        lightDarkFallback,
        autoprefixer,
        postcssNesting,
        cssnano({
            preset: [
                "default",
                {
                    reduceIdents: false,
                    normalizeWhitespace: %s,
                },
            ],
        }),
    ])
        .process(input, { from: undefined })
        .then(function (result) {
            process.stdout.write(result.css.toString());
        });
});
        """
                % minify,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        stdout, _ = p.communicate(text.encode("utf-8"))
        assert p.returncode == 0
        return stdout.decode("utf-8")
