# Bundle fixtures

## `timeline-coverage.json`

An authored FHIR R4 Bundle, written to exercise every parsing rule of
specification sections 5 through 5.4 in one file. Not a Synthea output and not
one of the six Authored Synthetic Scenarios — those carry hidden Scenario
Manifests and arrive with #19. This one has nothing hidden in it.

**Provenance.** Drafted by the assistant with AI assistance; reviewed by rendong
on 2026-08-24. Terminology codes were checked against RxNav and a FHIR
terminology server rather than recalled: osimertinib 80 MG Oral Tablet is RxNorm
1721581, PD-L1 by clone 22C3 is LOINC 83052-1, EGFR c.2573T>G — which is L858R —
is 55766-0, ALK rearrangements by FISH is 78205-2, neutrophils in blood is 751-8,
ECOG performance status score is 89247-1, and the SNOMED codes are 254637007
(non-small cell lung cancer), 94225005 (metastatic malignant neoplasm to brain)
and 26643006 (oral route).

| Resource | The rule it exercises |
| --- | --- |
| `patient-1` | Birth date with precision, administrative sex, geography |
| `cond-1` | Clinical Time from `onsetDateTime`, not from `recordedDate` |
| `cond-2` | Year-only onset: precision preserved, never widened |
| `cond-3` | A supported type with no code: inventoried, not dropped |
| `obs-1`, `obs-2` | A correction chain that flips the answer, negative to positive |
| `obs-3` | A qualitative result that never becomes a number |
| `obs-4` | `entered-in-error`: the fact is kept, with its status |
| `obs-5` | `preliminary`: same |
| `obs-6` | A comparator and a reference range, both preserved |
| `obs-7` | Dated after the assessment time: not a fact, still inventoried |
| `obs-8`, `obs-9` | Local and central laboratories disagreeing on one day |
| `medadmin-1` | An exposure interval with a route |
| `medadmin-2` | A year-only administration date |
| `medreq-1` | An order with no administration: intent is not exposure |
| `enc-1`, `doc-1` | Outside the evidence-bearing boundary: inventoried with identity |

The patient is synthetic and authored. No real record, and no PHI, is involved.

## `scn-01.json` through `scn-06.json`

The six Authored Synthetic Scenarios of specification section 4.4, one FHIR R4
Bundle each. `fixtures/scenarios.json` lists them with the `assessment_as_of`
each is screened at, because a Bundle does not say when screening happened and
inferring it from the newest resource in the file would move the Assessment Time
whenever a record gained a row.

Each Bundle holds one patient, three to five conditions, a routine visit of nine
vital signs and thirteen chemistry results, the oncology facts the criteria turn
on, and two or three resources outside the evidence-bearing boundary. That comes
to 30 to 45 facts, which is enough record that finding the right one is work.

Some of those facts are planted hazards of section 8.3 — a retracted result, two
laboratories disagreeing, an order that was never administered. Which fact is
which is recorded in the Scenario Manifest beside the Bundle, not here: it is
the answer key, and `fixtures/manifests/README.md` says why it lives where it
does.

**Provenance.** Drafted by the assistant with AI assistance; reviewed by rendong
on 2026-08-24. The oncology and terminology codes are those of the coverage
Bundle above, plus LOINC 47303-3, Anaplastic lymphoma kinase Ag in Tissue by
Immune stain — the ALK protein stain that is the near miss for the ALK
rearrangement test, 78205-2. Vital sign and chemistry codes are the standard
LOINC codes a Synthea record uses. The patients are synthetic and authored, and
no real record or PHI is involved.

Bundles are frozen. Each manifest records the SHA-256 of the Bundle it was
authored against, so editing one file without the other makes the pair fail to
load rather than quietly disagree.
