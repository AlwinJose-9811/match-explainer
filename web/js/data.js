// Loads the processed JSON bundle over same-origin fetch and caches it in memory.
export class DataError extends Error {
  constructor(file, cause) { super(`Could not load ${file}`); this.file = file; this.cause = cause; }
}

const cache = new Map();

export function load(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(`data/${path}`).then(r => {
      if (!r.ok) throw new DataError(path, `HTTP ${r.status}`);
      return r.json();
    }).catch(e => { cache.delete(path); throw e instanceof DataError ? e : new DataError(path, e); }));
  }
  return cache.get(path);
}

export const matchFile = (id, name) => load(`${id}/${name}.json`);
