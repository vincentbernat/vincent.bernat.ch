// Splitting prose the way both the cue sheet and the subtitles need it.

export const ABBREVIATIONS = [
  "e.g",
  "i.e",
  "etc",
  "vs",
  "cf",
  "Mr",
  "Ms",
  "Dr",
  "Fig",
  "No",
  "approx",
];

export function splitSentences(text) {
  const out = [];
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    if (!".!?".includes(text[i])) continue;
    if (/\d/.test(text[i - 1] ?? "") && /\d/.test(text[i + 1] ?? "")) continue;
    const rest = text.slice(i + 1);
    const gap = rest.match(/^\s+/);
    if (!gap) continue;
    if (!/^[A-Z"“(]/.test(rest.slice(gap[0].length))) continue;
    const before = text.slice(start, i);
    const lastWord = before.split(/[\s(]/).pop();
    if (ABBREVIATIONS.some((a) => lastWord === a || lastWord.endsWith("." + a)))
      continue;
    if (/(^|[\s(])[A-Z]$/.test(before)) continue;
    out.push(text.slice(start, i + 1).trim());
    start = i + 1 + gap[0].length;
  }
  const tail = text.slice(start).trim();
  if (tail) out.push(tail);
  return out.length ? out : [text];
}
