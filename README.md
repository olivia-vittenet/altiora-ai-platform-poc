# Altiora AI Platform POC - Mock Data

Ce dossier contient les données de test (mocks) nécessaires pour valider l'ingestion, le filtrage et la sécurité de notre POC d'Intelligence Artificielle d'Entreprise.
Ces données reflètent le SI de notre entreprise fictive, **Altiora Group**, avec ses branches américaines (B2B, en anglais) et françaises (B2C, en français).

## Contenu des Mocks

Le dossier `/mocks` contient les fichiers suivants :

*   `users.json` : Simule deux profils de l'Active Directory.
    *   **Sophie** (`s.dev`) : Développeuse Senior dans l'équipe Mobile B2C. A accès aux documents techniques non-confidentiels.
    *   **Marc** (`m.rh`) : Responsable des Ressources Humaines FR. A accès aux documents RH fortement sécurisés.
*   `jira.json` : Tickets de bugs (B2C sur iOS), epics d'architecture (éoliennes B2B) et des tickets RH strictement confidentiels (préparation de contrats).
*   `confluence.json` : Pages documentaires d'ingénierie globale, OKRs de l'entreprise, chartes de télétravail publiques ou grilles de salaires strictement confidentielles.
*   `gitlab.json` : Dépôts de code, Merge Requests et Commits. Contient un projet d'app mobile B2C européen et un backend d'optimisation énergétique B2B aux US. Mêle du code source technique et un backend de gestion des "performance reviews".

## Simulation du Rôle Azure AD (ACL)

Chaque document possède une métadonnée `__mock_acl` qui décrit :
1.  **`allowed_aad_groups`** : Les groupes utilisateurs ("mobile_apps_team", "hr_confidential_france", etc.) qui ont l'autorisation métier de lire le document.
2.  **`visibility`** : "public", "restricted", ou "highly_restricted".

**Comment l'exploiter dans le pipeline RAG ?**
Avant de retourner un résultat de recherche, le moteur doit vérifier que l'utilisateur qui fait la requête (décrit dans `users.json`) possède au moins un des groupes requis dans `allowed_aad_groups` du document.

## Classification et Règles d'Ingestion par l'IA

Tous les documents indexables ont une politique d'ingestion stricte dans l'objet de sécurité :
```json
"classification": "Strictly Confidential",
"ai_ingestion": {
  "is_eligible": false,
  "reason": "Contains PII and salary information. Never index or transmit to AI.",
  "security_owner": "Information Security Office and HR Director"
}
```

**Comment l'exploiter dans le pipeline d'Ingestion ?**
Le crawler/scrapper doit filtrer les documents en amont de la base vectorielle. Si `ai_ingestion.is_eligible` est à `false` (cas des documents `Strictly Confidential` ou `Confidential` contenant des données personnelles Identifiables - PII), **le document ne doit jamais être vectorisé ni envoyé au LLM**.

## Simulation Régionale et Bilingue

Pour valider le multilinguisme et les filtres géographiques, les documents portent des métadonnées comme :
*   `region:france` / `lang:fr` (pour le B2C Mobile).
*   `region:us` / `lang:en` (pour le B2B Industriel).

Cela permet de filtrer l'ingestion ou le contexte RAG selon la région définie sur le profil utilisateur dans `users.json`.
