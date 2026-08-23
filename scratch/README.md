# Spanning tree article -> video

Turns `content/en/blog/2026-spanning-tree.html` into a narrated video, with the
article's own interactive diagrams running for real: the stage loads the same
CSS and JavaScript the site does, and the simulations are MSTPD compiled to
WebAssembly, exactly as a reader sees them.

This was coded mostly by Claude Opus 5 and the code may be a bit brittle and was
tested empirically, but its only goal is to produce the video artifact.

## The pieces

| File                  | What it does                                                         |
| --------------------- | -------------------------------------------------------------------- |
| `pipeline.mjs`        | The whole run, in order, stopping if the narration is behind         |
| `extract.mjs`         | Article -> `out/segments.json` + `script/*.txt` + `PRONUNCIATION.md` |
| `overrides.json`      | The video's edits to the article: wording, diagrams, cuts            |
| `highlight.py`        | Renders the code blocks with the site's own Pygments lexers          |
| `serve.mjs`           | Static server for the stage, on port 8081                            |
| `stage.*`             | The 1080p stage: one segment on screen                               |
| `browser.sh`          | Starts the headless browser the recorder drives                      |
| `cdp.mjs`             | Minimal DevTools protocol client, no dependencies                    |
| `shot.mjs`            | One frame of one segment, to check how it looks                      |
| `record-audio.html`   | Teleprompter and recorder for the narration                          |
| `recorder-worklet.js` | Microphone capture for it                                            |
| `record.mjs`          | Renders segments to video, straight out of the browser               |
| `models/`             | whisper.cpp GGML model and the piper voice                           |
| `out/`                | everything derived: segments.json, blocks, clips, stills, the MP4    |
| `assemble.mjs`        | Clips + narration -> the final MP4, with chapters and subtitles      |
| `text.mjs`            | Sentence splitting, shared by the cue sheet and the subtitles        |
| `runs.mjs`            | Groups continuous autorun segments, shared by both                   |
| `align.mjs`           | Word timings from whisper.cpp, for subtitles and the poem            |
| `respell.mjs`         | espeak-ng IPA -> DE-zig-nay-tid                                      |
| `coverage.mjs`        | Measures how much of its script each take reached                    |
| `normalize-takes.mjs` | Gives takes recorded earlier the same lead-in as new ones            |

## Running it

Two things stay up in their own terminals, because both outlive a run:

```sh
node serve.mjs            # the stage and the recorder, on :8081
sh browser.sh             # the headless browser the recorder drives
```

Then one command does the rest:

```sh
node pipeline.mjs --all   # -> out/spanning-tree.mp4 + .en.vtt
```

It runs `extract.mjs`, then `highlight.py`, then looks at the narration, then
`record.mjs` and `assemble.mjs`. The selection is passed on to the last two, so
`--section electing-the-root-bridge` works the same way there.

The narration check is the reason this is a script and not a paragraph of
instructions. It stops before the render when a segment has no recording, when
a take was read from wording the article has since changed, or when a reading
stopped short of the end of its script — the three things the recorder page
marks in its sidebar, worked out from the same files. All three are fixed at
`http://127.0.0.1:8081/record-audio.html`, so it stops rather than spending an
hour rendering the wrong thing. `--check` stops there in any case, `--no-check`
carries on regardless, and a segment with no take then becomes silence as long
as its word count suggests.

It also names recordings whose paragraph has gone from the article. Those are
harmless at assembly and cannot be fixed in the browser, so they are printed
and nothing more.

Paths are anchored to each script rather than to the working directory, so
running them from the repository root works too, and the steps remain ordinary
scripts: any one of them can still be run on its own.

After editing `overrides.json` or the article, re-run `extract.mjs` (and
`highlight.py` if a code block changed) and reload the page. The server picks up
the new `out/segments.json` by itself — it only needs restarting when
`serve.mjs` changes.

`record.mjs` and `assemble.mjs` both need to be told what to work on: `--all`,
`--segment <id|slug>` or `--section <slug>`. Naming one is how to iterate
without re-rendering half an hour of video, and requiring it means a bare
invocation cannot start an hour of work by accident.
`record.mjs --segment <slug> --preview` writes a single PNG, and `--force`
renders even when the cache says it need not. `assemble.mjs --no-align` times
subtitles by proportion rather than by whisper. Both commands accept a slug as
well as a number, and the slug is steadier: numbers shift when a segment is
added.

