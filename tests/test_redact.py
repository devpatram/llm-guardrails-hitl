from hitl.redact import redact, restore


def test_contacts_are_replaced_and_restored():
    note = "call Sam at 555-201-4477 or sam.lee@example.com, or (555) 201 4477 again"
    sent, found = redact(note)
    assert "555" not in sent and "@" not in sent
    assert sent == "call Sam at [PHONE_1] or [EMAIL_1], or [PHONE_2] again"
    assert restore(sent, found) == note


def test_the_same_value_gets_the_same_placeholder():
    sent, found = redact("a@b.com then a@b.com")
    assert sent == "[EMAIL_1] then [EMAIL_1]" and len(found) == 1


def test_tags_and_readings_are_not_phone_numbers():
    sent, found = redact("WO4105 on CV-3 at 14:30, 1,200 cycles, 412F")
    assert found == {}
