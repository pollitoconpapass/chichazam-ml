_HEAD = ["HeadYaw", "HeadPitch"]
_L_ARM = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw"]
_R_ARM = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]
_LEGS = ["LHipPitch", "LKneePitch", "LAnklePitch",
         "RHipPitch", "RKneePitch", "RAnklePitch",
         "LHipRoll", "LAnkleRoll", "RHipRoll", "RAnkleRoll"]
_ALL = _HEAD + _L_ARM + _R_ARM + _LEGS

# Poses del brazo izquierdo: (ShoulderPitch, ShoulderRoll, ElbowYaw, ElbowRoll, WristYaw)
# El derecho se obtiene por espejo.
_POSES = {
    "down":    (1.55, 0.15, -1.2, -0.5, 0.0),
    "chest":   (1.00, 0.25, -1.4, -1.3, 0.0),
    "chest_b": (0.90, 0.40, -1.4, -0.9, 0.0),
    "front":   (0.40, 0.20, -0.5, -0.4, 0.0),
    "side":    (1.10, 1.10, -1.2, -0.3, 0.0),
    "up":      (-0.90, 0.35, -1.2, -0.6, 0.0),
    "high":    (-1.50, 0.40, -0.8, -0.5, 0.0),
    "back":    (1.90, 0.20, -1.2, -0.4, 0.0),
    "fist_up": (-0.80, 0.20, -1.2, -1.3, 0.0),
    "strum_a": (0.50, 0.30, 1.0, -0.5, 0.0),
    "strum_b": (0.50, 0.30, 1.0, -1.3, 0.0),
    "hip":     (1.40, 0.45, -1.8, -1.5, 0.0),
    "hanky_a": (0.00, 0.50, -1.3, -0.9, -1.0),
    "hanky_b": (0.00, 0.50, -1.3, -0.9, 1.0),
}

# Limites para no perder estabilidad: (rebote, balanceo) en rad
_MAX_SAFE = (0.12, 0.04)
_MAX_FULL = (0.20, 0.08)


def _mirror(p):
    return (p[0], -p[1], -p[2], -p[3], -p[4])


def _S(la, ra=None, head=(0.0, 0.0), b=0.0, s=0.0, beats=1.0):
    """Paso: poses de brazos (ra se espeja), cabeza (yaw, pitch),
    b=rebote de rodillas, s=balanceo lateral, beats=duracion en tiempos."""
    return dict(la=la, ra=ra, head=head, b=b, s=s, beats=beats)


def _run(motion, choreo, bpm, reps, safe):
    limits = {}
    for n in _ALL:
        lim = motion.getLimits(n)[0]
        limits[n] = (lim[0], lim[1])
    base = dict(zip(_LEGS, motion.getAngles(_LEGS, True)))
    max_b, max_s = _MAX_SAFE if safe else _MAX_FULL

    def clamp(n, v):
        return max(limits[n][0], min(limits[n][1], v))

    for _ in range(reps):
        for st in choreo:
            la = _POSES[st["la"]] if isinstance(st["la"], str) else st["la"]
            ra = st["ra"] if st["ra"] is not None else st["la"]
            ra = _mirror(_POSES[ra] if isinstance(ra, str) else ra)
            b = max(-max_b, min(max_b, st["b"]))
            s = max(-max_s, min(max_s, st["s"]))

            t = {}
            t.update(zip(_HEAD, st["head"]))
            t.update(zip(_L_ARM, la))
            t.update(zip(_R_ARM, ra))
            for side in ("L", "R"):
                t[side + "HipPitch"] = base[side + "HipPitch"] - b
                t[side + "KneePitch"] = base[side + "KneePitch"] + 2.0 * b
                t[side + "AnklePitch"] = base[side + "AnklePitch"] - b
                # balanceo lateral con pie plano
                t[side + "HipRoll"] = base[side + "HipRoll"] + s
                t[side + "AnkleRoll"] = base[side + "AnkleRoll"] - s

            dur = st["beats"] * 60.0 / bpm
            angles = [[clamp(n, t[n])] for n in _ALL]
            times = [[dur] for _ in _ALL]
            motion.angleInterpolation(_ALL, angles, times, True)