A render is reused when the segment is unchanged, and also when it only got
_shorter_ — the clip is cut down at assembly instead. `record.mjs` notes where
each animation comes to rest so the cut never lands mid-flight. Growing longer
still needs a fresh render, which is why the word-rate estimate is set below the
measured pace: a guess that runs long costs nothing.

The browser runs outside the sandbox this was built in, so it is started by hand
rather than by the recorder. It only ever needs `scratch/`: everything else
reaches it over HTTP.

## Recording the narration

Open `http://127.0.0.1:8081/record-audio.html`. It shows one segment at a time,
in order, with the ones already done ticked off down the side.

| Key     | Action                                         |
| ------- | ---------------------------------------------- |
| `Space` | start recording, press again to stop and save  |
| `P`     | play the chosen take                           |
| `H`     | hear the line read by piper, before you say it |
| `S`     | make a take with the cloned voice instead      |
| `Esc`   | stop whatever is playing                       |
| `←` `→` | move between segments                          |

Ninety-six segments, about 3,800 words, roughly half an hour of finished audio.

Capture is an `AudioWorklet`, not `MediaRecorder`, so what leaves the browser is
exactly what came off the microphone. `getUserMedia` is asked for raw input —
echo cancellation, noise suppression and automatic gain all off — because the
levelling happens once, over the whole video, in `assemble.mjs`. Letting the
browser ride the gain per segment would make them inconsistent with each other.
The meter turns red past 95% so clipping is visible.

Takes are stored as 128 kbps mono MP3; `AUDIO_BITRATE` changes that. Every take
is kept under `audio/takes/`, and the recorder lists them with their length so
any one can be played, chosen or deleted. The chosen one is copied to
`audio/NNN-slug.mp3`, which is what the pipeline reads.

## The cloned voice

`Synthesize` sends the segment's script to ElevenLabs and files the result as a
take, so a segment can be filled without a microphone. It needs
`ELEVENLABS_API_KEY` in the environment; without it the button answers 503 and
nothing else changes.

A picker chooses between the voices listed in `ELEVEN_VOICES` in `serve.mjs`,
each with its id and a short label. `ELEVENLABS_VOICE` sets which one starts
selected, by id or by name, and `ELEVENLABS_MODEL` picks the model. Adding a
voice means one line in that list.

Four sliders tune the voice: speed (0.7 to 1.2), stability, similarity and style
exaggeration (each 0 to 100%). They and the chosen voice are global, not per
segment, and are saved in `audio/takes/voice.json`, so they outlive a reload and
every later take is made the same way. Deleting that file goes back to the tuned
defaults — speed 0.96, stability 56%, similarity 44%, style 6% — which are the
constants in `serve.mjs`. Values are clamped on the way in, so a bad request
cannot put the voice out of range.

### When it says a word wrong

The dictionary is made and edited in the ElevenLabs interface, the same way the
voices are, and its id sits beside them in `serve.mjs`
(`ELEVENLABS_DICTIONARY` overrides it). It is attached to every synthesis. No
version is sent, so the newest one is always used and editing a rule there takes
effect on the next take, with nothing to change here. The server prints which
voice and dictionary it will use when it starts.

Alias rules — plain replacements, `VXLAN` to `vee-ex-lan` — work on any model.
The IPA and CMU phoneme rules the interface also offers are exact, but only
`eleven_flash_v2` and `eleven_v3` apply them; `eleven_multilingual_v2` ignores
them silently. `ELEVENLABS_MODEL` picks the model.

Both kinds of take sit in the same list and compete on equal terms: same
numbering, same coverage measurement, same `use` and `delete`. Which one is
which is recorded in `audio/takes/origins.json` and shown in the table as `mic`
or as the voice that said it, so a synthesized take can never be mistaken for a
read one, and two voices cannot be confused with each other. Takes made before
this existed count as `mic`.

Every take is saved with the same lead-in: whatever silence it opens with is
cut, and 0.15 s is put back. `AUDIO_LEAD` changes that. This matters because the
cue fires with the first frame of video, so a take opening on a second of room
tone would animate in silence while the next one speaks at once — and left
alone, the pause between segments would be the 0.45 s gap plus whatever silence
the next take happened to start with. Recordings varied between 0.06 s and
1.09 s; the API starts on the first syllable.

