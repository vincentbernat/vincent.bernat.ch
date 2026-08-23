// Turns the article into a cue sheet for the video: one segment per paragraph
// or block, with paragraphs split wherever an #mstp: control link appears so
// that every cue lands at the start of its own segment.
//
//   node scratch/extract.mjs
//
// Writes scratch/out/segments.json, scratch/script/*.txt and
// scratch/PRONUNCIATION.md. Everything a human sets lives in overrides.json,
// so the output can be thrown away and rebuilt at any time.

import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { splitSentences } from "./text.mjs";
import { respell } from "./respell.mjs";

import { fileURLToPath } from "node:url";

// Paths are anchored to this file, not to the working directory, so the scripts
// run the same from scratch/ or anywhere else.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");

const ARTICLE = join(REPO, "content/en/blog/2026-spanning-tree.html");
const OUT = HERE;
const SCRIPT_DIR = join(OUT, "script");
const DERIVED = join(OUT, "out", "segments.json");

// Words a minute, used only to guess a duration for a segment with no recording
// yet. Measured over 38 takes it comes to 124, and this is set a little under
// that on purpose: a guess that runs long can be trimmed at assembly, while one
// that falls short has to be rendered again.
const WORDS_PER_MINUTE = 115;

// Anything a human sets by hand lives in overrides.json, so this file is pure
// output and can be thrown away at any time.
const HAND_SET = [
  "holdOverride",
  "durationOverride",
  "loopGap",
  "note",
  "credit",
  "iris",
];

// Segments shorter than this are folded into a neighbour.
const MIN_WORDS = 8;
// A bullet stands on its own only when it is long enough to be worth it. Short
// items — a list of port roles, a list of states — read as one breath.
const BULLET_MIN_WORDS = 25;

// Marker left in place of an #mstp: link, so we can find it again once the
// rest of the markup is gone. Printable, and absent from the article.
const CUE_OPEN = "@@CUE";
const CUE_CLOSE = "@@";

// -- reading the article ---------------------------------------------

function stripFrontMatter(text) {
  const end = text.indexOf("\n---", 3);
  return text.slice(text.indexOf("\n", end + 1) + 1);
}

