-- ============================================================================
--  regulatory-index — MODÈLE RELATIONNEL IRR v2 (réconcilié)
-- ----------------------------------------------------------------------------
--  Provenance : modele_relationnel_raglogic_irr_v2.xlsx (15 onglets du client).
--  Le classeur n'est qu'une maquette : la SOURCE DE VÉRITÉ est ce schéma
--  PostgreSQL. Neo4j et l'index vectoriel sont des DÉRIVÉS reconstruits depuis
--  `regindex` (vues → embeddings/graphe) ; ils ne portent jamais la donnée
--  golden et ne sont jamais réimportés vers PG.
--
--  Vit dans un schéma dédié `regindex` : n'interfère PAS avec la base source du
--  dump (tables dans `public`). Le DROP ci-dessous ne concerne que `regindex`.
--
--  Appliquer :  uv run --no-sync python scripts/apply_schema.py
-- ============================================================================

DROP SCHEMA IF EXISTS regindex CASCADE;      -- ne touche QUE le schéma regindex
CREATE SCHEMA regindex;
SET search_path TO regindex;

-- INVARIANT : aucune FK ne porte de ON DELETE (défaut NO ACTION, intentionnel).
-- La donnée est golden/auditable : supprimer une regulation encore référencée
-- doit ÉCHOUER, jamais détruire silencieusement statements et coverage_audit en
-- cascade. Une suppression est une opération explicite, enfants d'abord
-- (coverage_audit → liaisons/conditions/exceptions/relations → statement →
-- source_unit → regulation).

-- === 01 · Source réglementaire (déterministe, avant IA) =====================

