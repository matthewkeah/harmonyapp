from engine import VerticalSlice, NoteNode
from sheria import RulesEngine, SubmissionEngine, KeySignature, RomanNumeralAnalyzer


def test_submission_workflow():
    print("=== TESTING RED PEN GRADING ENGINE ===")
    rules_engine = RulesEngine()          # uses RULESETS from sheria.py
    c_major = KeySignature(root_pitch=60)

    # Chord 1: G Major (V chord). Soprano has B4 (Leading Tone)
    chord_1 = VerticalSlice(
        soprano=NoteNode(pitch=71, tick_length=480),  # B4
        alto=NoteNode(pitch=62, tick_length=480),     # D4
        tenor=NoteNode(pitch=55, tick_length=480),    # G3
        bass=NoteNode(pitch=43, tick_length=480)      # G2
    )

    # Chord 2: C Major (I chord). Soprano fails resolution.
    chord_2 = VerticalSlice(
        soprano=NoteNode(pitch=67, tick_length=480),  # G4
        alto=NoteNode(pitch=64, tick_length=480),     # E4
        tenor=NoteNode(pitch=60, tick_length=480),    # C4
        bass=NoteNode(pitch=48, tick_length=480)      # C3
    )

    grader = SubmissionEngine()
    report = grader.submit([chord_1, chord_2], rules_engine.rules, c_major)

    print(f"Final Score: {report.final_score}/100")
    for i, fault in enumerate(report.faults, 1):
        print(f"Fault {i}: {fault.error_message} "
              f"(Penalty: -{fault.penalty_weight}) | Tick: {fault.tick_coordinate}")
    print("\n")


def test_typewriter_snap():
    print("=== TESTING ROMAN NUMERAL ANALYZER ===")
    analyzer = RomanNumeralAnalyzer()
    c_major = KeySignature(root_pitch=60)

    # Chord 1: G Major (Root position V chord)
    chord_1 = VerticalSlice(
        soprano=NoteNode(pitch=71, tick_length=480),  # B4
        alto=NoteNode(pitch=67, tick_length=480),     # G4
        tenor=NoteNode(pitch=62, tick_length=480),    # D4
        bass=NoteNode(pitch=43, tick_length=480)      # G2
    )

    snap_1 = analyzer.trigger_snap_analysis(chord_1, c_major)
    print(f"Chord 1 (G, D, G, B) analyzed as: {snap_1}")

    # Chord 2: C Major in First Inversion (I6)
    chord_2 = VerticalSlice(
        soprano=NoteNode(pitch=72, tick_length=480),  # C5
        alto=NoteNode(pitch=67, tick_length=480),     # G4
        tenor=NoteNode(pitch=60, tick_length=480),    # C4
        bass=NoteNode(pitch=52, tick_length=480)      # E3
    )

    snap_2 = analyzer.trigger_snap_analysis(chord_2, c_major)
    print(f"Chord 2 (E, C, G, C) analyzed as: {snap_2}\n")


if __name__ == "__main__":
    test_submission_workflow()
    test_typewriter_snap()