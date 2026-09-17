"""
Tests unitaires du système de diagnostic hybride.

Lancement :
    pytest -q
"""

import json
from pathlib import Path

import pytest

from src.hybrid_engine import HybridDiagnosisEngine
from src.models import Observation

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def engine() -> HybridDiagnosisEngine:
    return HybridDiagnosisEngine(
        rules_path=ROOT / "config" / "rules.yaml",
        bayes_path=ROOT / "config" / "bayes_network.yaml",
    )


@pytest.fixture(scope="module")
def test_cases():
    with open(ROOT / "data" / "test_cases.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_engine_loads_all_causes(engine):
    assert "fuite_majeure" in engine.bayes_engine.all_causes
    assert "ras" in engine.bayes_engine.all_causes
    assert len(engine.rules_engine.rules) >= 5


def test_hybrid_diagnosis_returns_ranked_causes(engine):
    obs = Observation(pression="basse", debit="nul", pompe_etat="ok")
    diagnosis = engine.diagnose(obs, configuration="hybrid")
    assert diagnosis.ranked_causes
    assert diagnosis.top_cause
    assert 0.0 <= diagnosis.confidence <= 1.0
    assert diagnosis.explanation


def test_missing_observations_do_not_crash(engine):
    obs = Observation()  # aucune observation connue
    diagnosis = engine.diagnose(obs, configuration="hybrid")
    assert diagnosis.top_cause is not None


def test_contradiction_is_logged_and_resolved(engine):
    # pompe déclarée OK mais alarme + tension anormale => conflit R3 vs R6
    obs = Observation(
        pression="basse",
        debit="nul",
        pompe_etat="ok",
        pompe_alarme="oui",
        tension_anormale="oui",
    )
    diagnosis = engine.diagnose(obs, configuration="hybrid")
    assert diagnosis.top_cause == "panne_electrique_pompe"
    assert diagnosis.conflicts, "Un conflit aurait dû être détecté et journalisé."


def test_all_configurations_run_without_error(engine, test_cases):
    for case in test_cases:
        obs = Observation.from_dict(case["observation"])
        for config in ("rules", "bayes", "hybrid"):
            diagnosis = engine.diagnose(obs, configuration=config)
            assert diagnosis.top_cause is not None


def test_hybrid_accuracy_on_full_test_set(engine, test_cases):
    correct = 0
    for case in test_cases:
        obs = Observation.from_dict(case["observation"])
        diagnosis = engine.diagnose(obs, configuration="hybrid")
        if diagnosis.top_cause == case["diagnostic_attendu"]:
            correct += 1
    accuracy = correct / len(test_cases)
    # Critère d'acceptation du cadrage : exactitude >= 80 % sur les cas standards.
    assert accuracy >= 0.80, f"Exactitude hybride trop faible : {accuracy:.0%}"


def test_diagnosis_to_dict_is_json_serializable(engine):
    obs = Observation(turbidite="elevee", plaintes_gout="oui")
    diagnosis = engine.diagnose(obs, configuration="hybrid")
    payload = diagnosis.to_dict()
    json.dumps(payload)  # ne doit pas lever d'exception
    assert payload["diagnostic_principal"] == "contamination"
