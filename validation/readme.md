# Validation

Two things live here:

1. **Hand-crafted test chorales** (`test_chorales.py`) — four SATB
   examples that a theory professor would accept as correct, used to
   catch false positives in the rule layer.

2. **A MusicXML converter** (`convert_musicxml.py`) — for turning real
   Bach chorales (or any other MusicXML score) into `.sharm` files
   that the app can open.

## Running the built-in tests

From the project root:

    python validation/run_validation.py

Expected output on a healthy engine:

    === I-IV-V-I in C major ===
      PASS — 0 fault(s), all expected
    === I-vi-IV-ii6-V-I in C major ===
      PASS — 0 fault(s), all expected
    === i-iv-V-i in A minor ===
      PASS — 0 fault(s), all expected
    === I-IV-Ger65-V-I in C major ===
      PASS — 0 fault(s), all expected

    ============================================================
    RESULT: 4 passed, 0 failed

Any `FAIL` line means the engine reports faults on a chorale we
believe to be correct. The specific fault and its rule_id tell you
which handler or analyzer path is misbehaving.

## Validating real Bach

1. Download the Bach chorales in MusicXML. A good public-domain source
   is the "bach-370-chorales" set maintained by the Center for Computer
   Assisted Research in the Humanities, or the Craig Sapp kern dataset
   available via `humdrum-tools`. Any MusicXML rendering works.

2. Install the converter dependency:

       pip install music21

3. Convert them:

       python validation/convert_musicxml.py path/to/xml/ path/to/sharm/

4. Run the batch validator:

       python validation/run_validation.py --dir path/to/sharm/

   The output reports every fault grouped by rule. Real Bach will
   produce some faults (Bach wasn't bound by textbook rules), but a
   healthy engine should show only a few dozen across all 371 chorales,
   not hundreds. Anything suspicious — a rule firing 300 times on
   music that's obviously correct — is a sign of a bug in the rule or
   in the analyzer.

## Adding a hand-crafted test

Open `test_chorales.py`, add a new dict in the same shape as the
existing entries, and append it to the `CHORALES` list at the bottom.
If the new chorale intentionally violates a rule, put the rule_id in
its `expected_faults` list.