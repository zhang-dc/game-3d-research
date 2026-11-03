"""Seeded geometry variation with explicit shared boundaries and fixed anchors.

This module is independent of bpy; callers may use numpy arrays from Blender
meshes or GLB POSITION buffers. Units are the caller's units (here metres).
No materials, indices, UVs, stage tags, object transforms or hinges are edited.

Design sources: Blender Random Value (stable ID+seed), Realize Instances
(separate per-element geometry). Boundary partitioning/constraint projection
is our implementation, not a claim to reproduce Townscaper's algorithm.
https://docs.blender.org/manual/en/5.4/modeling/geometry_nodes/utilities/random_value.html
https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/instances/realize_instances.html
"""
from dataclasses import dataclass
import hashlib
import numpy as np

def generator(seed,key):
    digest=hashlib.sha256(f'{seed}:{key}'.encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8],'little'))

def standardized(n,seed,key,limit=2.2):
    """Zero mean, unit population SD, bounded deterministic sample."""
    a=generator(seed,key).normal(size=n);a=np.clip(a,-limit,limit);a-=a.mean()
    return a/max(a.std(),1e-12)

def partition(lo,hi,n,cv,seed,key,min_fraction=.30):
    """Positive random widths exactly filling a fixed span; no independent jitter.
    CV is exact unless min_fraction clips the requested distribution (reported
    by callers from the returned widths). Shared edges cannot overlap.
    """
    w=np.maximum(min_fraction,1+cv*standardized(n,seed,key));w*=((hi-lo)/w.sum())
    return np.r_[lo,lo+np.cumsum(w)]

def map_partition(values,old,new):
    return np.interp(values,old,new)

def smoothstep(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def fixed_box_weight(points,lo,hi,margin=.08):
    """Zero at/near protected AABB faces. This is not a collision test."""
    d=np.minimum(points-np.asarray(lo),np.asarray(hi)-points)
    return smoothstep(np.min(d,axis=1)/margin)

def beam_warp(vertices,axis,cv,seed,key,lean_sd_deg=0.0,bow_fraction=.02,anchor_fraction=.18):
    """Vary cross section / centreline, with both end attachment zones fixed.
    Large side contacts require extra caller-provided masks; use validate_group.
    """
    v=np.asarray(vertices,float);lo=v.min(0);hi=v.max(0);c=(lo+hi)/2;L=hi[axis]-lo[axis]
    t=(v[:,axis]-lo[axis])/max(L,1e-9);w=smoothstep(t/anchor_fraction)*smoothstep((1-t)/anchor_fraction)
    r=generator(seed,key);scale=1+cv*np.clip(r.normal(),-2,2)
    transverse=[i for i in range(3) if i!=axis];out=v.copy()
    lean=np.tan(np.radians(r.normal(0,lean_sd_deg)))
    for k in transverse:
        out[:,k]+=w*((v[:,k]-c[k])*(scale-1)+lean*L*(t-.5)+r.uniform(-1,1)*bow_fraction*(hi[k]-lo[k])*np.sin(np.pi*t))
    return out

@dataclass
class GroupContract:
    bounds_min: object
    bounds_max: object
    tolerance: float=.00001
    anchors: object=None
    anchor_tolerance: float=.000001

def validate_group(before,after,contract,connectivity=None,collision=None,coverage=None):
    """Fail closed on supplied structural checks, never certify absent checks.
    Caller callbacks return a bool plus evidence and should use actual geometry.
    """
    before=np.asarray(before);after=np.asarray(after)
    report={'finite':bool(np.isfinite(after).all()),'bounds':bool(np.all(after>=np.asarray(contract.bounds_min)-contract.tolerance) and np.all(after<=np.asarray(contract.bounds_max)+contract.tolerance))}
    if contract.anchors is not None:
        mask=np.asarray(contract.anchors,bool);report['anchors']=bool(np.max(np.abs(before[mask]-after[mask]),initial=0)<=contract.anchor_tolerance)
    for name,fn in [('connectivity',connectivity),('collision',collision),('coverage',coverage)]:report[name]=fn(after) if fn else None
    report['certified']=all(report.get(k) is True for k in ['finite','bounds','anchors','connectivity','collision','coverage'])
    return report
