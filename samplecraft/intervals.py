"""Sets of intervals along rays: the common language of all the shapes.

A ray k is the line o_k + t d_k (d_k a unit vector, t in mm). The part of a shape it crosses is a set of disjoint
intervals [t0, t1] of t. An IntervalSet holds them for many rays at once, as three flat arrays (ray index, t0, t1),
sorted by ray then t0, disjoint and not touching within a ray. Unbounded intervals use ±inf (a half-space).

Boolean operations (union, intersection, difference) are exact: the ends of the intervals are events along each ray;
counting how many intervals of each set cover each stretch between two consecutive events tells which stretches
belong to the result (a sweep, as in the cell tracking of Monte Carlo transport codes).
"""
import numpy as np


def _sweep(sets, rule, n_rays):
    """(ray, t0, t1) of the stretches where rule(list of 'covered by set i') holds; disjoint, merged."""
    k = len(sets)
    parts = [(s.ray, s.t0, s.t1) for s in sets]
    if not sum(len(p[0]) for p in parts):
        return np.zeros(0, np.int64), np.zeros(0), np.zeros(0)
    ray = np.concatenate([np.r_[r, r] for r, _, _ in parts])
    t = np.concatenate([np.r_[a, b] for _, a, b in parts])
    which = np.concatenate([np.full(2 * len(r), i) for i, (r, _, _) in enumerate(parts)])
    delta = np.concatenate([np.r_[np.ones(len(r), np.int64), -np.ones(len(r), np.int64)] for r, _, _ in parts])
    o = np.lexsort((-delta, t, ray))                 # at equal t, starts before ends: touching intervals join
    ray, t, which, delta = ray[o], t[o], which[o], delta[o]
    inside = rule([np.cumsum(np.where(which == i, delta, 0)) > 0 for i in range(k)])
    # the stretch from event j to event j+1 of the same ray is in the result if the state after event j is
    seg = inside[:-1] & (ray[1:] == ray[:-1]) & (t[1:] > t[:-1])
    j = np.flatnonzero(seg)
    r, a, b = ray[j], t[j], t[j + 1]
    if len(r) > 1:                                   # stretches that touch (an event of another set between): merge
        cont = (r[1:] == r[:-1]) & (a[1:] == b[:-1])
        if cont.any():
            start = np.r_[True, ~cont]
            first = np.flatnonzero(start)
            last = np.r_[first[1:], len(r)] - 1
            r, a, b = r[first], a[first], b[last]
    return r, a, b


class IntervalSet:
    __slots__ = ("ray", "t0", "t1", "n_rays")

    def __init__(self, ray, t0, t1, n_rays, normalized=False):
        self.n_rays = int(n_rays)
        ray = np.asarray(ray, np.int64); t0 = np.asarray(t0, float); t1 = np.asarray(t1, float)
        if not normalized:
            keep = t1 > t0
            raw = _Raw(ray[keep], t0[keep], t1[keep])
            ray, t0, t1 = _sweep([raw], lambda c: c[0], self.n_rays)
        self.ray, self.t0, self.t1 = ray, t0, t1

    @classmethod
    def empty(cls, n_rays):
        return cls(np.zeros(0, np.int64), np.zeros(0), np.zeros(0), n_rays, normalized=True)

    @classmethod
    def full(cls, n_rays, rays=None):
        """The whole line, for every ray (or the rays given)."""
        r = np.arange(n_rays) if rays is None else np.unique(np.asarray(rays, np.int64))
        return cls(r, np.full(len(r), -np.inf), np.full(len(r), np.inf), n_rays, normalized=True)

    def __len__(self):
        return len(self.ray)

    def lengths(self):
        """Total length inside, for each ray [n_rays] (inf for an unbounded interval)."""
        return np.bincount(self.ray, weights=self.t1 - self.t0, minlength=self.n_rays)

    def take(self, rays):
        """The intervals of some rays only (rays: sorted unique indices), renumbered 0..len(rays)-1."""
        rays = np.asarray(rays, np.int64)
        if not len(rays):
            return IntervalSet.empty(0)
        pos = np.searchsorted(rays, self.ray)
        ok = (pos < len(rays)) & (rays[np.minimum(pos, len(rays) - 1)] == self.ray)
        return IntervalSet(pos[ok], self.t0[ok], self.t1[ok], len(rays), normalized=True)

    def put(self, rays, n_rays):
        """The inverse of take: intervals of rays 0..m-1 moved to the rays `rays` of a set of n_rays rays."""
        return IntervalSet(np.asarray(rays, np.int64)[self.ray], self.t0, self.t1, n_rays, normalized=True)

    def clip(self, lo, hi):
        """Intersection with [lo, hi] (scalars, or one value per ray)."""
        lo = np.broadcast_to(np.asarray(lo, float), (self.n_rays,))[self.ray]
        hi = np.broadcast_to(np.asarray(hi, float), (self.n_rays,))[self.ray]
        return IntervalSet(self.ray, np.maximum(self.t0, lo), np.minimum(self.t1, hi), self.n_rays)

    def __or__(self, other):
        return combine([self, other], lambda c: c[0] | c[1])

    def __and__(self, other):
        return combine([self, other], lambda c: c[0] & c[1])

    def __sub__(self, other):
        return combine([self, other], lambda c: c[0] & ~c[1])

    def __repr__(self):
        return f"IntervalSet({len(self)} intervals on {self.n_rays} rays)"


class _Raw:
    __slots__ = ("ray", "t0", "t1")

    def __init__(self, ray, t0, t1):
        self.ray, self.t0, self.t1 = ray, t0, t1


def combine(sets, rule):
    """Boolean combination of interval sets of the same rays: rule(list of boolean arrays 'inside set i') -> inside."""
    n = sets[0].n_rays
    return IntervalSet(*_sweep(sets, rule, n), n, normalized=True)


def union(sets):
    sets = list(sets)
    return combine(sets, lambda c: np.logical_or.reduce(c)) if sets else None


def intersection(sets):
    sets = list(sets)
    return combine(sets, lambda c: np.logical_and.reduce(c))


def from_lists(n_rays, ray, t0, t1):
    """An IntervalSet from intervals that may overlap (they are merged)."""
    return IntervalSet(ray, t0, t1, n_rays)
