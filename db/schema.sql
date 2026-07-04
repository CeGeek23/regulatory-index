-- ============================================================================
--  regulatory-index — SCHÉMA RELATIONNEL NORMALISÉ (PROVISOIRE)
-- ----------------------------------------------------------------------------
--  ⚠️ PROVISOIRE : dérivé de nos données actuelles (obligations / relations /
--     glossaire). À RÉCONCILIER avec le modèle du client (les 14 onglets de son
--     Excel) dès réception — ce fichier est un point de départ, pas la cible finale.
--
--  Vit dans un schéma dédié `regindex` : n'interfère PAS avec la base source du
--  dump (tables dans `public`). Le DROP ci-dessous ne concerne que ce brouillon.
--
--  Appliquer :  just schema-apply     (ou psql -f db/schema.sql)
-- ============================================================================

DROP SCHEMA IF EXISTS regindex CASCADE;      -- ne touche QUE le brouillon regindex
CREATE SCHEMA regindex;
SET search_path TO regindex;

-- === Dimensions / référentiels =============================================

-- Acte réglementaire (source d'un niveau donné).
CREATE TABLE source (
    source_id   text PRIMARY KEY,             -- ex. 'AIFMD_L1'
    celex       text,                          -- ex. '32011L0061'
    title       text NOT NULL,
    level       smallint,                      -- 1 = directive/règlement de base, 2 = délégué…
    issuer      text,                          -- ex. 'EU_Parliament_Council'
    language    char(2),                       -- 'EN' | 'FR'
    url         text
);

-- Thème réglementaire (Governance, Risk Management…).
CREATE TABLE theme (
    theme_code  text PRIMARY KEY,             -- code stable (ex. 'GOV')
    label_en    text NOT NULL,
    label_fr    text
);

-- Acteur, avec la typologie du glossaire (acteur / produit / activité).
CREATE TABLE actor (
    actor_id    bigserial PRIMARY KEY,
    label_en    text NOT NULL UNIQUE,
    label_fr    text,
    actor_type  text CHECK (actor_type IN ('actor','product','activity','concept','untyped'))
);

-- Action (verbe d'obligation), vocabulaire contrôlé.
CREATE TABLE action (
    action_id   bigserial PRIMARY KEY,
    label_en    text NOT NULL UNIQUE,
    label_fr    text
);

-- Vocabulaire contrôlé générique (objets, conditions, types de relation, acronymes…).
CREATE TABLE controlled_vocabulary (
    id          bigserial PRIMARY KEY,
    kind        text NOT NULL,                 -- 'object'|'condition'|'relation_type'|'acronym'|…
    code        text NOT NULL,
    label_en    text,
    label_fr    text,
    UNIQUE (kind, code)
);

-- Article (subdivision de niveau article d'un acte).
CREATE TABLE article (
    article_id      bigserial PRIMARY KEY,
    source_id       text NOT NULL REFERENCES source(source_id),
    number          text NOT NULL,             -- '21', '30a', '69b'…
    title           text,
    hierarchy_path  text,
    UNIQUE (source_id, number)
);

-- Traçabilité d'un run d'extraction (modèle, version, date).
CREATE TABLE extraction_run (
    run_id       bigserial PRIMARY KEY,
    model        text NOT NULL,                -- ex. 'qwen2.5-7b-instruct'
    task_version integer,
    started_at   timestamptz DEFAULT now(),
    params       jsonb
);

-- === Faits : obligations ====================================================

-- L'obligation = qui (actor) doit quoi (action) sur quoi (object), sous condition,
-- ancrée à son verbatim + article. Table centrale.
CREATE TABLE obligation (
    obligation_id       text PRIMARY KEY,      -- ex. 'AIFMD-GOV-0001'
    source_id           text NOT NULL REFERENCES source(source_id),
    article_id          bigint REFERENCES article(article_id),
    language            char(2),
    actor_id            bigint REFERENCES actor(actor_id),
    action_id           bigint REFERENCES action(action_id),
    object              text,                  -- objet (texte libre, canonicalisable)
    theme_code          text REFERENCES theme(theme_code),
    sub_theme           text,
    condition           text,
    scope               text,
    exception           text,
    expected_evidence   text,
    associated_control  text,
    verbatim_text       text NOT NULL,         -- passage exact (fidélité au texte)
    char_start          integer,
    char_end            integer,
    extraction_run_id   bigint REFERENCES extraction_run(run_id),
    human_validated     boolean NOT NULL DEFAULT false
);

-- Références citées PAR une obligation (multi-valué → table propre = normalisation).
CREATE TABLE obligation_citation (
    citation_id      bigserial PRIMARY KEY,
    obligation_id    text NOT NULL REFERENCES obligation(obligation_id),
    cited_reference  text NOT NULL,            -- ex. 'Directive 2009/65/EC, Article 15'
    target_source_id text REFERENCES source(source_id),   -- résolu si possible
    target_article   text
);

-- Renvois OBLIGATION → OBLIGATION (le cœur du graphe cross-level L2→L1).
CREATE TABLE obligation_relation (
    relation_id           bigserial PRIMARY KEY,
    source_obligation_id  text NOT NULL REFERENCES obligation(obligation_id),
    target_obligation_id  text NOT NULL REFERENCES obligation(obligation_id),
    relation_type         text,                -- 'operationalizes'|'clarifies'|'references'…
    citation_in_text      text,
    evidence_text         text,
    char_start            integer,
    char_end              integer,
    validated             boolean NOT NULL DEFAULT false
);

-- === Glossaire : termes définis ============================================

CREATE TABLE defined_term (
    term_id        bigserial PRIMARY KEY,
    source_id      text NOT NULL REFERENCES source(source_id),
    term_en        text,
    term_fr        text,
    term_type      text CHECK (term_type IN ('actor','product','activity','concept','untyped')),
    legal_basis    text,                        -- article de définition
    definition_en  text,
    definition_fr  text
);

-- Renvois portés par une définition (le champ `cites` du glossaire).
CREATE TABLE defined_term_citation (
    id               bigserial PRIMARY KEY,
    term_id          bigint NOT NULL REFERENCES defined_term(term_id),
    cited_reference  text NOT NULL,
    target_source_id text REFERENCES source(source_id)
);

-- === Index utiles ===========================================================
CREATE INDEX ON obligation (source_id);
CREATE INDEX ON obligation (theme_code);
CREATE INDEX ON obligation (actor_id);
CREATE INDEX ON article (source_id);
CREATE INDEX ON obligation_relation (source_obligation_id);
CREATE INDEX ON obligation_relation (target_obligation_id);