# === GENEROS ===
def baile_rock(motion, bpm=120, reps=4, safe=True):
    choreo = [
        _S("fist_up", "down", head=(0.0, 0.25), b=0.12),
        _S("down", "fist_up", head=(0.0, -0.10), b=0.02),
        _S("fist_up", "down", head=(0.0, 0.25), b=0.12),
        _S("down", "fist_up", head=(0.0, -0.10), b=0.02),
        _S("front", "strum_a", head=(0.3, 0.15), b=0.10, beats=0.5),
        _S("front", "strum_b", head=(0.3, 0.15), b=0.04, beats=0.5),
        _S("front", "strum_a", head=(0.3, 0.15), b=0.10, beats=0.5),
        _S("front", "strum_b", head=(0.3, 0.15), b=0.04, beats=0.5),
        _S("high", "high", head=(0.0, -0.30), b=0.05, beats=2.0),
    ]
    motion.setAngles(["LHand", "RHand"], [0.1, 0.1], 0.4)
    try:
        _run(motion, choreo, bpm, reps, safe)
    finally:
        motion.setAngles(["LHand", "RHand"], [0.6, 0.6], 0.4)


def baile_chicha(motion, bpm=105, reps=4, safe=True):
    choreo = [
        _S("side", "chest", head=(0.35, 0.05), b=0.08, s=0.04),
        _S("chest", "side", head=(-0.35, 0.05), b=0.08, s=-0.04),
        _S("side", "chest", head=(0.35, 0.05), b=0.08, s=0.04),
        _S("chest", "side", head=(-0.35, 0.05), b=0.08, s=-0.04),
        _S("front", "up", head=(0.2, -0.1), b=0.06, s=0.03),
        _S("up", "front", head=(-0.2, -0.1), b=0.06, s=-0.03),
        _S("front", "up", head=(0.2, -0.1), b=0.06, s=0.03),
        _S("up", "front", head=(-0.2, -0.1), b=0.06, s=-0.03),
    ]
    _run(motion, choreo, bpm, reps, safe)


def baile_criolla(motion, bpm=96, reps=4, safe=True):
    choreo = [
        _S("hanky_a", "hip", head=(0.30, 0.05), b=0.06, s=0.02),
        _S("hanky_b", "hip", head=(0.30, 0.00), b=0.02, s=0.02),
        _S("hanky_a", "hip", head=(0.30, 0.05), b=0.02, s=0.02),
        _S("hip", "hanky_a", head=(-0.30, 0.05), b=0.06, s=-0.02),
        _S("hip", "hanky_b", head=(-0.30, 0.00), b=0.02, s=-0.02),
        _S("hip", "hanky_a", head=(-0.30, 0.05), b=0.02, s=-0.02),
    ]
    _run(motion, choreo, bpm, reps, safe)


def baile_huayno(motion, bpm=120, reps=4, safe=True):
    choreo = []
    for _ in range(2):
        choreo += [_S("chest", "chest_b", head=(0.15, 0.05), b=0.12, beats=0.5),
                   _S("chest_b", "chest", head=(-0.15, 0.05), b=0.02, beats=0.5)] * 2
    choreo += [
        _S("up", "down", head=(0.2, -0.1), b=0.10, s=0.04),
        _S("down", "up", head=(-0.2, -0.1), b=0.10, s=-0.04),
        _S("up", "down", head=(0.2, -0.1), b=0.10, s=0.04),
        _S("down", "up", head=(-0.2, -0.1), b=0.10, s=-0.04),
    ]
    _run(motion, choreo, bpm, reps, safe)


def baile_cumbia_amazonica(motion, bpm=118, reps=4, safe=True):
    choreo = [
        _S("front", "back", head=(0.25, 0.0), b=0.10, s=0.06, beats=0.5),
        _S("back", "front", head=(-0.25, 0.0), b=0.04, s=-0.06, beats=0.5),
        _S("front", "back", head=(0.25, 0.0), b=0.10, s=0.06, beats=0.5),
        _S("back", "front", head=(-0.25, 0.0), b=0.04, s=-0.06, beats=0.5),
        _S("up", "side", head=(0.3, -0.1), b=0.08, s=0.05, beats=0.5),
        _S("side", "up", head=(-0.3, -0.1), b=0.08, s=-0.05, beats=0.5),
        _S("up", "side", head=(0.3, -0.1), b=0.08, s=0.05, beats=0.5),
        _S("side", "up", head=(-0.3, -0.1), b=0.08, s=-0.05, beats=0.5),
        _S("high", "high", head=(0.0, -0.25), b=0.06, beats=2.0),
    ]
    _run(motion, choreo, bpm, reps, safe)


# Acceso por nombre de genero (util si tu clasificador devuelve un string)
DANCES = {
    "rock": baile_rock,
    "chicha": baile_chicha,
    "criolla": baile_criolla,
    "huayno": baile_huayno,
    "cumbia_amazonica": baile_cumbia_amazonica,
}


def bailar(motion, genero, **kwargs):
    DANCES[genero.lower().replace(" ", "_").replace("-", "a")](motion, **kwargs)