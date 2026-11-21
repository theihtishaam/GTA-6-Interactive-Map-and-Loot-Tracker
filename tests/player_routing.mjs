// Exercise the same route solver and snap limit that players use on the map.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Roads} from '../public/routing.mjs';

function load(name) {
  return JSON.parse(readFileSync(new URL('../public/' + name, import.meta.url), 'utf8'));
}

const network = new Roads(load('roads.json'));
const venues = new Map(load('landmarks.json').map(r => [r.id, r]));
for (const [from, to] of [
  ['L1107', 'L224'],   // Game Horde → Downtown ShoreFront
  ['L325', 'L1570'],   // Rusty Anchor → Boone Speedway
  ['L590', 'L281'],    // Ambrosia Raceway → Gellhorn Raceway
  ['L1488', 'L1495'],  // Stock 305 → Paradise Garage
  ['L629', 'L1107']    // Delights → Game Horde
]) {
  const origin = venues.get('gtadb-' + from);
  const destination = venues.get('gtadb-' + to);
  const path = network.path(origin, destination);
  assert.ok(path?.length >= 2, from + ' → ' + to);
  assert.deepEqual(path[0], network.point(network.snap(origin)));
  assert.deepEqual(path.at(-1), network.point(network.snap(destination)));
}
assert.equal(network.path(venues.get('gtadb-L1107'), venues.get('gtadb-L530')), null);

const overlay = load('guide-positions.json');
const guides = new Map(load('guides.json').map(r => [r.id, {...r, ...overlay[r.id]}]));
for (const r of load('collectible-guides.json')) guides.set(r.id, r);
for (const [from, to] of [
  ['guide-job-key-lento-fleeca', 'guide-job-ambrosia-shorefront'],
  ['guide-loan-quick-buck-hamlet', 'guide-vault-downtown-lombank'],
  ['guide-job-downtown-shorefront', 'guide-job-rockridge-shorefront'],
]) {
  const a = guides.get(from), b = guides.get(to);
  assert.equal(a.precision, 'map-marker');
  assert.equal(b.precision, 'map-marker');
  assert.ok(network.path(a, b)?.length > 2, from + ' → ' + to);
}
for (const [from, to] of [
  ['guide-kingpin-watch', 'guide-duffel-bag'],
  ['guide-yasmani-tips', 'guide-kenton-dives'],
  ['guide-loan-quick-buck-hamlet', 'guide-marquise-card']
]) {
  assert.ok(network.path(guides.get(from), guides.get(to))?.length > 2, from + ' → ' + to);
}

// Open sea and interior runways must not become suggested street destinations.
for (const [x, y] of [[25, 660], [920, 1344], [415, 2140]]) {
  const p = {x: (x + 0.5) / network.width, y: (y + 0.5) / network.height};
  assert.equal(network.snap(p), -1);
}
// Count routable pairs using the same road adjacency and snap radius as path().
const groups = new Int32Array(network.nodes.length).fill(-1);
for (let seed = 0; seed < groups.length; seed++) {
  if (groups[seed] >= 0) continue;
  const visit = [seed];
  groups[seed] = seed;
  while (visit.length) {
    const current = visit.pop();
    for (const [next] of network.adj[current]) {
      if (groups[next] >= 0) continue;
      groups[next] = seed;
      visit.push(next);
    }
  }
}
const locations = new Map();
for (const r of guides.values()) {
  if (Number.isFinite(r.x) && Number.isFinite(r.y)) locations.set(r.x + ',' + r.y, r);
}
const hits = new Map();
for (const r of locations.values()) {
  const i = network.snap(r);
  if (i >= 0) hits.set(groups[i], (hits.get(groups[i]) || 0) + 1);
}
const pairs = n => n * (n - 1) / 2;
const connected = [...hits.values()].reduce((sum, n) => sum + pairs(n), 0);
console.log('Eleven route pairs and four unsupported destinations passed.');
console.log(connected + ' of ' + pairs(locations.size) + ' distinct mapped-guide pairs are connected.');
