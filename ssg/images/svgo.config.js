// svgo reads the stylesheet as if no element is targeted. With :target rules,
// it removes or restyles the elements these rules show.
const target = process.env.SVGO_TARGET === "1";

module.exports = {
  plugins: [
    {
      name: "preset-default",
      params: target
        ? { overrides: { removeHiddenElems: false, inlineStyles: false } }
        : {},
    },
  ],
};
