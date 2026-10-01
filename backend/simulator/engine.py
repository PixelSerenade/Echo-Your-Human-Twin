import os
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

# Deterministic base effects per 1 hour of activity
# Metrics clamped to [0, 100]
BASE_ACTIVITY_EFFECTS = {
    "study": {
        "energy": -12.0,
        "happiness": -4.0,
        "study": +22.0,
        "goals": +14.0,
        "free_time": -18.0
    },
    "badminton": {
        "energy": -8.0,
        "happiness": +22.0,
        "study": 0.0,
        "goals": +4.0,
        "free_time": +10.0
    },
    "netflix": {
        "energy": +8.0,
        "happiness": +14.0,
        "study": 0.0,
        "goals": -5.0,
        "free_time": +20.0
    },
    "project work": {
        "energy": -16.0,
        "happiness": +4.0,
        "study": +12.0,
        "goals": +24.0,
        "free_time": -22.0
    },
    "sleep": {
        "energy": +30.0,
        "happiness": +10.0,
        "study": 0.0,
        "goals": 0.0,
        "free_time": +8.0
    }
}

DEFAULT_INITIAL_STATE = {
    "energy": 70.0,
    "happiness": 65.0,
    "study": 50.0,
    "goals": 55.0,
    "free_time": 40.0
}

def clamp(val: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    return max(min_val, min(max_val, val))

class SimulatorEngine:
    def __init__(self):
        pass

    def simulate_path(
        self,
        activities: List[Dict[str, Any]],
        initial_state: Dict[str, float] = None,
        weights: Dict[str, float] = None,
        modifiers: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Simulate a sequence of activities.
        - Clamps all bars to [0, 100].
        - Applies priority weight adjustments.
        - Applies learned modifiers from simulator_modifiers.
        - Applies diminishing returns on study when energy is low (< 30).
        """
        state = dict(initial_state if initial_state is not None else DEFAULT_INITIAL_STATE)
        weights = weights or {"rational": 0.50, "emotional": 0.25, "ambitious": 0.25}
        modifiers = modifiers or []

        # Map modifiers by activity
        mod_map = {}
        for m in modifiers:
            act = m.get("activity_name", "").lower()
            if act not in mod_map:
                mod_map[act] = []
            mod_map[act].append(m)

        timeline = []
        timeline.append({"step": "Initial State", "state": {k: round(v, 1) for k, v in state.items()}})

        badminton_bonus_active = False

        for idx, item in enumerate(activities):
            act_name = item.get("activity", "").lower()
            hours = float(item.get("hours", 1.0))
            if hours <= 0:
                continue

            base = BASE_ACTIVITY_EFFECTS.get(act_name, {
                "energy": -5.0, "happiness": 0.0, "study": 0.0, "goals": 0.0, "free_time": 0.0
            })

            # 1. Diminishing returns on study / project when energy < 30
            curr_energy = state["energy"]
            study_scaling = 1.0
            diminishing_applied = False
            if act_name in ("study", "project work") and curr_energy < 30.0:
                diminishing_applied = True
                # Severe drop in study efficiency when exhausted
                study_scaling = max(0.20, curr_energy / 40.0)

            # 2. Priority weight personality adjustments
            # High rational weight mitigates fatigue slightly via structured pacing
            energy_fatigue_mult = 1.0 - (0.15 * weights.get("rational", 0.33))
            # High emotional weight boosts happiness recovery on recreation
            recreation_happiness_mult = 1.0 + (0.25 * weights.get("emotional", 0.33))
            # High ambitious weight boosts project / study goals achievement
            ambition_goals_mult = 1.0 + (0.30 * weights.get("ambitious", 0.33))

            # 3. Apply base effects * hours
            delta_energy = base["energy"] * hours
            if delta_energy < 0:
                delta_energy *= energy_fatigue_mult

            delta_happiness = base["happiness"] * hours
            if delta_happiness > 0 and act_name in ("badminton", "netflix", "sleep"):
                delta_happiness *= recreation_happiness_mult
            if diminishing_applied:
                # Extra happiness drain studying while exhausted
                delta_happiness -= (4.0 * hours)

            delta_study = base["study"] * hours * study_scaling
            delta_goals = base["goals"] * hours
            if act_name in ("project work", "study"):
                delta_goals *= ambition_goals_mult

            delta_free_time = base["free_time"] * hours

            # 4. Check badminton focus / energy bonus
            if act_name == "badminton":
                badminton_bonus_active = True

            if badminton_bonus_active and act_name in ("study", "project work"):
                # Bonus from previous badminton session
                delta_study += 5.0
                delta_energy += 3.0
                badminton_bonus_active = False

            # 5. Apply user learned modifiers from DB
            if act_name in mod_map:
                for m in mod_map[act_name]:
                    metric = m.get("metric_affected", "")
                    val = float(m.get("delta_value", 0.0))
                    if metric == "energy":
                        delta_energy += val
                    elif metric == "happiness":
                        delta_happiness += val
                    elif metric == "study" or metric == "focus":
                        delta_study += val
                    elif metric == "goals":
                        delta_goals += val
                    elif metric == "free_time":
                        delta_free_time += val

            # Apply and clamp
            state["energy"] = clamp(state["energy"] + delta_energy)
            state["happiness"] = clamp(state["happiness"] + delta_happiness)
            state["study"] = clamp(state["study"] + delta_study)
            state["goals"] = clamp(state["goals"] + delta_goals)
            state["free_time"] = clamp(state["free_time"] + delta_free_time)

            timeline.append({
                "step": f"{act_name.capitalize()} ({hours}h)",
                "diminishing_returns": diminishing_applied,
                "state": {k: round(v, 1) for k, v in state.items()}
            })

        init_state = initial_state if initial_state is not None else DEFAULT_INITIAL_STATE
        final_state = {k: round(v, 1) for k, v in state.items()}
        deltas = {k: round(final_state[k] - init_state.get(k, DEFAULT_INITIAL_STATE[k]), 1) for k in final_state}

        return {
            "initial_state": {k: round(v, 1) for k, v in init_state.items()},
            "final_state": final_state,
            "deltas": deltas,
            "timeline": timeline
        }

    def compare_paths(
        self,
        path_a: List[Dict[str, Any]],
        path_b: List[Dict[str, Any]],
        initial_state: Dict[str, float] = None,
        weights: Dict[str, float] = None,
        modifiers: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Compare Path A vs Path B side-by-side."""
        res_a = self.simulate_path(path_a, initial_state, weights, modifiers)
        res_b = self.simulate_path(path_b, initial_state, weights, modifiers)

        diff = {
            k: round(res_a["final_state"][k] - res_b["final_state"][k], 1)
            for k in res_a["final_state"]
        }

        return {
            "path_a": res_a,
            "path_b": res_b,
            "net_difference_a_minus_b": diff,
            "initial_state": res_a["initial_state"]
        }

simulator_engine = SimulatorEngine()
