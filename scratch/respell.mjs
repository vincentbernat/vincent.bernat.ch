// espeak-ng speaks IPA, which is precise and unreadable unless you already know
// it. This turns its output into the kind of respelling a dictionary puts in
// brackets: DE-zig-nay-tid, with the stressed syllable in capitals.

const VOWELS = {
  aɪɚ: "ire",
  aʊɚ: "ower",
  ɔːɹ: "or",
  ɑːɹ: "ar",
  ɛɹ: "air",
  ɪɹ: "eer",
  ʊɹ: "oor",
  ɔɪ: "oy",
  aɪ: "y",
  aʊ: "ow",
  eɪ: "ay",
  oʊ: "oh",
  iː: "ee",
  uː: "oo",
  ɜː: "ur",
  ɑː: "ah",
  ɔː: "aw",
  ɪə: "eer",
  ɚ: "er",
  ɝ: "ur",
  ɪ: "i",
  ɛ: "e",
  æ: "a",
  ʊ: "uu",
  ʌ: "u",
  ə: "uh",
  ᵻ: "i",
  ɐ: "uh",
  ɒ: "o",
  e: "e",
  i: "i",
  u: "oo",
  o: "oh",
};
const CONSONANTS = {
  tʃ: "ch",
  dʒ: "j",
  θ: "th",
  ð: "th",
  ʃ: "sh",
  ʒ: "zh",
  ŋ: "ng",
  ɹ: "r",
  ɾ: "t",
  ʔ: "",
  ɡ: "g",
  j: "y",
  x: "kh",
};
for (const c of "pbtdkfvszmnlrwh") CONSONANTS[c] = c;

const SYLLABIC = { n̩: "uhn", l̩: "uhl", m̩: "uhm" };
Object.assign(VOWELS, SYLLABIC);

const ONSETS = new Set([
  "bl",
  "br",
  "kl",
  "kr",
  "dr",
  "fl",
  "fr",
  "gl",
  "gr",
  "pl",
  "pr",
  "sl",
  "sm",
  "sn",
  "sp",
  "st",
  "sw",
  "tr",
  "tw",
  "thr",
  "sk",
  "spr",
  "str",
  "skr",
  "shr",
  "kw",
  "sf",
  "sv",
  "skw",
]);

const OPENERS = { y: "eye", ow: "ow", oy: "oy" };

const KEYS = [...Object.keys(VOWELS), ...Object.keys(CONSONANTS)].sort(
  (a, b) => b.length - a.length,
);

export function respell(ipa) {
  const units = [];
  let stressNext = false;
  for (let i = 0; i < ipa.length; ) {
    const ch = ipa[i];
    if (ch === "ˈ") {
      stressNext = true;
      i++;
      continue;
    }
    if (ch === "ˌ" || ch === "ː" || ch === "͡" || ch === "‍") {
      i++;
      continue;
    }
    if (ch === " ") {
      units.push({ kind: "space" });
      i++;
      continue;
    }
    const key = KEYS.find((k) => ipa.startsWith(k, i));
    if (!key) {
      i++;
      continue;
    }
    const vowel = key in VOWELS;
    units.push({
      kind: vowel ? "vowel" : "cons",
      text: vowel ? VOWELS[key] : CONSONANTS[key],
      stress: stressNext,
    });
    stressNext = false;
    i += key.length;
  }

  const syllables = [];
  let current = null;
  let pending = [];
  for (const unit of units) {
    if (unit.kind === "space") {
      if (current) {
        current.text += pending.map((p) => p.text).join("");
        syllables.push(current);
      } else if (pending.length)
        syllables.push({ text: pending.map((p) => p.text).join("") });
      current = null;
      syllables.push({ text: " ", space: true });
      pending = [];
      continue;
    }
    if (unit.kind === "vowel") {
      // The consonant right before a vowel opens its syllable; anything earlier
      // closes the one before.
      let onset = [];
      for (let take = Math.min(3, pending.length); take >= 1; take--) {
        const cluster = pending
          .slice(-take)
          .map((p) => p.text)
          .join("");
        if (take === 1 || ONSETS.has(cluster)) {
          onset = pending.splice(pending.length - take, take);
          break;
        }
      }
      if (current) {
        current.text += pending.map((p) => p.text).join("");
        syllables.push(current);
      } else if (pending.length)
        syllables.push({ text: pending.map((p) => p.text).join("") });
      current = {
        // A diphthong written "y" reads as a consonant when it opens a
        // syllable: identifier would come out y-DEN-ti-fire.
        text:
          onset.map((o) => o.text).join("") +
          (!onset.length && OPENERS[unit.text]
            ? OPENERS[unit.text]
            : unit.text),
        stress: unit.stress,
      };
      pending = [];
    } else {
      pending.push(unit);
    }
  }
  if (current) {
    current.text += pending.map((p) => p.text).join("");
    syllables.push(current);
  } else if (pending.length)
    syllables.push({ text: pending.map((p) => p.text).join("") });

  const out = [];
  for (const s of syllables) {
    if (s.space) {
      out.push(" ");
      continue;
    }
    if (!s.text) continue;
    out.push(s.stress ? s.text.toUpperCase() : s.text);
  }
  return out.join("-").replace(/-? -?/g, " ").replace(/^-|-$/g, "");
}