function parseBlocks(text) {
  const lines = text.split("\n");
  const blocks = [];
  let paragraph = [];
  let i = 0;

  const flush = () => {
    const body = paragraph.join("\n").trim();
    if (body) blocks.push({ type: "paragraph", body });
    paragraph = [];
  };

  while (i < lines.length) {
    const line = lines[i];

    if (line.trimStart().startsWith("<!--")) {
      flush();
      while (i < lines.length && !lines[i].includes("-->")) i++;
      i++;
      continue;
    }

    // The whole info string, not just the first word: a wireshark block
    // carries its highlighted lines after the language, as hl_lines="5 6".
    const fence = line.match(/^```\s*(.*)$/);
    if (fence) {
      flush();
      const body = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i]))
        body.push(lines[i++]);
      i++;
      blocks.push({
        type: "fence",
        info: fence[1] ?? "",
        body: body.join("\n"),
      });
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      flush();
      blocks.push({
        type: "heading",
        level: heading[1].length,
        body: heading[2].trim(),
      });
      i++;
      continue;
    }

    if (line.startsWith("![")) {
      flush();
      const body = [];
      while (i < lines.length && lines[i].trim() !== "") body.push(lines[i++]);
      blocks.push({ type: "image", body: body.join("\n") });
      continue;
    }

    if (line.startsWith(">")) {
      flush();
      const body = [];
      while (i < lines.length) {
        if (lines[i].startsWith(">")) body.push(lines[i++]);
        else if (lines[i].trim() === "" && lines[i + 1]?.startsWith(">")) i++;
        else break;
      }
      blocks.push({ type: "quote", body: body.join("\n") });
      continue;
    }

    if (line.startsWith("!!!")) {
      flush();
      const body = [];
      while (i < lines.length && lines[i].trim() !== "") body.push(lines[i++]);
      if (lines[i + 1]?.startsWith("{.")) i++;
      blocks.push({ type: "admonition", body: body.join("\n") });
      continue;
    }

    if (/^\[\^[^\]]+\]:/.test(line)) {
      flush();
      const body = [line];
      i++;
      while (i < lines.length) {
        if (lines[i].startsWith("    ")) body.push(lines[i++]);
        else if (lines[i].trim() === "" && lines[i + 1]?.startsWith("    "))
          i++;
        else break;
      }
      blocks.push({ type: "footnote", body: body.join("\n") });
      continue;
    }

    // Lines that carry no narration.
    if (
      /^\[TOC\]/.test(line) ||
      /^\{\./.test(line) ||
      /^\*\[[^\]]+\]:/.test(line) ||
      /^\[[^\]^]+\]:\s/.test(line)
    ) {
      flush();
      i++;
      continue;
    }

    if (line.trim() === "") {
      flush();
      i++;
      continue;
    }

    paragraph.push(line);
    i++;
  }
  flush();
  return blocks;
}

// -- turning markdown into something readable aloud ------------------

function markCues(text, cues) {
  return text.replace(/\[([^\]]*)\]\(#mstp:([^)]+)\)/g, (_, label, spec) => {
    cues.push(decodeURIComponent(spec.trim()));
    return CUE_OPEN + (cues.length - 1) + CUE_CLOSE + label;
  });
}

function flatten(text) {
  return text
    .replace(/\[\^[^\]]+\]/g, "")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\[[^\]]*\]/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/(?<!\w)[*_]([^*_]+)[*_](?!\w)/g, "$1")
    .replace(/\u00a0/g, " ")
    .replace(/\s*\n\s*/g, " ")
    .replace(/ {2,}/g, " ")
    .trim();
}

// Strip the markers and report where each one sat in the resulting text.
function takeCueOffsets(text) {
  const re = new RegExp(CUE_OPEN + "(\\d+)" + CUE_CLOSE, "g");
  const found = [];
  let shift = 0;
  let m;
  while ((m = re.exec(text))) {
    found.push({ index: Number(m[1]), offset: m.index - shift });
    shift += m[0].length;
  }
  return { clean: text.replace(re, ""), cues: found };
}

// -- sentences -------------------------------------------------------

// -- helpers ---------------------------------------------------------

const slugify = (s) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48) || "segment";

const wordCount = (s) => (s.trim() ? s.trim().split(/\s+/).length : 0);
const estimate = (s) => Math.max(1.5, (wordCount(s) / WORDS_PER_MINUTE) * 60);

// How a cue behaves on screen, from its op list:
//   run     it ends with "...", so the clock keeps running and the diagram
//           never stops moving. Nothing to loop.
//   step    it ends on a step count, so one step plays animated and then it
//           stops. Short, and worth replaying under a long sentence.
//   static  everything applies at once and nothing moves.
const classifyCue = (spec) => {
  const all = spec
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const slow = all.includes("@");
  if (all.includes("...")) return { mode: "run", slow };
  const ops = all.filter(
    (op) => op !== "..." && op !== "@" && !op.includes("->"),
  );
  const step = ops.length > 0 && /^\d+$/.test(ops[ops.length - 1]);
  return { mode: step ? "step" : "static", slow };
};

// -- building the segments -------------------------------------------

// One paragraph or bullet, cut at the sentences that carry a control link.
function piecesOf(clean, cues) {
  const sentences = splitSentences(clean);
  const bounds = [];
  let at = 0;
  for (const sentence of sentences) {
    const idx = clean.indexOf(sentence, at);
    bounds.push({ start: idx, end: idx + sentence.length });
    at = idx + sentence.length;
  }
  const placed = cues.map((c) => {
    const found = bounds.findIndex(
      (b) => c.offset >= b.start && c.offset <= b.end,
    );
    return { ...c, sentence: found < 0 ? 0 : found };
  });
  const starts = [...new Set([0, ...placed.map((c) => c.sentence)])].sort(
    (a, b) => a - b,
  );
  return starts.map((from, j) => {
    const to = starts[j + 1] ?? sentences.length;
    return {
      text: sentences.slice(from, to).join(" "),
      cues: placed.filter((c) => c.sentence >= from && c.sentence < to),
    };
  });
}

function build(blocks) {
  const segments = [];
  const topologies = [];
  const footnotes = [];
  // Per language, so a block keeps its name when segments move around it.
  const blockCount = {};
  let section = "";
  let sectionSlug = "";
  let topology = null;
  // Prose that opens a section talks about the diagram it is about to show,
  // not the one from the section before. Until that diagram turns up, such
  // segments are pointed at the next topology instead of the previous one.
  let aheadOfTopology = true;
  let counter = 0;

  const push = (seg) => {
    counter += 1;
    segments.push({
      id: String(counter).padStart(3, "0"),
      section,
      sectionSlug,
      ...seg,
    });
  };

  for (const block of blocks) {
    if (block.type === "footnote") {
      footnotes.push(flatten(block.body.replace(/^\[\^([^\]]+)\]:\s*/, "")));
      continue;
    }

    if (block.type === "admonition") {
      if (/leave your RSS reader|enable JavaScript/i.test(block.body)) continue;
      const text = flatten(block.body.replace(/^!!!\s*"[^"]*"\s*/, ""));
      push({
        kind: "note",
        visual: { type: "note" },
        text,
        slug: slugify(text.slice(0, 40)),
        static: true,
      });
      continue;
    }

    if (block.type === "heading") {
      section = block.body;
      sectionSlug = slugify(block.body);
      aheadOfTopology = true;
      push({
        kind: "title",
        visual: { type: "title", level: block.level, title: block.body },
        text: "",
        slug: "title-" + sectionSlug,
        static: true,
        hold: block.level === 1 ? 2.6 : 2.0,
      });
      continue;
    }

    if (block.type === "fence") {
      if (/mstp-topology/.test(block.info)) {
        topology = topologies.length;
        aheadOfTopology = false;
        topologies.push({ id: topology, source: block.body });
        continue;
      }
      const lang = /^wireshark/.test(block.info)
        ? "wireshark"
        : /javascript/.test(block.info)
          ? "javascript"
          : /console/.test(block.info)
            ? "console"
            : "text";
      const highlights = (block.info.match(/hl_lines="([^"]+)"/)?.[1] ?? "")
        .split(/\s+/)
        .filter(Boolean)
        .map(Number);
      const lineCount = block.body.split("\n").length;
      push({
        kind: "block",
        visual: {
          type: lang === "wireshark" ? "packet" : "code",
          lang,
          highlights,
          lines: lineCount,
        },
        text: "",
        slug: lang + "-" + (blockCount[lang] = (blockCount[lang] ?? 0) + 1),
        static: true,
        hold:
          lang === "wireshark"
            ? 2.5 + highlights.length * 1.0
            : 3.0 + lineCount * 0.25,
        body: block.body,
      });
      continue;
    }

    if (block.type === "image") {
      const alt = flatten(block.body.match(/^!\[([\s\S]*?)\]/)?.[1] ?? "");
      const src = block.body.match(/\[\[!!([^\]]+)\]\]/)?.[1] ?? "";
      push({
        kind: "image",
        visual: { type: "image", src, alt },
        text: "",
        slug: "image-" + slugify(alt.slice(0, 30)),
        static: true,
        hold: 4.0,
      });
      continue;
    }

    if (block.type === "quote") {
      const lines = block.body
        .split("\n")
        .map((l) => l.replace(/^>\s?/, "").trimEnd())
        .filter((l) => l.trim() !== "");
      const attribution = lines.pop();
      push({
        kind: "poem",
        visual: {
          type: "poem",
          lines: lines.map(flatten),
          attribution: flatten(attribution),
          photo: "assets/radia-perlman-2009.jpg",
        },
        credit: "Read by Radia Perlman",
        audio: join(HERE, "assets/radia-algorhyme.ogg"),
        text: "",
        slug: "poem-algorhyme",
        static: false,
      });
      continue;
    }

    // Paragraphs: mark the cues, flatten, then split at cue sentences.
    //
    // A bullet list arrives as one paragraph. Each bullet is a natural place to
    // break, so they are cut apart here and the short ones folded back together
    // below: a list of one-line items belongs in a single breath, while two
    // bullets of sixty words each do not.
    const chunks = block.body
      .split(/\n(?=\s*[-*] )/)
      .map((chunk) => chunk.replace(/^\s*[-*] /, ""))
      .filter((chunk) => chunk.trim());

    const pieces = [];
    for (const chunk of chunks) {
      const specs = [];
      const { clean, cues } = takeCueOffsets(flatten(markCues(chunk, specs)));
      if (!clean) continue;
      for (const piece of piecesOf(clean, cues))
        pieces.push({ ...piece, specs, chunk: chunks.indexOf(chunk) });
    }

    // Fold short bullets back together, but never across a piece that carries
    // a control link: those have to start their own segment.
    for (let j = 0; j < pieces.length - 1; j++) {
      const here = pieces[j];
      const next = pieces[j + 1];
      if (here.chunk === next.chunk) continue;
      if (here.cues.length || next.cues.length) continue;
      if (
        wordCount(here.text) >= BULLET_MIN_WORDS ||
        wordCount(next.text) >= BULLET_MIN_WORDS
      )
        continue;
      here.text = `${here.text} ${next.text}`.trim();
      pieces.splice(j + 1, 1);
      j--;
    }
    if (!pieces.length) continue;

    // Fold away pieces too short to be worth a take of their own.
    for (let j = 0; j < pieces.length && pieces.length > 1; j++) {
      if (wordCount(pieces[j].text) >= MIN_WORDS) continue;
      const forward = Boolean(pieces[j + 1]);
      const target = pieces[j + 1] ?? pieces[j - 1];
      if (!target) break;
      target.text = forward
        ? (pieces[j].text + " " + target.text).trim()
        : (target.text + " " + pieces[j].text).trim();
      target.cues = forward
        ? [...pieces[j].cues, ...target.cues]
        : [...target.cues, ...pieces[j].cues];
      pieces.splice(j, 1);
      j--;
    }

    for (const piece of pieces) {
      const [primary, ...rest] = piece.cues;
      const specs = piece.specs;
      const spec = primary ? specs[primary.index] : null;
      const kind = spec ? classifyCue(spec) : { mode: "none", slow: false };
      push({
        kind: "prose",
        // Prose that opens a section is about the diagram it is about to
        // show. That diagram has not been parsed yet, but its index is known:
        // it is the next one to be registered.
        visual: {
          type: "topology",
          topology: aheadOfTopology ? topologies.length : topology,
        },
        text: piece.text,
        slug: slugify(piece.text.slice(0, 40)),
        cue: spec
          ? {
              spec,
              at: 0,
              mode: kind.mode,
              slow: kind.slow,
              loop: kind.mode === "step",
            }
          : null,
        extraCues: rest.map((c) => ({
          spec: specs[c.index],
          at: null, // measured against the recording, or hand-set
          ...classifyCue(specs[c.index]),
        })),
        static: kind.mode === "none" || kind.mode === "static",
      });
    }
  }

  // An article ending on prose leaves those segments pointing past the last
  // diagram. Fall back to it.
  for (const segment of segments) {
    if (segment.visual.type !== "topology") continue;
    if (segment.visual.topology >= topologies.length)
      segment.visual.topology = topologies.length - 1;
  }

  // What a topology segment without a cue of its own should show.
  //
  // The article is one continuous exploration: prose after a control link
  // discusses the state that link produced, so the segment replays it and
  // holds there. Prose that comes before any control link on its diagram has
  // no state to inherit, so the simulation simply runs, which is what a reader
  // does when they hit start.
  const lastCue = {};
  for (const segment of segments) {
    if (segment.visual.type !== "topology") continue;
    const topo = segment.visual.topology;
    if (segment.cue) {
      lastCue[topo] = segment.cue;
      continue;
    }
    const previous = lastCue[topo];
    if (previous) {
      segment.inherit = { spec: previous.spec, mode: previous.mode };
      segment.static = previous.mode !== "run";
    } else {
      segment.autorun = true;
      segment.static = false;
    }
  }

  return { segments, topologies, footnotes };
}

// -- output ----------------------------------------------------------

// -- video edits -------------------------------------------------------

// The article is written for a reader who can click. A video cannot, and some
// sentences make no sense read aloud, while some diagrams want splitting or
// replacing. Those changes live in scratch/overrides.json and are applied here,
// keyed by slug so they survive renumbering.

// Edits are patterns, not whole rewrites: an override that stops matching means
// the article moved under it, and that should be loud rather than silent.
function substitute(text, rules, slug) {
  let out = text;
  for (const [pattern, replacement, flags] of rules) {
    const re = new RegExp(pattern, flags ?? "");
    if (!re.test(out))
      throw new Error(`overrides: "${slug}" has no match for /${pattern}/`);
    out = out.replace(re, replacement);
  }
  return out;
}

let overrideNotes = {};

function applyOverrides(result) {
  const path = join(OUT, "overrides.json");
  if (!existsSync(path)) return result;
  const edits = JSON.parse(readFileSync(path, "utf8"));
  overrideNotes = edits.pronunciation ?? {};

  const named = {};
  for (const [name, spec] of Object.entries(edits.topologies ?? {})) {
    let source = typeof spec === "string" ? spec : null;
    if (!source) {
      const from = named[spec.from] ?? spec.from;
      const base = result.topologies[from];
      if (!base) throw new Error(`overrides: unknown topology "${spec.from}"`);
      source = base.source;
      for (const line of spec.drop ?? [])
        source = source
          .split("\n")
          .filter((l) => l.trim() !== line.trim())
          .join("\n");
    }
    named[name] = result.topologies.length;
    result.topologies.push({ id: result.topologies.length, source, name });
  }
  const topologyIndex = (value) =>
    typeof value === "number" ? value : named[value];

  const pointAt = (segment, value) => {
    const index = topologyIndex(value);
    if (index === undefined)
      throw new Error(`overrides: unknown topology "${value}"`);
    segment.visual = { type: "topology", topology: index };
    delete segment.cue;
    delete segment.inherit;
    segment.autorun = true;
    segment.static = false;
  };

  for (const [slug, edit] of Object.entries(edits.sections ?? {}))
    for (const segment of result.segments)
      if (segment.sectionSlug === slug && edit.skip) segment.skip = true;

  const bySlug = new Map(result.segments.map((s) => [s.slug, s]));
  const unused = new Set(Object.keys(edits.segments ?? {}));

  for (const [slug, edit] of Object.entries(edits.segments ?? {})) {
    const segment = bySlug.get(slug);
    if (!segment || !edit.absorb) continue;
    const source = bySlug.get(edit.absorb);
    if (!source)
      throw new Error(`overrides: "${slug}" absorbs unknown "${edit.absorb}"`);
    segment.visual = { ...source.visual };
    if (source.body) segment.body = source.body;
    delete segment.cue;
    delete segment.inherit;
    delete segment.autorun;
    segment.static = true;
    source.skip = true;
  }

  for (const [slug, edit] of Object.entries(edits.segments ?? {})) {
    const segment = bySlug.get(slug);
    if (!segment) continue;
    unused.delete(slug);
    if (edit.skip) segment.skip = true;
    for (const field of HAND_SET)
      if (edit[field] !== undefined) segment[field] = edit[field];
    if (edit.replace)
      segment.text = substitute(segment.text, edit.replace, slug);
    if (edit.hold !== undefined) segment.hold = edit.hold;
    if (edit.topology !== undefined) pointAt(segment, edit.topology);
    // The stage prints the section in a corner, and a run of segments that all
    // let one diagram carry on has to show the same thing throughout, or it
    // cannot be one continuous take.
    if (edit.section !== undefined) segment.section = edit.section;
    if (edit.tail !== undefined) segment.tail = edit.tail;
    if (edit.image) {
      segment.visual = { type: "image", src: edit.image, alt: edit.alt ?? "" };
      delete segment.cue;
      delete segment.inherit;
      delete segment.autorun;
      segment.static = true;
    }
  }

  for (const [slug, edit] of Object.entries(edits.segments ?? {})) {
    if (!edit.splitAt) continue;
    const at = result.segments.findIndex((s) => s.slug === slug);
    if (at < 0) continue;
    unused.delete(slug);
    const original = result.segments[at];
    const cut = original.text.search(new RegExp(edit.splitAt));
    if (cut < 0)
      throw new Error(
        `overrides: "${slug}" has no match for splitAt ${edit.splitAt}`,
      );
    const halves = [
      original.text.slice(0, cut).trim(),
      original.text.slice(cut).trim(),
    ];
    const pieces = (edit.pieces ?? [{}, {}]).map((piece, i) => {
      const next = { ...original, ...piece, text: halves[i] ?? "" };
      next.slug = piece.slug ?? `${original.slug}-${i + 1}`;
      if (piece.replace)
        next.text = substitute(next.text, piece.replace, next.slug);
      if (piece.topology !== undefined) pointAt(next, piece.topology);
      delete next.pieces;
      delete next.splitAt;
      delete next.replace;
      return next;
    });
    result.segments.splice(at, 1, ...pieces);
  }

  for (const slug of unused)
    throw new Error(`overrides: no segment matches "${slug}"`);

  // Slugs name every artefact on disk and every recording, so two paragraphs
  // that happen to open the same way must not end up sharing one.
  const taken = new Set();
  for (const segment of result.segments) {
    let slug = segment.slug;
    for (let n = 2; taken.has(slug); n++) slug = `${segment.slug}-${n}`;
    taken.add(slug);
    segment.slug = slug;
  }

  result.segments.forEach((segment, i) => {
    segment.id = String(i + 1).padStart(3, "0");
  });
  return result;
}

// -- pronunciation -----------------------------------------------------

// What is actually worth rehearsing is decided by the script, not by guesswork:
// the words it uses that a dictionary does not know, the acronyms, the names,
// and the bridge labels that come up on nearly every page. espeak-ng supplies
// the phonetics; overrides.json supplies the judgement calls it cannot make,
// like how to say a bridge name aloud.
const DICTIONARIES = [
  "/usr/share/dict/american-english",
  "/usr/share/dict/words",
];

function loadDictionary() {
  for (const path of DICTIONARIES)
    if (existsSync(path))
      return new Set(
        readFileSync(path, "utf8")
          .split("\n")
          .map((w) => w.trim().toLowerCase())
          .filter(Boolean),
      );
  return new Set();
}

// S1, R0, H4 and friends. They are read constantly, and what matters is saying
// them the same way every time, so they are collected as one family each.
const IDENTIFIER = /^([A-Z]{1,3})(\d+)$/;

function candidates(segments, notes) {
  const dictionary = loadDictionary();
  // A word someone has written a note for is in the guide whatever the
  // dictionary thinks: "designated" is ordinary English and still the one most
  // worth settling.
  const noted = new Set(Object.keys(notes).map((w) => w.toLowerCase()));
  const counts = new Map();
  const families = new Map();

  for (const segment of segments) {
    if (!segment.text || segment.skip) continue;
    for (const raw of segment.text.split(/[^\p{L}\p{N}'\u2019-]+/u)) {
      const word = raw.replace(/[\u2019']s$/, "");
      if (word.length < 2) continue;

      const identifier = word.match(IDENTIFIER);
      if (identifier) {
        const family = families.get(identifier[1]) ?? {
          count: 0,
          seen: new Set(),
        };
        family.count += 1;
        family.seen.add(word);
        families.set(identifier[1], family);
        continue;
      }
      // A part number is not a bridge label and not a plain number, so it only
      // gets in when someone has said how to read it: Cisco 2960X.
      if (/\d/.test(word)) {
        if (notes[word]) counts.set(word, (counts.get(word) ?? 0) + 1);
        continue;
      }

      const bare = word.replace(/[^\p{L}]/gu, "").toLowerCase();
      if (!bare) continue;
      // don't, you'd, That's: the dictionary lacks the contraction, not the word.
      const stem = word.split(/['\u2019]/)[0].toLowerCase();
      if (stem !== word.toLowerCase() && dictionary.has(stem)) continue;
      const acronym = /^[A-Z]{2,}s?$/.test(word);
      if (!acronym && !noted.has(bare) && dictionary.has(bare)) continue;
      counts.set(word, (counts.get(word) ?? 0) + 1);
    }
  }
  return { counts, families };
}

const LETTER_NAMES = {
  a: "ay",
  b: "bee",
  c: "see",
  d: "dee",
  e: "ee",
  f: "eff",
  g: "jee",
  h: "aitch",
  i: "eye",
  j: "jay",
  k: "kay",
  l: "ell",
  m: "em",
  n: "en",
  o: "oh",
  p: "pee",
  q: "cue",
  r: "arr",
  s: "ess",
  t: "tee",
  u: "you",
  v: "vee",
  w: "double-you",
  x: "ex",
  y: "why",
  z: "zed",
};

// espeak tries to say an initialism rather than spell it, which gives
// "e-stee-PEE" for STP. Letters are mechanical, so spell them here and leave
// the exceptions — the ones said as a word, like DEC or MAC — to overrides.
function spellLetters(word) {
  const plural = /[A-Z0-9]s$/.test(word);
  const names = [...(plural ? word.slice(0, -1) : word)].map(
    (c) => LETTER_NAMES[c.toLowerCase()] ?? c,
  );
  // The plural rides on the last letter: BPDUs is bee-pee-dee-youz.
  if (plural && names.length) names[names.length - 1] += "z";
  return names.join("-");
}

function phonetics(words) {
  if (!words.length) return {};
  try {
    const out = execFileSync("espeak-ng", ["-q", "--ipa", "-v", "en-us"], {
      input: words.join(",\n"),
      encoding: "utf8",
    });
    const parts = out.trim().split(/\s*\n\s*/);
    return Object.fromEntries(
      words.map((w, i) => [
        w,
        /^[A-Z0-9]{2,}s?$/.test(w)
          ? spellLetters(w)
          : respell((parts[i] ?? "").trim()),
      ]),
    );
  } catch {
    return {};
  }
}

const ONES = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
  "thirteen",
  "fourteen",
  "fifteen",
  "sixteen",
  "seventeen",
  "eighteen",
  "nineteen",
];
const TENS = [
  "",
  "",
  "twenty",
  "thirty",
  "forty",
  "fifty",
  "sixty",
  "seventy",
  "eighty",
  "ninety",
];

function spellNumber(n) {
  if (n < 20) return ONES[n];
  if (n < 100)
    return TENS[Math.floor(n / 10)] + (n % 10 ? `-${ONES[n % 10]}` : "");
  if (n < 1000)
    return `${ONES[Math.floor(n / 100)]} hundred${n % 100 ? ` ${spellNumber(n % 100)}` : ""}`;
  if (n < 1000000)
    return `${spellNumber(Math.floor(n / 1000))} thousand${
      n % 1000 ? ` ${spellNumber(n % 1000)}` : ""
    }`;
  return String(n);
}

const DIGIT_NAMES = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
];

// A MAC is read as six octets with no colons said aloud, each with its leading
// zero dropped: 02:00:00:00:00:01 is "two, zero, zero, zero, zero, one".
function spellMac(mac) {
  return mac
    .toLowerCase()
    .split(":")
    .map((octet) => {
      const trimmed = octet.replace(/^0+(?=.)/, "");
      return [...trimmed].map((c) => DIGIT_NAMES[Number(c)] ?? c).join(" ");
    })
    .join(", ");
}

// The numbers and identifiers the script actually contains. Said inconsistently
// across half an hour they are what a listener notices, so each one gets a form
// to settle on.
function numberGuide(segments, notes) {
  const text = segments
    .filter((s) => s.text && !s.skip)
    .map((s) => s.text)
    .join(" ");

  const patterns = [
    ["bridge id", /\b\d+\.(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b/gi],
    ["MAC", /\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b/gi],
    ["hex", /\b0x[0-9a-f]+\b/gi],
    ["number", /\b\d{1,3}(?:,\d{3})+\b/g],
  ];

  const seen = new Set();
  const rows = [];
  for (const [kind, pattern] of patterns) {
    const counts = new Map();
    for (const match of text.match(pattern) ?? []) {
      if ([...seen].some((s) => s.includes(match))) continue;
      counts.set(match, (counts.get(match) ?? 0) + 1);
    }
    for (const [value, n] of [...counts.entries()].sort(
      (a, b) => b[1] - a[1],
    )) {
      seen.add(value);
      let say = notes[value] ?? "";
      if (!say && kind === "number")
        say = spellNumber(Number(value.replace(/,/g, "")));
      if (!say && kind === "MAC") say = spellMac(value);
      if (!say && kind === "bridge id") {
        const [priority, ...mac] = value.split(".");
        say = `priority ${spellNumber(Number(priority))}, then ${spellMac(mac.join("."))}`;
      }
      rows.push({ value, kind, n, say });
    }
  }
  return rows;
}

function pronunciationGuide(segments, notes) {
  const { counts, families } = candidates(segments, notes);
  const numbers = numberGuide(segments, notes);
  const words = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const sounds = phonetics(words.map(([w]) => w));

  const lines = [
    "# Pronunciation notes",
    "",
    "Built from the script, ordered by how often each turns up, so the ones at",
    "the top are the ones worth settling first. The respelling comes from",
    "espeak-ng, with the stressed syllable in capitals; it is a rules-based",
    "guess, so treat a name as a suggestion. The notes are from overrides.json.",
    "",
    "## Numbers and identifiers",
    "",
    "| Written | Times | Say |",
    "|---|---|---|",
    ...numberGuide(segments, notes).map(
      (r) => `| \`${r.value}\` | ${r.n} | ${r.say} |`,
    ),
    "",
    "## Bridge and port names",
    "",
    "Read constantly, so pick one way and keep it.",
    "",
    "| Family | Seen | Times | Note |",
    "|---|---|---|---|",
  ];
  for (const [prefix, family] of [...families.entries()].sort(
    (a, b) => b[1].count - a[1].count,
  )) {
    const seen = [...family.seen].sort();
    const range =
      seen.length > 3
        ? `${seen[0]}\u2026${seen[seen.length - 1]}`
        : seen.join(", ");
    lines.push(
      `| ${prefix}n | ${range} | ${family.count} | ${notes[prefix + "n"] ?? ""} |`,
    );
  }

  lines.push(
    "",
    "## Words",
    "",
    "| Word | Times | Say | Note |",
    "|---|---|---|---|",
  );
  for (const [word, n] of words)
    lines.push(
      `| ${word} | ${n} | ${sounds[word] ?? ""} | ${notes[word] ?? ""} |`,
    );
  lines.push("");

  // What the recorder shows beside a segment. Each entry carries the pattern
  // that finds it in the text: a word on its own, a bridge family by its shape,
  // a number or MAC literally.
  const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // An acronym is matched as written: \bUS with a case-insensitive flag lights
  // up on "user", "used" and "using".
  const flagsFor = (label) => (/^[A-Z0-9]{2,}$/.test(label) ? "" : "i");
  const map = [];
  for (const [prefix, family] of families)
    if (notes[prefix + "n"])
      map.push({
        label: `${[...family.seen].sort().slice(0, 2).join(", ")}\u2026`,
        say: notes[prefix + "n"],
        match: `\\b${prefix}\\d+\\b`,
        flags: "",
      });
  for (const [word] of words)
    if (notes[word] || sounds[word])
      map.push({
        label: word,
        say: notes[word] ?? sounds[word],
        match: `\\b${escape(word)}\\b`,
        flags: flagsFor(word),
      });
  for (const row of numbers)
    if (row.say)
      map.push({
        label: row.value,
        say: row.say,
        match: `${escape(row.value)}\\b`,
        flags: "",
      });
  return { text: lines.join("\n"), map };
}

