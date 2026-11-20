from hitl.rules import check, ids, numbers


def names(found):
    return {f.check for f in found}


def test_a_clean_rewrite_passes():
    assert check("repl brg on cnvyr CV-3, still noisy, chk tmrw",
                 "Replaced the bearing on conveyor CV-3. It is still noisy; will check tomorrow.") == []


def test_numbers_are_normalized_before_comparing():
    assert numbers("added two qts, 3.0 mm/s, 1,200 cycles") == ["1200", "2", "3"]
    assert numbers("CV-3 and WO4105 are tags, not numbers") == []


def test_added_dropped_and_changed_numbers_are_blocked():
    assert names(check("repl brg on CV-3", "Replaced 2 bearings on CV-3.")) == {"numbers"}
    assert names(check("added 2 qts oil GB-12", "Added oil to gearbox GB-12.")) == {"numbers"}
    found = check("pressure 45 psi on P-101", "Pressure on P-101 was 54 psi.")
    assert [f.detail for f in found] == ["added 54", "dropped 45"]


def test_asset_tags_must_survive_with_or_without_the_dash():
    assert ids("CV-1 thru CV4, WO4410") == {"CV1", "CV4", "WO4410"}
    assert check("lube brgs CV1-CV4", "Lubricated the bearings on CV-1 through CV-4.") == []
    assert names(check("repl seal on PU-3", "Replaced the seal on PU-8.")) == {"ids"}


def test_placeholders_must_be_kept_exactly():
    assert names(check("call [PHONE_1] re parts", "Call the customer about parts.")) == {"placeholders"}


def test_stronger_claims_are_blocked_unless_the_note_made_them():
    assert names(check("repl brg CV-3, still noisy", "Replaced the bearing on CV-3; fully resolved.")) == {"assurance"}
    assert check("root cause unknown, PLC flt", "Root cause unknown; PLC fault.") == []


def test_model_chatter_is_blocked():
    assert "format" in names(check("repl brg CV-3", "Here is the rewritten note: Replaced the bearing on CV-3."))


def test_length_limits_but_short_notes_may_shrink():
    assert names(check("repl brg CV-3", "Replaced the bearing on CV-3 " + " ".join(["and more"] * 10))) == {"length"}
    long_note = "hyd lk at P-101 fitting, tightened it, cleaned up oil on the floor, will monitor next shift"
    assert names(check(long_note, "Fixed P-101 leak.")) == {"length"}
    assert check("chkd guard CV-2 ok", "Checked CV-2 guard: OK.") == []


def test_empty_suggestion():
    assert names(check("repl brg CV-3", "  ")) == {"empty"}