-- Référentiel des textes sources. PK text lisible : 'REG-<celex>'.
CREATE TABLE regulation (
    regulation_id           text PRIMARY KEY,
    celex_id                text,
    official_title          text NOT NULL,
    short_name              text,
    legal_level             text,               -- 'L1' | 'L2' | 'L3' (niveau Lamfalussy)
    legal_instrument_type   text,               -- 'Directive' | 'Regulation' | …
    jurisdiction            text,
    language                text,
    consolidation_date      date,
    eurlex_url              text,
    status                  text,               -- cycle de vie du texte ('Active'…)
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- Découpage déterministe du texte, AVANT toute interprétation IA. PK stable
-- lisible : 'SU-<celex>-ART<n>-P<n>-S<n>'. `source_text_hash` détecte le
-- changement de texte source (même contrat que subdivisions.content_hash de
-- Lalande) : un hash différent ⇒ re-extraction des statements aval.
CREATE TABLE source_unit (
    source_unit_id      text PRIMARY KEY,
    regulation_id       text NOT NULL REFERENCES regulation(regulation_id),
    title_number        text,
    chapter_number      text,
    section_number      text,
    article_number      text,
    paragraph_number    text,
    point_number        text,
    subpoint_number     text,
    sentence_number     text,
    source_text_exact   text NOT NULL,
    source_text_hash    text NOT NULL,
    structural_path     text,                   -- chemin lisible : 'AIFMD > Chapter III > Article 15 > …'
    is_normative        boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- === 03 · Statement (unité logique extraite et normalisée) ==================

-- Cœur du modèle. INVARIANT : aucun statement sans source exacte
-- (`source_unit_id` NOT NULL). `statement_type`/`validation_status` en
-- vocabulaire anglais snake_case (CHECK). theme/subtheme/business_process/
-- risk_category portent des codes de `dictionary_entry` (réf. souple, non FK :
-- subtheme/business_process/risk_category n'ont pas de table dédiée au v2).
CREATE TABLE statement (
    statement_id                text PRIMARY KEY,
    source_unit_id              text NOT NULL REFERENCES source_unit(source_unit_id),
    regulation_id               text NOT NULL REFERENCES regulation(regulation_id),
    statement_type              text NOT NULL CHECK (statement_type IN (
                                    'obligation','prohibition','definition','condition',
                                    'exception','power','right','authorisation',
                                    'scope','reference')),
    legal_modality              text,           -- 'mandatory' | 'permissive' | 'prohibitive' | …
    applicability_status        text,           -- 'always' | 'conditional' | …
    statement_text_exact        text NOT NULL,
    statement_text_normalized   text,
    semantic_intent             text,
    theme_id                    text,
    subtheme_id                 text,
    business_process_id         text,
    risk_category_id            text,
    extraction_model            text,
    confidence_score            numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    validation_status           text NOT NULL DEFAULT 'pending' CHECK (validation_status IN (
                                    'pending','validated','rejected','needs_review')),
    validated_by                text,
    validated_at                timestamptz,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now()
);

-- === 04–06 · Dictionnaires (référentiels contrôlés) =========================

-- PK text lisible cohérente avec le modèle ('ACT-AIFM'). `actor_type`,
-- `action_category`, `object_category` sont des catégories ouvertes du
-- dictionnaire (pas de CHECK : enrichies progressivement par l'expert).

CREATE TABLE actor (
    actor_id                text PRIMARY KEY,
    canonical_name          text NOT NULL,
    display_name            text,
    actor_type              text,
    parent_actor_id         text REFERENCES actor(actor_id),
    definition_statement_id text REFERENCES statement(statement_id),
    definition_text         text,
    jurisdiction            text,
    source_regulation_id    text REFERENCES regulation(regulation_id),
    is_active               boolean NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE action (
    action_id               text PRIMARY KEY,
    canonical_verb          text NOT NULL,
    display_label           text,
    action_category         text,
    legal_effect            text,
    original_verb_examples  text,
    description             text,
    is_active               boolean NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE regulatory_object (
    object_id               text PRIMARY KEY,
    canonical_name          text NOT NULL,
    display_name            text,
    object_category         text,
    parent_object_id        text REFERENCES regulatory_object(object_id),
    definition_statement_id text REFERENCES statement(statement_id),
    description             text,
    source_regulation_id    text REFERENCES regulation(regulation_id),
    is_active               boolean NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- === 07–09 · Liaisons statement ↔ dictionnaires =============================

-- PK surrogate (identity) : ces lignes sont dérivées de l'extraction, pas des
-- entités golden nommées. `source_unit_id` redondant avec statement mais porté
-- par le modèle (traçabilité directe de chaque liaison à son verbatim).

CREATE TABLE statement_actor (
    statement_actor_id  bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    statement_id        text NOT NULL REFERENCES statement(statement_id),
    actor_id            text NOT NULL REFERENCES actor(actor_id),
    actor_role          text,                   -- 'subject' | 'beneficiary' | 'counterparty' | …
    actor_qualifier     text,
    is_primary_actor    boolean NOT NULL DEFAULT false,
    source_unit_id      text REFERENCES source_unit(source_unit_id),
    confidence_score    numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE statement_action (
    statement_action_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    statement_id        text NOT NULL REFERENCES statement(statement_id),
    action_id           text NOT NULL REFERENCES action(action_id),
    original_action_text text,
    action_rank         integer,
    is_primary_action   boolean NOT NULL DEFAULT false,
    source_unit_id      text REFERENCES source_unit(source_unit_id),
    confidence_score    numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE statement_object (
    statement_object_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    statement_id        text NOT NULL REFERENCES statement(statement_id),
    object_id           text NOT NULL REFERENCES regulatory_object(object_id),
    object_role         text,                   -- 'main_object' | 'instrument' | …
    original_object_text text,
    object_rank         integer,
    is_primary_object   boolean NOT NULL DEFAULT false,
    source_unit_id      text REFERENCES source_unit(source_unit_id),
    confidence_score    numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- === 10–11 · Conditions & exceptions ========================================

CREATE TABLE condition (
    condition_id        bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    statement_id        text NOT NULL REFERENCES statement(statement_id),
    condition_type      text,                   -- 'scope' | 'trigger' | 'threshold' | …
    condition_text_exact text,
    condition_normalized text,
    operator            text,                   -- opérateur de seuil ('>=','<','=' …)
    threshold_value     text,
    threshold_unit      text,
    trigger_event       text,
    applicability_scope text,
    source_unit_id      text REFERENCES source_unit(source_unit_id),
    confidence_score    numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Porte aussi l'ABSENCE documentée d'exception ('no_explicit_exception') : une
-- ligne y atteste que le point a été revu, pas seulement qu'une exception existe.
CREATE TABLE exception (
    exception_id        bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    statement_id        text NOT NULL REFERENCES statement(statement_id),
    exception_type      text,
    exception_text_exact text,
    exception_normalized text,
    exception_scope     text,
    source_unit_id      text REFERENCES source_unit(source_unit_id),
    confidence_score    numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- === 12 · Relations entre statements (graphe interne + renvois) =============

-- `target_statement_id` nullable : un renvoi peut viser un texte externe non
-- encore ingéré, alors décrit en clair par `target_reference`.
CREATE TABLE statement_relation (
    relation_id         bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    source_statement_id text NOT NULL REFERENCES statement(statement_id),
    target_statement_id text REFERENCES statement(statement_id),
    target_reference    text,
    relation_type       text,                   -- 'uses_definition' | 'operationalises' | 'derogates' | …
    relation_direction  text,                   -- 'source_to_target' | 'bidirectional' | …
    relation_description text,
    source_unit_id      text REFERENCES source_unit(source_unit_id),
    confidence_score    numeric(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- === 13 · Traduction opérationnelle (contrôles & preuves) ===================

CREATE TABLE control_mapping (
    control_mapping_id      bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    statement_id            text NOT NULL REFERENCES statement(statement_id),
    expected_control        text,
    expected_evidence       text,
    expected_procedure      text,
    control_frequency       text,
    control_owner_function  text,
    evidence_type           text,
    testing_method          text,
    automation_potential    text,               -- 'low' | 'medium' | 'high'
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- === 14 · Coverage audit (preuve d'exhaustivité) ============================

-- INVARIANT métier : une (et une seule) ligne par source_unit — l'exhaustivité
-- se prouve ici. UNIQUE(source_unit_id) encode l'unicité ; l'EXISTENCE (toute
-- source_unit auditée) est garantie par le pipeline, pas par une contrainte SQL.
-- `coverage_status` en vocabulaire anglais snake_case (CHECK).
CREATE TABLE coverage_audit (
    coverage_id             bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    regulation_id           text NOT NULL REFERENCES regulation(regulation_id),
    source_unit_id          text NOT NULL UNIQUE REFERENCES source_unit(source_unit_id),
    statement_id            text REFERENCES statement(statement_id),
    coverage_status         text NOT NULL CHECK (coverage_status IN (
                                'covered','partially_covered','not_covered',
                                'non_normative','to_review')),
    has_statement           boolean NOT NULL DEFAULT false,
    has_actor               boolean NOT NULL DEFAULT false,
    has_action              boolean NOT NULL DEFAULT false,
    has_object              boolean NOT NULL DEFAULT false,
    has_condition_review    boolean NOT NULL DEFAULT false,
    has_exception_review    boolean NOT NULL DEFAULT false,
    requires_human_review   boolean NOT NULL DEFAULT false,
    review_reason           text,
    review_status           text,               -- 'passed' | 'pending' | 'failed'
    checked_at              timestamptz,
    checked_by              text
);

-- === 15 · Dictionnaire d'amorçage (référentiel contrôlé initial) ============

-- Seed unifié des tables 04/05/06 + types de statements + thèmes (onglet 15 du
-- classeur). `dictionary_type` sépare les familles ; UNIQUE(dictionary_type,
-- code) car un code n'est unique qu'au sein de sa famille.
CREATE TABLE dictionary_entry (
    entry_id        bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    dictionary_type text NOT NULL CHECK (dictionary_type IN (
                        'actor','action','object','statement_type','theme')),
    code            text NOT NULL,              -- 'ACT-AIFM', 'THM-RISK', 'STT-OBLIGATION' …
    canonical_name  text NOT NULL,
    category        text,                       -- actor_type / action_category / object_category / default_subtheme
    parent_code     text,
    description     text,
    UNIQUE (dictionary_type, code)
);

-- === Index utiles ===========================================================
-- FKs chaudes + accès métier récurrents (filtre par texte, audit par statut).
CREATE INDEX ON source_unit (regulation_id);
CREATE INDEX ON statement (source_unit_id);
CREATE INDEX ON statement (regulation_id);
CREATE INDEX ON actor (parent_actor_id);
CREATE INDEX ON actor (source_regulation_id);
CREATE INDEX ON regulatory_object (parent_object_id);
CREATE INDEX ON regulatory_object (source_regulation_id);
CREATE INDEX ON statement_actor (statement_id);
CREATE INDEX ON statement_actor (actor_id);
CREATE INDEX ON statement_action (statement_id);
CREATE INDEX ON statement_action (action_id);
CREATE INDEX ON statement_object (statement_id);
CREATE INDEX ON statement_object (object_id);
CREATE INDEX ON condition (statement_id);
CREATE INDEX ON exception (statement_id);
CREATE INDEX ON statement_relation (source_statement_id);
CREATE INDEX ON statement_relation (target_statement_id);
CREATE INDEX ON control_mapping (statement_id);
CREATE INDEX ON coverage_audit (regulation_id);
CREATE INDEX ON coverage_audit (statement_id);
CREATE INDEX ON coverage_audit (coverage_status);
