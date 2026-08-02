from app.core.derived_houses import compute_derived_houses


def test_reference_house_7_maps_house_8_to_partners_house_1():
    result = compute_derived_houses(planets=[])
    ref7 = next(r for r in result if r["reference_house"] == 7)
    entry = next(m for m in ref7["mapping"] if m["represents_house"] == 1)
    assert entry["derived_house_number"] == 8


def test_reference_house_itself_represents_the_persons_twelfth_house():
    result = compute_derived_houses(planets=[])
    ref7 = next(r for r in result if r["reference_house"] == 7)
    entry = next(m for m in ref7["mapping"] if m["derived_house_number"] == 7)
    assert entry["represents_house"] == 12


def test_reference_house_1_still_starts_counting_at_the_next_house():
    # La convention "N+1 -> 1, N+2 -> 2, ..." s'applique aussi pour R=1 (pas de cas
    # particulier identité) : maison 2 = "sa" maison 1, ..., maison 1 elle-même = "sa" maison 12.
    result = compute_derived_houses(planets=[])
    ref1 = next(r for r in result if r["reference_house"] == 1)
    entry_house2 = next(m for m in ref1["mapping"] if m["derived_house_number"] == 2)
    assert entry_house2["represents_house"] == 1
    entry_house1 = next(m for m in ref1["mapping"] if m["derived_house_number"] == 1)
    assert entry_house1["represents_house"] == 12


def test_all_twelve_reference_houses_present_with_full_mapping():
    result = compute_derived_houses(planets=[])
    assert len(result) == 12
    for ref in result:
        assert len(ref["mapping"]) == 12
        assert {m["represents_house"] for m in ref["mapping"]} == set(range(1, 13))
        assert {m["derived_house_number"] for m in ref["mapping"]} == set(range(1, 13))


def test_planets_are_attached_to_correct_natal_house():
    planets = [{"name": "Sun", "house": 8}, {"name": "Moon", "house": 8}, {"name": "Mars", "house": 3}]
    result = compute_derived_houses(planets)
    ref7 = next(r for r in result if r["reference_house"] == 7)
    house8_entry = next(m for m in ref7["mapping"] if m["derived_house_number"] == 8)
    assert set(house8_entry["planets"]) == {"Sun", "Moon"}
