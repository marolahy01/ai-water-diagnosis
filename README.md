# ai-water-diagnosis

Système d'aide au diagnostic de pannes pour un réseau de distribution
d'eau potable en zone semi-urbaine (contexte Madagascar / Fianarantsoa).

Prototype démontrable réalisé pour le mini-projet *Raisonnement en
Intelligence Artificielle*. Il implémente et hybride deux formalismes
du cours :

- un **moteur symbolique** (chaînage avant sur une base de règles en
  logique propositionnelle),
- un **réseau bayésien** léger (gestion explicite de l'incertitude,
  taux de base visibles, formule de Bayes appliquée explicitement).

L'architecture hybride combine les deux : les règles filtrent
rapidement les causes impossibles, le réseau bayésien classe les
causes restantes par probabilité, et un module d'explication produit
une justification lisible par un technicien non informaticien.

## Sommaire

- [Architecture](#architecture)
- [Installation](#installation)
- [Lancement de la démonstration](#lancement-de-la-démonstration)
- [Utilisation en ligne de commande](#utilisation-en-ligne-de-commande)
- [Évaluation automatique](#évaluation-automatique)
- [Tests](#tests)
- [Structure du dépôt](#structure-du-dépôt)
- [Gestion de l'incertitude, de l'incomplétude et des contradictions](#gestion-de-lincertitude-de-lincomplétude-et-des-contradictions)
- [Limites et pistes d'amélioration](#limites-et-pistes-damélioration)

## Architecture

```
Observations (opérateur / capteurs)
        │
        ▼
┌───────────────────────┐
│  Moteur symbolique     │  config/rules.yaml
│  (chaînage avant)      │  -> causes candidates + causes écartées
└───────────┬────────────┘  + trace des règles activées
            │ causes candidates
            ▼
┌───────────────────────┐
│  Moteur bayésien       │  config/bayes_network.yaml
│  (inférence naïve,     │  -> P(cause | observations), restreinte
│   causes mutuellement  │     aux causes candidates, renormalisée
│   exclusives)          │
└───────────┬────────────┘
            │ causes classées par probabilité
            ▼
┌───────────────────────┐
│  Module d'explication  │  -> diagnostic principal, niveau de
│                        │     confiance, action recommandée,
└───────────────────────┘     justification textuelle
```

Trois configurations sont disponibles pour le protocole d'évaluation
comparatif (voir section [Évaluation](#évaluation-automatique)) :
`rules` (règles seules), `bayes` (réseau bayésien seul) et `hybrid`
(pipeline complet, configuration principale du système).

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement de la démonstration

Interface web (Streamlit) :

```bash
streamlit run demo.py
```

## Utilisation en ligne de commande

Mode interactif (saisie guidée des observations) :

```bash
python app.py
```

Mode non interactif, à partir d'un fichier JSON :

```bash
python app.py --json data/exemple_observation.json
```

Ou avec un JSON inline, en forçant une configuration et une sortie JSON :

```bash
python app.py --json '{"pression":"basse","debit":"nul","pompe_etat":"ok"}' \
    --config-only hybrid --as-json
```

## Évaluation automatique

Le script `evaluate.py` exécute les 12 cas de test (`data/test_cases.json` :
9 cas standards + 3 cas limites) sur les trois configurations et affiche
un tableau comparatif (exactitude, cohérence, latence moyenne, cas
limites correctement traités) :

```bash
python evaluate.py --verbose
```

Résultat obtenu sur le jeu de test fourni :

| Configuration     | Exactitude | Cohérence | Latence moy. | Cas limites OK |
|--------------------|-----------|-----------|---------------|-----------------|
| Règles seules      | 9/12 (75 %)  | 100 %     | < 1 ms        | 1/3             |
| Bayes seul         | 11/12 (92 %) | 100 %     | < 1 ms        | 2/3             |
| **Hybride (C)**    | **12/12 (100 %)** | 100 % | < 1 ms   | **3/3**         |

L'approche hybride surpasse nettement les approches isolées, en
particulier sur les cas limites (observations incomplètes, symptômes
contradictoires, cause rare avec symptômes ambigus), conformément à
l'analyse attendue dans le rapport.

Pour sauvegarder un rapport détaillé :

```bash
python evaluate.py --json-out rapport_evaluation.json
```

## Tests

```bash
pytest -q
```

Les tests couvrent : le chargement de la base de connaissances, le
comportement face à des observations manquantes, la détection et la
résolution d'un conflit entre règles, l'exécution des trois
configurations sur l'ensemble du jeu de test, et le critère
d'acceptation du cadrage (exactitude ≥ 80 % sur les cas standards).

## Structure du dépôt

```
ai-water-diagnosis/
├── README.md
├── requirements.txt
├── app.py                     # CLI interactive / batch
├── demo.py                    # Interface web Streamlit
├── evaluate.py                # Script d'évaluation automatique (12 cas, 3 configs)
├── config/
│   ├── rules.yaml              # Base de règles (logique propositionnelle)
│   └── bayes_network.yaml      # Causes, a priori, CPT, actions recommandées
├── data/
│   ├── test_cases.json         # 12 cas de test (9 standards + 3 limites)
│   └── exemple_observation.json
├── src/
│   ├── models.py                # Structures de données (Observation, Diagnosis, ...)
│   ├── rules_engine.py          # Moteur symbolique (chaînage avant)
│   ├── bayesian_engine.py       # Moteur probabiliste (inférence bayésienne légère)
│   ├── hybrid_engine.py         # Orchestration + 3 configurations d'évaluation
│   └── explanation.py           # Génération de la justification lisible
└── tests/
    └── test_engine.py           # Tests unitaires (pytest)
```

## Gestion de l'incertitude, de l'incomplétude et des contradictions

- **Incertitude** : le réseau bayésien retourne toujours une
  distribution de probabilités sur les causes candidates (jamais une
  réponse binaire), avec un niveau de confiance qualitatif
  (faible / moyenne / élevée) dérivé de la probabilité du diagnostic
  principal.
- **Incomplétude** : une observation absente n'est jamais forcée. Côté
  règles, une condition portant sur un fait inconnu empêche simplement
  la règle concernée de se déclencher (pas d'erreur). Côté bayésien,
  un fait manquant est absent du produit de vraisemblance : il ne
  pénalise ni ne favorise aucune cause.
- **Contradictions** : lorsqu'une cause est simultanément proposée par
  une règle et écartée par une autre, le conflit est résolu par
  **spécificité** (la règle ayant le plus de conditions l'emporte) et
  **journalisé explicitement** dans la trace (`diagnosis.conflicts`),
  afin que l'opérateur puisse voir qu'un arbitrage a eu lieu.
- Si **aucune règle ne se déclenche**, le système ne bloque pas : il
  bascule en mode de secours (`fallback_used = True`), transmet
  l'ensemble des causes non explicitement écartées au réseau bayésien,
  et le signale dans l'explication.

## Limites et pistes d'amélioration

- Les tables de probabilité conditionnelle sont estimées à dire
  d'expert et non apprises sur des données historiques massives, ce
  qui peut introduire des biais.
- L'hypothèse de mutuelle exclusivité des causes simplifie la réalité
  (plusieurs pannes peuvent coexister) ; une extension naturelle serait
  un réseau bayésien multi-causes (variables binaires indépendantes
  par cause plutôt qu'une variable catégorielle unique).
- Aucune boucle d'apprentissage automatique des nouveaux cas
  (Case-Based Reasoning) n'est encore implémentée.
- L'interface n'est pas connectée en temps réel aux capteurs du réseau ;
  elle attend une saisie (manuelle ou fichier JSON) des observations.
- Un diagnostic erroné pouvant retarder une intervention critique pour
  la santé publique, le système affiche systématiquement son niveau de
  confiance et recommande de faire confirmer le diagnostic par un
  technicien avant toute action lourde (cf. `config/bayes_network.yaml`,
  section `actions`).
