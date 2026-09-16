# Source chart review and data-handling report

This document describes the six genealogy charts in `data/source-material/charts/`,
their legibility and evidentiary quality, and how their information has been
represented in the normalized registries. It replaces the earlier selective
English transcription, which was useful as a reading aid but was neither a
complete transcription nor a reliable statement of every chart relationship.

The CSV files in `data/registries/` are the source of truth. Polish personal and
place names are retained. Dates are normalized to years in `people.csv`, while
full dates and source wording are preserved in relationship evidence or this
report when they affect interpretation. In the printed charts, `+` before a date
means “died”; `zd.` (*z domu*) means “née.” Inferred surnames and uncertain
connections are explicitly identified instead of being presented as source text.

## Source overview

| ID | File | Description | Quality | Registry treatment |
| --- | --- | --- | --- | --- |
| S1 | `Drzewo Genealogy.png` | Polished modern tree for Wanda Gościńska's branch | Excellent | All displayed relationships are recorded as confirmed. |
| S2 | `Goscinscy z Wapiennego Genealogy.png` | Dense printed Gościński chart with several spouse pedigrees | Good, but structurally dense | Clear solid and dotted connectors are recorded; ambiguous annotations remain in notes. |
| S3 | `Goscinski z Pyrc Genealogy.png` | Handwritten Gościński–Pyrc chart with later descendants | Fair; lower portion is overwritten | Clear upper relationships and readable additions are recorded. Unresolvable lower entries are not forced into families. |
| S4 | `Wladusklana Mickulska Genealogy.png` | Handwritten Antonina and Jerzy Guzyk descendant chart | Fair to good | Family groups are recorded; inferred child surnames and one provisional surname are noted. |
| S5 | `Rodzina Ramsow Geneoaogy.png` | Printed Rams chart with Gościński and Miczulski bridges | Good; right and lower edges are cropped | Clear relationships are confirmed; cropped descendant details and isolated labels are marked probable or uncertain. |
| S6 | `Mickulska Genealogy.png` | Sparse handwritten Stanisław and Władysława descendant chart | Fair | Used to resolve the Małgorzata–Bogdan Pluta branch and to corroborate four children of the head couple. |

## S1 — “Drzewo genealogiczne”

This polished chart begins with Władysława Miczulska and Stanisław Gościński,
then follows their daughter Wanda Gościńska and Wanda's husband Bogumił
Gościński. It gives four children of Wanda and Bogumił—Magdalena, Rafał,
Paulina, and Renata—and the children of the first three couples.

The scan is clean, the names are typeset, and all connectors are unambiguous.
Its relationships are therefore recorded as confirmed. The chart is limited in
scope: it documents Wanda's branch and does not imply that Wanda was the head
couple's only child.

## S2 — “Gościńscy z Wapiennego”

This is the richest historical source. It combines a principal Gościński line,
collateral siblings, descendant households, and dotted spouse pedigrees for the
Miczulski, Łyga, Moszczak, Śliwa, Homa, Szost, Rams, Gruczelak, Jacenik, and
Pyrc families.

The central family line and most printed dates are highly legible, but the page
is dense and some dotted connectors cross other branches. The registry therefore
distinguishes confirmed links from probable links instead of treating every
nearby box as a relationship.

Important handling decisions:

- The shared connector clearly makes Wawrzyniec Gościński (born 1780), Jakub
  Gościński (born 1788), and Stanisław Gościński (born 1785) children of
  Wawrzyniec Gościński (about 1760) and Teresa née Bartmanowicz.
- Franciszek Gościński and Józefa née Szost have a printed child list containing
  Wiktoria, Zofia, Jan, Józef, Andrzej, and Franciszek. Wiktoria was missing from
  the earlier extraction.
- Zofia née Gościńska is shown with a husband identified only as `Pyrc`, with
  children Bronisława, Karol, Tadeusz, and Stefania. S3 supplies the husband's
  given name, Józef, and adds Emil and Stanisław. S2 also states that Zofia
  emigrated to Chicago and married there.
- The dotted spouse pedigrees have been retained as separate `spouse_ancestry`
  families. A dotted line is not downgraded merely because it is dotted; its
  confidence depends on whether its endpoints are visually clear.
- The parentage of Maria/Marianna née Miczulska is cross-checked against S5.
  S5 identifies her father more precisely as Jan Miczulski, born 2 February
  1868, while leaving her mother unclear between his two recorded wives.

The unexplained parenthetical date beside Jan Gościński's birth date and other
isolated annotations are not converted into facts without a clear label.

## S3 — handwritten “Gościński z Pyrc” chart

The upper half repeats Franciszek Gościński and Józefa Szost, showing children
Zofia, Jan, Andrzej, and Józef. This does not contradict Zofia's presence in S2;
instead, S3 omits Wiktoria and the younger Franciszek shown by S2.

