# Chatbot Evaluation

Ce dossier contient les jeux de tests JSONL utilises par `scripts/run_chat_eval.py`.

Chaque ligne represente un cas de test. Champs utiles:

- `id`: identifiant stable du cas.
- `question`: question envoyee a `/chat`.
- `expected_keywords`: mots ou valeurs qui doivent apparaitre dans la reponse.
- `expected_regex`: expression reguliere optionnelle.
- `expected_sources`: sources RAG attendues, par exemple `{"doctype": "Item", "docname": "ITEM-001"}`.
- `expected_tools`: tools attendus, par exemple `fetch_accounting_data`.
- `setup_rag_documents`: documents temporaires a indexer avant l'evaluation.
- `modes`: sous-ensemble de `baseline`, `tools`, `rag`, `hybrid`.
- `enabled`: mettre `false` pour garder un exemple sans le compter.

Modes mesures:

- `baseline`: `use_rag=false`, `use_tools=false`
- `tools`: `use_rag=false`, `use_tools=true`
- `rag`: `use_rag=true`, `use_tools=false`
- `hybrid`: `use_rag=true`, `use_tools=true`
