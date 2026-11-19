"""ITU-R BS.1770-4 loudness (integrated LUFS, gated) and true peak (4x oversampled dBTP) for 48 kHz float audio."""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter, resample_poly

SR = 48000
# K-weighting at 48 kHz (BS.1770-4 table 1 and 2)
_B1, _A1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
_B2, _A2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]


def _kw(x: np.ndarray) -> np.ndarray:
    return lfilter(_B2, _A2, lfilter(_B1, _A1, x, axis=-1), axis=-1)


def _blocks(x: np.ndarray, block=0.4, step=0.1) -> np.ndarray:
    """Mean square of K-weighted audio per 400 ms block (75 % overlap), summed over channels."""
    x = np.atleast_2d(x)
    z = _kw(x) ** 2
    n, b, s = z.shape[1], int(block * SR), int(step * SR)
    if n < b:
        return np.array([z.sum(0).mean()]) if n else np.array([])
    c = np.cumsum(np.concatenate([np.zeros((z.shape[0], 1)), z], axis=1), axis=1)
    starts = np.arange(0, n - b + 1, s)
    return ((c[:, starts + b] - c[:, starts]) / b).sum(0)


def lufs(x: np.ndarray, mask: np.ndarray | None = None) -> float:
    """Integrated loudness. `mask` (bool per 100 ms block start) restricts the measurement to chosen blocks."""
    ms = _blocks(x)
    if mask is not None:
        k = min(len(ms), len(mask))
        ms = ms[:k][mask[:k]]
    ms = ms[ms > 0]
    if not len(ms):
        return -np.inf
    l = -0.691 + 10 * np.log10(ms)
    g = ms[l > -70]
    if not len(g):
        return -np.inf
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g = ms[(l > -70) & (l > rel)]
    return float(-0.691 + 10 * np.log10(g.mean()))


def true_peak_db(x: np.ndarray) -> float:
    x = np.atleast_2d(x)
    return float(20 * np.log10(max(np.abs(resample_poly(ch, 4, 1)).max() for ch in x) + 1e-12))


def limit(x: np.ndarray, ceiling_db=-1.5, lookahead=0.005, release=0.08) -> np.ndarray:
    """Look-ahead peak limiter on the 4x oversampled peak envelope (linked across channels)."""
    x = np.atleast_2d(x)
    over = np.max([np.abs(resample_poly(ch, 4, 1)) for ch in x], axis=0)
    peak = over.reshape(-1, 4).max(1)[: x.shape[1]] if len(over) >= 4 * x.shape[1] else np.abs(x).max(0)
    peak = np.pad(peak, (0, x.shape[1] - len(peak)))
    c = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, c / np.maximum(peak, 1e-9))
    la = int(lookahead * SR)
    # min over the look-ahead window so the gain is down before the peak arrives
    from scipy.ndimage import minimum_filter1d
    need = minimum_filter1d(need, size=2 * la + 1, origin=0)
    # smooth: instant attack (already looked ahead), exponential release
    a = np.exp(-1.0 / (release * SR))
    g = lfilter([1 - a], [1, -a], need)  # rises back slowly
    g = np.minimum(g, need)
    return (x * g).astype(np.float32)


if __name__ == "__main__":  # self-check: a 1 kHz sine at -20 dBFS peak reads about -23 LUFS (stereo: +3)
    t = np.arange(SR * 5) / SR
    s = 0.1 * np.sin(2 * np.pi * 997 * t)
    print("mono 997 Hz, -20 dBFS:", round(lufs(s), 2), "LUFS (expect -23.0)")
    print("true peak:", round(true_peak_db(s), 2), "dBTP (expect -20.0)")
    y = limit(np.vstack([s * 20, s * 20]), -1.0)
    print("limited true peak:", round(true_peak_db(y), 2), "dBTP (expect <= -1.0)")