`node normalize-takes.mjs` gives takes recorded before this the same treatment,
in place, and refreshes the copy under `audio/` for any it changes.
`--dry-run` lists what it would do. It is safe to run twice: a take already at
the right lead-in is left alone. Durations shift by a tenth of a second or so,
so re-run `record.mjs` and `assemble.mjs` afterwards — alignment caches key on
the file's size and time, so subtitles re-time themselves.

Each take also shows how much of its script it covers. A take that was stopped
early leaves the tail of the script with nothing to match, so the count of
script words present in the transcript says how far the reading got — counting
how _far in_ a match lands does not work, because a four-second fragment can
still throw one stray match near the end and look complete. Under 90% is marked
"cut short", and the sidebar marks the segment. It is measured after the take is
saved, not before the reply, so recording never waits on whisper; the figure
appears on its own a few seconds later. `node coverage.mjs` measures takes
recorded before this existed.

The sidebar marks each segment: a check when its chosen take is good, a warning
when the script has changed since it was read, scissors when the take is cut
short.

Nothing forces you to use this page: the pipeline only wants files named
`audio/NNN-slug.<ext>` matching `script/NNN-slug.txt`, in any
format ffmpeg reads — the number in front is ignored, the slug is what matches.
`AUDIO_DIR` points both scripts at a different directory.

After recording, re-run `record.mjs` and `assemble.mjs`: segments whose duration
changed are re-rendered or trimmed, the rest are cached, and the subtitles
re-time themselves against the new audio.

## Saying it right

Two things sit under the script, and they answer different questions.

**Click any word** and its respelling appears; click it again and piper says
just that word. This is the one that matters. What is hard to pronounce is not
something a word list can know in advance — "neighbor" and "thorough" are
ordinary English and awkward, while half of what a guess would flag never
appears in the article at all. So there is no filter here: look up whatever you
are unsure of, on the word in front of you.

**`PRONUNCIATION.md`** is the shortlist that appears by itself when you land on
a segment, built from the script rather than from imagination:

- every word the system dictionary does not know, every acronym, every name,
  ordered by how often you will actually say it;
- the bridge and port names as families — `Sn` alone comes up 199 times, and
  what matters is saying them the same way every time;
- every number, MAC and hex literal in the script, with plain integers spelled
  out automatically;
- anything with a note in `overrides.json`, dictionary word or not. That
  exception exists because the filter would otherwise drop `designated`, the
  most-repeated awkward word in the article.

Respellings come from espeak-ng through `respell.mjs`, which turns its IPA into
`DE-zig-nay-tid` with the stress in capitals. It is a rules-based guess and it
is wrong on names — `VLAN-aware` comes out "v-LA-nuh-WAIR". That is what the
note column is for: a hand-written decision in `overrides.json` sits beside the
machine guess, and wins.

## How segments work

`extract.mjs` cuts the article into segments, splitting a paragraph wherever an
`#mstp:` control link appears, so every cue lands at the start of its own
segment and fires the moment its narration does. No timing to tune.

Each topology segment does one of three things:

- **cue** — plays the control link from the article. A cue that ends on a step
  count animates one step, so it replays under a long sentence, leaving
  `loopGap` seconds between plays and only starting a replay that has room to
  finish. A cue ending in `...` leaves the simulation running.
- **inherit** — no link of its own, so it replays the last one on that diagram
  and holds there. That is the state the prose is talking about.
- **autorun** — prose that comes before any link on its diagram, so the
  simulation just runs, which is what a reader does when they hit start.

Segments where nothing moves are kept as a single frame in `out/stills/<slug>.png` and
stretched by ffmpeg at assembly time, which is what keeps a half-hour render at
30 fps affordable, and what makes swapping a recording almost free.

Consecutive segments that only let a diagram run are one continuous take, and
are rendered as a single clip in `out/clips-raw/run-<slug>.mp4` with each
segment's piece cut out of it at assembly. That matters because such a segment
starts wherever the ones before it finished: shortening an early one used to
move every later one to a different part of the animation, which no amount of
trimming can produce. Now it only re-cuts, and a fresh render is needed only
when the run's _total_ grows past what was captured.

A run ends at a change of diagram, at the first segment that does more than let
it run, and at a heading, since the stage prints the section in a corner — which
is why the opening demo sets `"section": ""` on the segments after its heading,
so all three are one take and the simulation never restarts under them. Cards
with no diagram, a title or a packet dump, do not end a run: the simulation
pauses under them and carries on.