const article = stripFrontMatter(readFileSync(ARTICLE, "utf8"));
const result = applyOverrides(build(parseBlocks(article)));

for (const seg of result.segments) {
  if (!seg.text) continue;
  seg.words = wordCount(seg.text);
  seg.estimate = Number(estimate(seg.text).toFixed(2));
}

const output = {
  source: ARTICLE,
  fps: 30,
  width: 1920,
  height: 1080,
  loopGap: 1.2,
  segmentGap: 0.45,
  topologies: result.topologies,
  footnotes: result.footnotes,
  segments: result.segments,
};

mkdirSync(SCRIPT_DIR, { recursive: true });
for (const f of readdirSync(SCRIPT_DIR)) rmSync(join(SCRIPT_DIR, f));
for (const seg of output.segments) {
  if (!seg.text) continue;
  writeFileSync(
    join(SCRIPT_DIR, seg.id + "-" + seg.slug + ".txt"),
    seg.text + "\n",
  );
}
mkdirSync(join(OUT, "out"), { recursive: true });
writeFileSync(DERIVED, JSON.stringify(output, null, 2) + "\n");
const guide = pronunciationGuide(output.segments, overrideNotes);
output.pronunciation = guide.map;
writeFileSync(DERIVED, JSON.stringify(output, null, 2) + "\n");
writeFileSync(join(OUT, "PRONUNCIATION.md"), guide.text);

const counts = {};
for (const s of output.segments)
  counts[s.visual.type] = (counts[s.visual.type] ?? 0) + 1;
const cued = output.segments.filter((s) => s.cue).length;
const extra = output.segments.reduce(
  (n, s) => n + (s.extraCues?.length ?? 0),
  0,
);
const spoken = output.segments.filter((s) => s.text).length;
const total = output.segments.reduce(
  (n, s) => n + (s.estimate ?? s.hold ?? 0),
  0,
);

console.log(
  "segments      " + output.segments.length + " (" + spoken + " spoken)",
);
console.log("topologies    " + output.topologies.length);
console.log(
  "cues          " + cued + " at segment start, " + extra + " mid-segment",
);
console.log("footnotes     " + result.footnotes.length + " (not narrated)");
console.log("by visual     " + JSON.stringify(counts));
console.log("rough length  " + Math.round(total / 60) + " min");
