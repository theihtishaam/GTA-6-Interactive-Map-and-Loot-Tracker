// The atlas frame is planar and north-up. Distances are relative to its game grid.
export function vector(a, b) {
  return [(b.x - a.x) * 13824, (a.y - b.y) * 19456];
}
export function length(a, b) {
  return Math.hypot(...vector(a, b));
}
export function angle(a, b) {
  const [east, north] = vector(a, b);
  return ((Math.atan2(east, north) * 180) / Math.PI + 360) % 360;
}
export function compass(bearing) {
  return [
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
  ][Math.round(bearing / 45) % 8];
}
export function distance(units) {
  return units >= 1000
    ? (units / 1000).toFixed(1) + " km"
    : Math.round(units) + " m";
}
export function routeDirections(legs) {
  let total = 0;
  const cues = [];
  for (const leg of legs) {
    const path = leg.points;
    if (path.length < 2) continue;
    let cumulative = [0];
    for (let i = 1; i < path.length; i++)
      cumulative.push(cumulative[i - 1] + length(path[i - 1], path[i]));
    const size = cumulative.at(-1);
    if (size < 1) continue;
    if (!leg.road) {
      cues.push({
        at: total,
        text: leg.direct
          ? "Direct bearing " +
            compass(angle(path[0], path.at(-1))) +
            " to " +
            leg.label +
            " · road unknown."
          : leg.arrival
            ? "Leave the road trace for " + leg.label + "."
            : "Join the mapped road.",
      });
      total += size;
      continue;
    }
    // Sample neighborhood headings across 64 game units to suppress pixel jitter.
    const offset = 64,
      turnGap = 100;
    let left = 0,
      right = 1,
      lastTurn = -turnGap;
    while (right < path.length - 1 && cumulative[right] < offset) right++;
    cues.push({
      at: total,
      text:
        "Follow the mapped road " + compass(angle(path[0], path[right])) + ".",
    });
    for (let i = 1; i < path.length - 1; i++) {
      while (left < i - 1 && cumulative[i] - cumulative[left + 1] >= offset)
        left++;
      while (
        right < path.length - 1 &&
        cumulative[right] - cumulative[i] < offset
      )
        right++;
      if (
        cumulative[i] - cumulative[left] < offset * 0.85 ||
        cumulative[right] - cumulative[i] < offset * 0.85
      )
        continue;
      const change =
        ((angle(path[i], path[right]) - angle(path[left], path[i]) + 540) %
          360) -
        180;
      if (Math.abs(change) >= 48 && cumulative[i] - lastTurn > turnGap) {
        lastTurn = cumulative[i];
        cues.push({
          at: total + cumulative[i],
          text:
            (Math.abs(change) > 145
              ? "Turn back"
              : change > 0
                ? "Bear right"
                : "Bear left") +
            " toward the " +
            compass(angle(path[i], path[right])) +
            ".",
        });
      }
    }
    total += size;
  }
  return { total, cues };
}
