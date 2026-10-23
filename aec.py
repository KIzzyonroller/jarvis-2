"""
Echo cancellation: take his own voice back out of the microphone.

With speakers (no headphones) the mic hears him talk, which makes interrupting
him unreliable. Because we know EXACTLY what audio we sent to the speakers,
an adaptive filter can learn how that audio comes back into the mic (delay,
room echo, speaker colouring) and subtract it, leaving mostly your voice.

  * RefRing: every block the speaker plays is stored with the time it reaches
    the speaker (PortAudio's DAC timestamp).
  * EchoCanceller: a partitioned-block frequency-domain adaptive filter
    (the same family of algorithm Speex and WebRTC use), with a "two-path"
    setup: a background filter keeps learning, and only replaces the one in
    use when it's actually doing better. That way you talking over him
    (double-talk) can't wreck it.

Costs a few percent of one CPU core while he's talking, close to nothing otherwise.
"""
import threading

import numpy as np

SR = 16000


class RefRing:
    """What the speakers played, on a timeline, resampled to 16 kHz for the canceller."""

    def __init__(self, seconds=6):
        self.n = SR * seconds
        self.buf = np.zeros(self.n, dtype=np.float32)
        self.t0 = None              # stream time of buf sample index 0 (absolute index space)
        self.head = 0               # absolute 16 kHz index one past the newest sample written
        self.last_loud = -1e9       # stream time of the last non-silent output
        self.lock = threading.Lock()

    def write(self, dac_time, block, sr):
        """Called from the output stream callback with the block about to be played."""
        block = np.asarray(block, dtype=np.float32).reshape(-1)
        if sr != SR:
            m = int(round(len(block) * SR / sr))
            if m <= 0:
                return
            block = np.interp(np.arange(m) * (sr / SR), np.arange(len(block)), block).astype(np.float32)
        with self.lock:
            if self.t0 is None:
                self.t0 = dac_time
                self.head = 0
            start = int(round((dac_time - self.t0) * SR))
            # small clock jitter: trust continuity, re-anchor only if way off
            if abs(start - self.head) > SR // 10:
                self.head = start
            idx = (np.arange(self.head, self.head + len(block)) % self.n)
            self.buf[idx] = block
            self.head += len(block)
            if np.max(np.abs(block)) > 1e-3:
                self.last_loud = dac_time + len(block) / SR

    def read(self, t, count):
        """count samples starting at stream time t (zeros where nothing was played)."""
        with self.lock:
            if self.t0 is None:
                return np.zeros(count, dtype=np.float32)
            start = int(round((t - self.t0) * SR))
            out = np.zeros(count, dtype=np.float32)
            lo, hi = max(start, self.head - self.n + 1), min(start + count, self.head)
            if hi > lo:
                out[lo - start:hi - start] = self.buf[np.arange(lo, hi) % self.n]
            return out

    def covered_until(self):
        """Stream time up to which we know what the speaker plays."""
        with self.lock:
            return None if self.t0 is None else self.t0 + self.head / SR

    def active(self, t, within=0.6):
        return t - self.last_loud < within


class EchoCanceller:
    """Partitioned-block frequency-domain adaptive filter, two-path."""

    def __init__(self, block=256, tail_ms=400, mu=0.7):
        self.B = block
        self.P = int(np.ceil(tail_ms * SR / 1000 / block))
        self.mu = mu
        F = block + 1
        self.Wb = np.zeros((self.P, F), dtype=np.complex64)    # background (always learning)
        self.Wf = np.zeros((self.P, F), dtype=np.complex64)    # foreground (what we subtract)
        self.X = np.zeros((self.P, F), dtype=np.complex64)     # spectra of recent reference blocks
        self.prev_ref = np.zeros(block, dtype=np.float32)
        self.pw = np.full(F, 1e-4, dtype=np.float32)          # per-bin reference power
        self.eb_s = self.ef_s = self.d_s = 1e-6                # smoothed energies
        self.erle = 0.0

    def reset(self):
        self.__init__(self.B, self.P * self.B * 1000 // SR, self.mu)

    def _block(self, d, x):
        B = self.B
        X0 = np.fft.rfft(np.concatenate([self.prev_ref, x])).astype(np.complex64)
        self.prev_ref = x
        self.X = np.roll(self.X, 1, axis=0)
        self.X[0] = X0
        far = float(np.dot(x, x)) / B
        if far < 1e-8:                                       # he's silent: nothing to cancel
            return d
        yb = np.fft.irfft((self.Wb * self.X).sum(axis=0))[B:]
        yf = np.fft.irfft((self.Wf * self.X).sum(axis=0))[B:]
        eb, ef = d - yb, d - yf
        Eb, Ef, D = float(np.dot(eb, eb)), float(np.dot(ef, ef)), float(np.dot(d, d))
        a = 0.85
        self.eb_s = a * self.eb_s + (1 - a) * Eb
        self.ef_s = a * self.ef_s + (1 - a) * Ef
        self.d_s = a * self.d_s + (1 - a) * D
        # learn (background only), normalised per frequency bin
        self.pw = 0.9 * self.pw + 0.1 * (np.abs(X0) ** 2)
        E = np.fft.rfft(np.concatenate([np.zeros(B, np.float32), eb])).astype(np.complex64)
        G = self.mu * np.conj(self.X) * E / (self.P * self.pw + 1e-3 * B)
        g = np.fft.irfft(G, axis=1)
        g[:, B:] = 0                                         # keep it a proper linear (not circular) filter
        self.Wb += np.fft.rfft(g, axis=1).astype(np.complex64)
        # two-path bookkeeping
        if self.eb_s < 0.7 * self.ef_s and self.eb_s < self.d_s:
            self.Wf[:] = self.Wb                             # background is clearly better: promote it
        elif self.eb_s > 4 * self.d_s:
            self.Wb[:] = self.Wf                             # background diverged (you were talking): roll back
            self.eb_s = self.ef_s
        self.erle = 10 * np.log10(max(self.d_s, 1e-9) / max(self.ef_s, 1e-9))
        return ef if self.ef_s <= self.d_s * 1.05 else d     # never make it worse than no cancelling

    def process(self, mic, ref):
        """mic, ref: float32 arrays of equal length (a multiple of the block size works best)."""
        mic = np.asarray(mic, dtype=np.float32)
        ref = np.asarray(ref, dtype=np.float32)
        out = np.empty_like(mic)
        B = self.B
        n = len(mic) - len(mic) % B
        for i in range(0, n, B):
            out[i:i + B] = self._block(mic[i:i + B], ref[i:i + B])
        if n < len(mic):
            out[n:] = mic[n:]
        return out


REF = RefRing()          # shared: the speaker writes into it, the microphone reads from it
