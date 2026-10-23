"""
Speech detection: is someone actually TALKING right now?

Uses Silero VAD, a tiny neural network that ships with faster-whisper (no
extra download). Unlike a volume threshold it ignores fans, keyboards, music,
game audio and door slams, and it still hears you when you speak quietly.
Falls back to the old loudness check if the model can't load.
"""
import os

import numpy as np

FRAME = 512            # 32 ms at 16 kHz, what the model expects
CONTEXT = 64


def _model_path():
    try:
        import faster_whisper
        p = os.path.join(os.path.dirname(faster_whisper.__file__), "assets", "silero_vad_v6.onnx")
        if os.path.exists(p):
            return p
        for name in ("silero_vad.onnx", "silero_vad_v5.onnx"):
            q = os.path.join(os.path.dirname(faster_whisper.__file__), "assets", name)
            if os.path.exists(q):
                return q
    except Exception:
        pass
    return None


class SileroVAD:
    """Streaming: feed 16 kHz float32 audio in any chunk size, get one speech
    probability (0..1) per 32 ms frame."""

    def __init__(self):
        import onnxruntime as ort
        path = _model_path()
        if not path:
            raise FileNotFoundError("Silero VAD model not found in faster-whisper")
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 4
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"], sess_options=opts)
        self.inputs = {i.name for i in self.sess.get_inputs()}
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.ctx = np.zeros(CONTEXT, dtype=np.float32)
        self.buf = np.zeros(0, dtype=np.float32)

    def __call__(self, audio):
        """Returns a list of probabilities, one per complete 32 ms frame in (buffered + new) audio."""
        self.buf = np.concatenate([self.buf, np.asarray(audio, dtype=np.float32)])
        out = []
        while len(self.buf) >= FRAME:
            frame, self.buf = self.buf[:FRAME], self.buf[FRAME:]
            x = np.concatenate([self.ctx, frame])[None, :]
            prob, self.h, self.c = self.sess.run(None, {"input": x, "h": self.h, "c": self.c})
            self.ctx = frame[-CONTEXT:]
            out.append(float(np.asarray(prob).reshape(-1)[0]))
        return out


def load(log=print):
    try:
        v = SileroVAD()
        v(np.zeros(FRAME * 2, dtype=np.float32))      # warm up
        v.reset()
        return v
    except Exception as e:
        log(f"NEURAL SPEECH DETECTION UNAVAILABLE ({type(e).__name__}); USING LOUDNESS")
        return None
