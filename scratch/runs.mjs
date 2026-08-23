// Consecutive segments that just let a diagram run belong to one continuous
// take. Rendering them as a single clip and cutting the pieces out of it means
// that moving time from one to another costs a re-slice rather than a
// re-render of everything after it.
//
// The beat between two segments belongs to the run as well: the words stop for
// it, the diagram must not. So each member holds its own length plus one gap,
// and the take is rendered long enough to cover them all.
//
// Both the recorder and the assembler work the chains out the same way, from
// the durations they have in front of them. Storing an offset would be wrong:
// it depends on the segments before it, so re-recording any of them would leave
// every later offset pointing at the wrong frames with nothing to say so.

export function planRuns(segments, secondsOf, gap) {
  const runs = new Map();
  const runOf = {};
  let current = null;

  for (const segment of segments) {
    // A card with no diagram on it — a section title, a packet dump — does not
    // interrupt a run: when the diagram comes back it should carry on rather
    // than start over.
    if (segment.visual.type !== "topology") continue;
    // A segment cut from the video is not rendered and not assembled, so it
    // must not take up room in the middle of a run either.
    if (segment.skip) continue;
    const open = Boolean(segment.autorun) && !segment.static;
    const carries =
      open &&
      current !== null &&
      segment.visual.topology === current.topology &&
      (segment.section ?? "") === current.section;

    if (!carries) {
      current = open
        ? {
            id: segment.slug,
            topology: segment.visual.topology,
            // The stage prints the section in a corner, so a run crossing a
            // heading cannot be one clip.
            section: segment.section ?? "",
            members: [],
            total: 0,
          }
        : null;
      if (current) runs.set(current.id, current);
    }
    if (!current) continue;

    runOf[segment.slug] = { id: current.id, offset: current.total };
    current.members.push(segment);
    current.total += secondsOf(segment) + gap;
  }

  // A run of one is an ordinary segment, with nothing to share.
  for (const [id, run] of runs)
    if (run.members.length < 2) {
      for (const member of run.members) delete runOf[member.slug];
      runs.delete(id);
    }

  return { runs, runOf };
}
