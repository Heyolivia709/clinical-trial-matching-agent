# Match against immutable versioned snapshots

Matching runs use one immutable ClinicalTrials.gov Trial Corpus Snapshot with frozen source records, parsed criteria, indexes, and configuration rather than querying or reparsing live data during a run. This trades immediate freshness for reproducibility and evidence stability; freshness is handled through explicit snapshot warnings and new snapshot versions, never mutation of historical Matching Runs.