S3 identifies Józef Pyrc as a child of Jan Pyrc and Anna Bukowska and shows
Józef with Zofia Gościńska. Their children are Emil, Stanisław, Tadeusz, Karol,
Bronisława, and Stefania. It also records Maria Pyrc with Jan Storoż and a
Franciszek Pyrc as other children of Jan and Anna.

Readable descendant additions include Teresa, Marta, and Barbara under
Bronisław Gościński and Władysława Śliwa; Marek under Edward Gościński and Anna
Maślanka; Mariusz under Jan Gościński and Zofia Jacenik; and Antonina,
Elżbieta, Wanda, and Małgorzata under Stanisław Gościński and Władysława
Miczulska.

The lower portion contains additional names, but repeated overwriting makes
several partner and parent-child lines impossible to distinguish. Legible names
are not automatically treated as people in the normalized tree when their
identity or family placement cannot be separated from overwritten alternatives.

## S4 — handwritten Antonina and Jerzy Guzyk chart

This chart begins with Stanisław Gościński and Władysława Miczulska and follows
their daughter Antonina with Jerzy Guzyk. The central group has four child
branches:

- Joanna with Józef Berduchowski; their children are Jakub and Krzysztof, and
  Jakub is shown with Emilia Pawłowska.
- Łukasz with Katarzyna Sułkowska; their children are Emilia and Olivier.
- Marta with Marcin Magarzewych; their children are Maja and Marcel.
- Grażyna with Andrzej Drabyk.

The scan and connectors are clear enough to confirm the family groupings.
`Magarzewych` remains the best provisional reading of Marcin's surname. The
chart often supplies only a child's first name; the registry's Guzyk,
Berduchowski, and Magarzewych surnames for those children are documented
inheritance inferences, not literal transcriptions. Antonina's Gościńska surname
is likewise inferred from her father and corroborating charts.

## S5 — “Rodzina Ramsów”

This printed chart supplies the Rams branch and its bridge through Bolesław
Rams and Bronisława née Gościńska. It also includes older Rams households,
spouse information, and dotted ancestry for the Gościński and Miczulski spouses.

The main boxes are highly legible. The far-right and bottom edge are cropped,
so some birth details are incomplete even where a connector remains visible.

Important handling decisions:

- Henryk Rams and Genowefa née Gumulak, Michał Rams's two wives, and the full
  Drzązgowski child surnames are retained rather than omitted from the summary.
- The arrow from Maciej Rams and Natalia née Tokarczyk to Hanna Rams, born
  2021, is clear and is recorded as confirmed.
- Józef Drost (born 1961) is legible near Małgorzata Rams and Henryk
  Drzązgowski, but no connector establishes his role. He remains an isolated
  person with an uncertainty note rather than being assigned as a spouse or
  child.
- Rita and Marta Romer appear below Anna Kokoszka and Jan Romer. Their branch
  is retained as probable because the connectors and dates are partly cropped.
- Jan Miczulski, born 2 February 1868, is shown with first wife Antonina née
  Bukowska and second wife Maria née Gruczelak, described as `Jacenikowa` and a
  widow of Andrzej from Folwark. The chart connects Jan to Maria/Marianna née
  Miczulska but does not identify which wife was her mother; only Jan's
  parent-child link is asserted.
- Zofia née Ślaby is described as being from Trzetrzewina and as the widow of
  Jan Miczulski. That biographical note is retained without merging her husband
  with another same-named Jan Miczulski unless independent evidence supports it.

## S6 — later handwritten Stanisław and Władysława chart

This sparse chart corroborates Antonina, Elżbieta, Wanda, and Małgorzata as
children of Stanisław Gościński and Władysława Miczulska. Its most important
clarification is the right-hand branch:

- Małgorzata is shown with **Bogdan Pluta**. The previous extraction incorrectly
  split his full name into two people, “Bogdan” and “Pluto.”
- Małgorzata and Bogdan have children Agnieszka, Beata, and Tomasz.
- Agnieszka is shown with Tomasz; the handwritten surname uses the family-form
  spelling `Wiklowscy`, normalized in the registry to Wiklowski/Wiklowska. Their
  daughter is Łucja.

The chart is sparse but its branch lines are visible. These relationships are
recorded as confirmed except for the Wiklowski surname normalization, which is
kept probable pending family confirmation.

## Reconciliation and quality policy

The six charts overlap but are not treated as equally complete versions of one
tree. A person absent from one chart is not presumed absent from the family.
When two sources show different child lists, the union is retained and each
source's contribution is described in `relationship_evidence.csv`.

Confidence labels mean:

- `confirmed`: the names and relevant connector are clear in the cited chart;
- `probable`: the relationship is visually supported but relies on a cropped
  connector, cross-source identity match, or normalized handwritten surname;
- `uncertain`: the name is readable but its family role or connector cannot be
  assigned safely.

The charts are family-created secondary sources, not civil or parish records.
Even a `confirmed` chart reading means “confirmed as shown on the chart,” not
independently proven historical fact. Dates, identities, and inferred surnames
should be checked against vital, parish, immigration, and cemetery records.
