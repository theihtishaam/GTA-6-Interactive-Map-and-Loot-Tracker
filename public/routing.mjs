import { json } from "./ui.mjs";
let pending;
export function roadNetwork() {
  return (pending ??= json("/roads.json")
    .then((data) => new Roads(data))
    .catch((e) => {
      pending = null;
      throw e;
    }));
}
export class Roads {
  constructor({ nodes, edges, width, height }) {
    Object.assign(this, { nodes, width, height });
    this.adj = nodes.map(() => []);
    for (const [a, b] of edges) {
      const [x, y] = nodes[a],
        [u, v] = nodes[b];
      const dist = Math.hypot(x - u, y - v);
      this.adj[a].push([b, dist]);
      this.adj[b].push([a, dist]);
    }
  }
  snap(p) {
    let best = -1,
      min = 16;
    const x = p.x * this.width - 0.5,
      y = p.y * this.height - 0.5;
    this.nodes.forEach(([u, v], i) => {
      const d = Math.hypot(x - u, y - v);
      if (d < min) {
        best = i;
        min = d;
      }
    });
    return best;
  }
  point(i) {
    const [x, y] = this.nodes[i];
    return { x: (x + 0.5) / this.width, y: (y + 0.5) / this.height };
  }
  path(a, b) {
    const start = this.snap(a),
      end = this.snap(b);
    if (start < 0 || end < 0) return null;
    const scores = new Float64Array(this.nodes.length).fill(Infinity),
      prev = new Int32Array(this.nodes.length).fill(-1);
    const heap = [];
    const push = (id, cost) => {
      let i = heap.length;
      heap.push([id, cost]);
      while (i) {
        const j = (i - 1) >> 1;
        if (heap[j][1] <= cost) break;
        heap[i] = heap[j];
        i = j;
      }
      heap[i] = [id, cost];
    };
    const pop = () => {
      const root = heap[0],
        last = heap.pop();
      if (heap.length) {
        let i = 0;
        while (i * 2 + 1 < heap.length) {
          let j = i * 2 + 1;
          if (j + 1 < heap.length && heap[j + 1][1] < heap[j][1]) j++;
          if (heap[j][1] >= last[1]) break;
          heap[i] = heap[j];
          i = j;
        }
        heap[i] = last;
      }
      return root;
    };
    scores[start] = 0;
    push(start, 0);
    while (heap.length) {
      const [id, cost] = pop();
      if (cost > scores[id]) continue;
      if (id === end) {
        const points = [];
        for (let cur = end; cur !== -1; cur = prev[cur])
          points.push(this.point(cur));
        return points.reverse();
      }
      for (const [next, d] of this.adj[id]) {
        const sum = cost + d;
        if (sum < scores[next]) {
          scores[next] = sum;
          prev[next] = id;
          push(next, sum);
        }
      }
    }
    return null;
  }
}
