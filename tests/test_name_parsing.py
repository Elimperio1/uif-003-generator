from uif.parse_employees import extract_first_name, extract_surname


def test_first_name_single_token():
    assert extract_first_name("Sibonile") == "Sibonile"


def test_first_name_multi_token_takes_leading():
    assert extract_first_name("Maxwell Zuze") == "Maxwell"
    assert extract_first_name("Peter John") == "Peter"
    assert extract_first_name("Babini Melbo") == "Babini"


def test_first_name_truncated_still_works():
    # Sage sometimes truncates the field; leading token should still be intact
    assert extract_first_name("Bongiwe Vict") == "Bongiwe"


def test_first_name_handles_blank():
    assert extract_first_name("") == ""
    assert extract_first_name("   ") == ""


def test_surname_simple():
    assert extract_surname("S Anthorn") == "Anthorn"
    assert extract_surname("M Mwenyedawa") == "Mwenyedawa"


def test_surname_strips_title_prefix():
    # The bug we're fixing — "Mt" is a title, must not end up in the surname
    assert extract_surname("Mt N Langeni") == "Langeni"


def test_surname_compound_van():
    assert extract_surname("P van Wyk") == "van Wyk"


def test_surname_compound_du():
    assert extract_surname("J du Plessis") == "du Plessis"


def test_surname_compound_le():
    assert extract_surname("A le Roux") == "le Roux"


def test_surname_compound_van_der():
    assert extract_surname("M van der Merwe") == "van der Merwe"


def test_surname_compound_van_den():
    assert extract_surname("R van den Berg") == "van den Berg"


def test_surname_particle_case_insensitive():
    # Particles should be detected regardless of how they're capitalised
    assert extract_surname("P Van Wyk") == "Van Wyk"
    assert extract_surname("J DU Plessis") == "DU Plessis"


def test_surname_handles_blank():
    assert extract_surname("") == ""
    assert extract_surname("   ") == ""
