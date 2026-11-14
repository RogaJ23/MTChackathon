"""Empirical 90% intervals with equal total calibration weight per validation domain.

Domains differ in density and residual bias. Image-weighted tails let large domains
hide small ones. A symmetric radius also avoids transferring one domain's signed bias.
Validation reuse and unseen domains preclude a distribution-free coverage guarantee.
"""
import collections,math


def weighted_quantile(values, weights, probability):
    if not values or len(values)!=len(weights) or not 0<probability<1:
        raise ValueError('Invalid calibration observations or probability')
    if not all(math.isfinite(v) for v in values) or not all(math.isfinite(w) and w>0 for w in weights):
        raise ValueError('Calibration requires finite scores and positive weights')
    ordered=sorted(zip(values,weights));threshold=probability*math.fsum(weights);total=0
    for value,weight in ordered:
        total+=weight
        if total>=threshold:return float(value)
    return float(ordered[-1][0])


def calibrate(observed,predicted,domains):
    if not observed or len(observed)!=len(predicted) or len(observed)!=len(domains):
        raise ValueError('Calibration row mismatch')
    counts=collections.Counter(domains)
    radius=weighted_quantile([abs(y-max(0,p)) for y,p in zip(observed,predicted)],
                             [1/counts[g] for g in domains],.9)
    return radius,{'method':'equal-domain weighted 90th percentile absolute residual',
                   'radius':radius,'domains':len(counts),'rows':len(observed),
                   'selection':'Minimum leave-one-validation-domain-out macro IS90 among six fixed candidates with macro coverage >= .90; no test labels',
                   'limitations':'Empirical validation calibration; reused validation and domain shift prevent a distribution-free guarantee.'}