Neither script stores the offsets. `runs.mjs` works them out from the durations
in front of it, so re-recording one segment cannot leave a later one pointing at
the wrong frames; where the manifest and the plan disagree, `assemble.mjs` says
so rather than cutting the wrong window.

Segments that move are encoded as they are captured: frames go straight from
the browser into an ffmpeg on stdin, writing `out/clips-raw/<slug>.mp4`. At 1080p
a PNG frame is about 110 kB, so keeping them would cost several gigabytes a
render. The pause after each segment is held on the last frame and baked into
that clip, so assembly copies the video through and only encodes audio.

The finished file is a master, not a delivery copy: `video2hls` re-encodes it
for streaming (see the snippet at the end of `tasks.py`), and that is where the
picture is allowed to suffer. So every clip is x264 at CRF 12 (`X264_CRF`),
well above what a viewer needs, and the final join copies the video through
untouched — the audio is the only thing mixed there. A segment cut out of a
run, a trimmed clip and a still are encoded a second time at assembly, at the
same CRF, which is why the number is shared between the two scripts. Diagrams
are flat colour, so this costs little: a clip lands near 500 kbit/s at 1080p.

CRF is part of what a clip is fingerprinted on. Change it and everything is
captured again, rather than the render quietly mixing two qualities.

`tail` on a segment adds seconds of diagram after the narration stops.

There are exactly two files a human writes: `overrides.json` and the article
itself. Everything else under `out/` is derived and can be deleted at any time —
`out/segments.json`, the rendered code blocks, the clips, the stills. That is
why the poem timings and any `holdOverride` live in `overrides.json` rather than
in the cue sheet: losing `out/` should cost render time, never work.

## The poem

"Historical interlude" cuts to `content/media/files/stp-algorhyme.ogg`, which is
Radia Perlman reading Algorhyme herself. The segment takes its length from that
file and needs no recording. Her lines light up one at a time, timed by the same
forced alignment used for the subtitles, brought forward a quarter of a second
so the highlight arrives just before the words rather than with them. Her audio
is left out of the loudness pass so it keeps its own character. The photograph
is from Wikimedia Commons and is public domain.

## The final level

Each segment is levelled on its own to -16 LUFS with a -2 dBFS ceiling, so the
loudest moment of the finished video lands wherever it lands rather than at the
ceiling — measured at -4.5 dBFS. `assemble.mjs` lifts the whole mix by
`AUDIO_GAIN`, 2.5 dB by default, which puts that peak back at -2 dBFS. It is one
gain over the join, not per segment, so nothing shifts relative to anything
else.

## The music

A piano bed runs under the whole video: [Aaron Dunn's recording of Muzio
Clementi's Sonatina no. 2 in G major, third movement][chosic], in `assets/`. It
is 2m25s long and the video is far longer, so it plays on repeat.

[chosic]: https://www.chosic.com/download-audio/25044/

`assemble.mjs` measures the file once and shifts the whole thing to
`MUSIC_LUFS`, -33 by default, about 17 LU under the narration. A fixed gain,
not `loudnorm`: a bed should keep the dynamics of the playing, and squashing it
flat is what makes background music tiring. It fades in over the first four
seconds and out over the last four.

Under the poem the bed drops to half its level. The ramps sit outside the
segment rather than inside it, so it is already down when Radia starts and only
comes back up once she has finished.

`MUSIC` points at a different file. Changing the bed only re-runs the final
join, since the per-segment clips are untouched.

## Why a slug, and what it cannot tell you

Everything on disk is named by slug — clips, stills, rendered code blocks,
alignment caches, recordings — so adding or removing a segment renumbers the
script files without invalidating a single render or orphaning a recording.
Slugs are made unique at extraction: two paragraphs opening the same way would
otherwise share one clip and one recording.

The catch is that a slug comes from the _opening_ words of a paragraph, so
editing the end of one leaves the name unchanged.

For rendering that does not matter: a clip is keyed by a hash of the whole
segment — text, visual, cue — so any edit invalidates it.

A recording is different. It is found by slug alone, so an edited paragraph
would otherwise leave the old audio paired with the new script, and nothing
would say so. Each take is stamped with a hash of the script it was read from,
in `audio/takes/scripts.json`. The recorder marks a stale take in its list and
puts a warning beside the segment, and `assemble.mjs` lists them when it
finishes. Re-record, or accept it knowingly.
