"""Schémas du glossaire : termes définis + table des matières (sommaire).

Ces objets sont produits par le sous-paquet `glossary/` à partir du HTML EUR-Lex, de la
même manière que `ingestion/` produit des NormativeUnit. Ils sont génériques : un
`DefinedTerm` ou une `TableOfContents` n'a rien de spécifique à AIFMD et se reproduit
sur n'importe quel acte EUR-Lex.
"""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, Field

from ..schemas.source import Language, Level

# Catégorie d'un terme défini — schéma UNIQUE du projet : actor | investor | supervisor | concept.
# Les trois premiers = acteurs (personne/entité régulée ou qui agit) ; `concept` = tout le reste
# (objet, instrument, opération, notion, géographie…). None = non classé (« vocab gap »).
TermType = str


class DefinedTerm(BaseModel):
    """Un terme défini dans l'article de définitions d'un texte, bilingue EN/FR."""

    term_id: str = Field(description="Identifiant stable en snake_case, ex. 'aifm'")
    label: str = Field(description="Étiquette du point dans l'article, ex. 'b' ou 'ao'")
    type: TermType | None = Field(default=None, description="actor | investor | supervisor | concept")
    term_en: str
    term_fr: str
    legal_basis: str = Field(description="Renvoi précis, ex. 'AIFMD Art. 4(1)(b)'")
    source_id: str
    celex: str | None = None
    level: Level = 1
    cites: list[str] = Field(
        default_factory=list,
        description="Autres textes que la définition importe/vise (graphe inter-textes)",
    )
    definition_en: str = ""
    definition_fr: str = ""


class TocArticle(BaseModel):
    """Un article dans la table des matières."""

    article: str
    subtitle: str | None = None
    is_definitions: bool = False


class TocSection(BaseModel):
    """Un chapitre / une section regroupant des articles."""

    label: str = Field(description="Ex. 'CHAPTER II' ou 'SECTION 1' (vide si hors structure)")
    title: str = ""
    articles: list[TocArticle] = Field(default_factory=list)


class TableOfContents(BaseModel):
    """Sommaire d'un texte : sections et articles, dans l'ordre du document."""

    source_id: str
    language: Language
    sections: list[TocSection] = Field(default_factory=list)

    def iter_articles(self) -> Iterator[TocArticle]:
        for section in self.sections:
            yield from section.articles

    @property
    def article_count(self) -> int:
        return sum(len(section.articles) for section in self.sections)

    @property
    def definitions_article(self) -> str | None:
        """Numéro de l'article de définitions (sous-titre 'Definitions'/'Définitions'), sinon None."""
        for article in self.iter_articles():
            if article.is_definitions:
                return article.article
        return None
