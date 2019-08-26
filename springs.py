import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import intersect_point_tri
from .utils import DummyObj, n_ring
from mathutils import Vector
from random import random


class SpringEngine:
    def __init__(self, source_bm, target_bm=None, max_springs=300, x_mirror=False, immediate_edges_max=6):
        self.max_springs = max_springs
        self.immediate_edges_max = immediate_edges_max
        self.bm = source_bm
        self.target_bm = target_bm
        self.n = len(source_bm.verts)
        self.co = np.array(list(tuple(v.co) for v in source_bm.verts), dtype=np.float64)
        self.last_co = self.co.copy()
        self.springs = np.zeros((self.n, max_springs), dtype=np.int64)
        self.immediate_edges = np.full((self.n, immediate_edges_max), -1, dtype=np.int64)
        self.lengths = np.zeros((self.n, max_springs), dtype=np.float64)
        self.sizing = 1

        self.pins = []
        self.out_cache = DummyObj()

        if target_bm:
            target_bm.faces.ensure_lookup_table()
            self.bvh = BVHTree.FromBMesh(target_bm)
        else:
            self.bvh = None

        source_bm.verts.ensure_lookup_table()
        source_bm.faces.ensure_lookup_table()

        if x_mirror:
            self.mirror_table = np.full((self.n,), -1, dtype=np.int64)
            self.x_mirr = True
            kd = KDTree(self.n)
            for vert in source_bm.verts:
                kd.insert(vert.co, vert.index)
            kd.balance()
        else:
            self.x_mirr = False
            self._mirror_table = None

        for vert in source_bm.verts:
            for j, edge in enumerate(vert.link_edges):
                if not j < immediate_edges_max:
                    break
                other = edge.other_vert(vert)
                if not vert.is_boundary or other.is_boundary == vert.is_boundary:
                    self.immediate_edges[vert.index, j] = other.index

            for j, other in enumerate(n_ring(vert, self.max_springs)):
                self.springs[vert.index, j] = other.index
                self.lengths[vert.index, j] = (other.co - vert.co).length

            if self.x_mirr:
                co = vert.co.copy()
                co.x *= -1
                mirrco, mirri, dist = kd.find(co)
                self.mirror_table[vert.index] = mirri

        self.immediate_edges_invalid_places = self.immediate_edges == -1
        self.immediate_edges_number = (immediate_edges_max - self.immediate_edges_invalid_places.sum(axis=1))

    def _stiffness_springs_clamp(self, stiffness, springs):
        stiffness = min(stiffness, self.max_springs)
        springs = min(stiffness, springs)
        return stiffness, springs

    def _springs_sample_cached(self, stiffness=100, springs=30):
        if self.out_cache.springs_ids:
            data = self.out_cache.springs_ids
            if data.stiffness == stiffness and data.springs == springs:
                return data.ids, data.lengths

        stiffness, springs = self._stiffness_springs_clamp(stiffness, springs)

        idx = np.arange(springs * self.n) // springs
        idx.shape = self.n, springs
        rnd = np.random.sample(self.n * stiffness)
        rnd.shape = self.n, stiffness
        idy = np.argsort(rnd, axis=1)[:, :springs]
        if not springs == stiffness:
            idy[:, :4] = range(4)

        data = DummyObj(stiffness=stiffness, springs=springs, ids=self.springs[idx, idy],
                        lengths=self.lengths[idx, idy])
        self.out_cache.springs_ids = data
        return data.ids, data.lengths

    def smooth(self, factor=0.5):
        while factor > 0:
            immediate_co = self.co[self.immediate_edges]
            immediate_co[self.immediate_edges_invalid_places] = 0
            new_co = immediate_co.sum(axis=1)
            new_co /= self.immediate_edges_number[:, np.newaxis]
            self.co = new_co * min(factor, 0.5) + self.co * (1 - min(factor, 0.5))
            factor = factor - 0.5

    def random_co(self, factor=0.5):
        rnd = np.random.sample(self.n * 3)
        rnd -= 0.5
        rnd *= 2 * factor
        rnd.shape = self.n, 3
        self.co += rnd

    def springs_force_apply(self, factor=0.99, stiffness=300, springs=30):
        stiffness, springs = self._stiffness_springs_clamp(stiffness, springs)
        ids, lengths = self._springs_sample_cached(stiffness, springs)
        co = self.co
        sco = self.co[ids]
        co.shape = self.n, 1, 3
        d = co - sco
        dle = (d * d).sum(axis=2)
        rescale = (((lengths * self.sizing) ** 2) / dle)
        d *= rescale[:, :, np.newaxis]
        nan = np.isnan(d)
        d[nan] = 0
        new_co = (d + sco).sum(axis=1) / springs
        co.shape = self.n, 3
        self.co = new_co * factor + co * (1 - factor)

    def target_attract(self, factor=0.9):
        for i in range(self.n):
            v = self.bm.verts[i]
            co0 = Vector(self.co[i])
            co1, normal, index, dist = self.bvh.find_nearest(co0)
            d = co0 - co1
            if v.normal.dot(normal) < 0 and d.dot(normal) < 0:
                d *= -1
            self.co[i] -= d * factor * (v.normal.dot(normal) ** 2)

    def movement_step(self, drag=1.0):
        d = self.co - self.last_co
        self.last_co = self.co
        self.co = self.co + d * drag

    def x_mirror_apply(self):
        if self.x_mirr:
            mirrco = self.co[self.mirror_table]
            mirrco[:, 0] *= -1
            self.co += mirrco
            self.co *= 0.5

    def pins_apply(self):
        for pin in self.pins:
            idx = pin.vert_index
            stiffness = max(min(pin.stiffness, self.max_springs), 0)
            fallof = (1 - (np.arange(stiffness) / stiffness)) * pin.factor
            fallof.shape = stiffness, 1
            ids = self.springs[idx, :stiffness]
            if pin.twisty:
                self.co[idx] = pin.co
                lengths = self.lengths[idx, :stiffness]
                sco = self.co[ids]
                co = self.co[idx]
                d = sco - co
                dle = (d * d).sum(axis=1)
                newd = d * (((lengths * self.sizing) ** 2) / dle)[:, np.newaxis]
                self.co[ids] = newd * fallof + d * (1 - fallof) + co
            else:
                d = np.array(np.array(pin.co) - self.co[idx])
                self.co[idx] += d * pin.factor
                self.co[ids] += d[np.newaxis, :] * fallof

    def add_pin(self, co, vert_index, stiffness=50, factor=0.99, twisty=False, x_mirr=False):
        stiffness = max(0, min(stiffness, self.max_springs))
        factor = max(0, min(factor, 1))
        self.pins.append(DummyObj(co=co, vert_index=vert_index, stiffness=stiffness,
                                  factor=factor, twisty=twisty))
        if x_mirr and self.x_mirr:
            co = co.copy()
            co[0] *= -1
            vert_index = self.mirror_table[vert_index]
            self.pins.append(DummyObj(co=co, vert_index=vert_index, stiffness=stiffness,
                                      factor=factor, twisty=twisty))

    def clear_pins(self):
        self.pins.clear()

    def back_to_bm(self):
        for vert in self.bm.verts:
            vert.co = self.co[vert.index]
        self.bm.normal_update()
