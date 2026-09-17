#!/usr/bin/env python3
"""
Démonstration Streamlit — Système d'aide au diagnostic de pannes pour un
réseau de distribution d'eau potable.

Lancement :
    streamlit run demo.py
"""

from __future__ import annotations

import json

import streamlit as st

from src.explanation import cause_label
from src.hybrid_engine import HybridDiagnosisEngine
from src.models import Observation

st.set_page_config(page_title="Diagnostic réseau d'eau", layout="wide")


@st.cache_resource
def get_engine() -> HybridDiagnosisEngine:
    return HybridDiagnosisEngine()


def main() -> None:
    engine = get_engine()

    st.title(" Aide au diagnostic — réseau de distribution d'eau potable")
    st.caption("Prototype démonstrable — approche hybride règles + réseau bayésien")

    with st.sidebar:
        st.header("Observations")
        pression = st.selectbox("Pression", ["", "basse", "normale", "haute"])
        debit = st.selectbox("Débit", ["", "nul", "faible", "normal"])
        turbidite = st.selectbox("Turbidité", ["", "elevee", "normale"])
        plaintes_gout = st.selectbox("Plaintes goût", ["", "oui", "non"])
        pompe_alarme = st.selectbox("Alarme pompe", ["", "oui", "non"])
        tension_anormale = st.selectbox("Tension anormale", ["", "oui", "non"])
        pompe_etat = st.selectbox("État pompe", ["", "ok", "hs"])

        st.divider()
        configuration = st.radio(
            "Configuration du moteur",
            options=["hybrid", "rules", "bayes"],
            format_func=lambda c: {"hybrid": "Hybride (recommandé)", "rules": "Règles seules", "bayes": "Bayes seul"}[c],
        )
        run = st.button("Lancer le diagnostic", type="primary", use_container_width=True)

    raw = {
        "pression": pression,
        "debit": debit,
        "turbidite": turbidite,
        "plaintes_gout": plaintes_gout,
        "pompe_alarme": pompe_alarme,
        "tension_anormale": tension_anormale,
        "pompe_etat": pompe_etat,
    }
    data = {k: v for k, v in raw.items() if v}

    if run:
        observation = Observation.from_dict(data)
        diagnosis = engine.diagnose(observation, configuration=configuration)

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Diagnostic")
            level_color = {"élevée": "green", "moyenne": "orange", "faible": "red"}[diagnosis.confidence_level]
            st.markdown(
                f"### {cause_label(diagnosis.top_cause)}  "
                f":{level_color}[({diagnosis.confidence:.0%} — confiance {diagnosis.confidence_level})]"
            )
            st.info(f"**Action recommandée :** {diagnosis.recommended_action}")
            st.text(diagnosis.explanation)

        with col2:
            st.subheader("Causes classées")
            for cs in diagnosis.ranked_causes[:6]:
                st.write(f"{cause_label(cs.cause)}")
                st.progress(min(cs.probability, 1.0))

            st.caption(f"Latence : {diagnosis.latency_ms:.2f} ms · Mode secours : {'oui' if diagnosis.fallback_used else 'non'}")

        with st.expander("Résultat brut (JSON)"):
            st.code(json.dumps(diagnosis.to_dict(), ensure_ascii=False, indent=2), language="json")
    else:
        st.write("Renseignez les observations dans la barre latérale puis cliquez sur **Lancer le diagnostic**.")


if __name__ == "__main__":
    main()
