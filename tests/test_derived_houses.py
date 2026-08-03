from app.core.derived_houses import compute_derived_houses, derive_house


def test_derive_house_reference_house_itself_is_the_persons_first_house():
    # La maison de référence ELLE-MÊME devient la maison 1 (identité) de la personne
    # représentée — pas de décalage d'un cran.
    assert derive_house(7, 1) == 7
    assert derive_house(4, 1) == 4


def test_derive_house_partner_example_from_spec():
    # maisons_derivees_extension.md section 1 : M7=partenaire, M8=sa maison 2 (pas M9).
    assert derive_house(7, 1) == 7
    assert derive_house(7, 2) == 8
    assert derive_house(7, 3) == 9
    assert derive_house(7, 12) == 6


def test_derive_house_wraps_around_modulo_12():
    assert derive_house(10, 5) == 2
    assert derive_house(1, 12) == 12
    assert derive_house(12, 2) == 1


def test_reference_house_7_maps_house_7_to_partners_house_1():
    result = compute_derived_houses(planets=[])
    ref7 = next(r for r in result if r["reference_house"] == 7)
    entry = next(m for m in ref7["mapping"] if m["represents_house"] == 1)
    assert entry["derived_house_number"] == 7


def test_reference_house_8_represents_partners_second_house():
    result = compute_derived_houses(planets=[])
    ref7 = next(r for r in result if r["reference_house"] == 7)
    entry = next(m for m in ref7["mapping"] if m["derived_house_number"] == 8)
    assert entry["represents_house"] == 2


def test_reference_house_4_maps_house_4_to_mothers_house_1():
    result = compute_derived_houses(planets=[])
    ref4 = next(r for r in result if r["reference_house"] == 4)
    entry = next(m for m in ref4["mapping"] if m["represents_house"] == 1)
    assert entry["derived_house_number"] == 4


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


def test_second_order_derivation_is_a_chained_call_belle_famille():
    # Belle-mère/beau-père (parents du partenaire) = derive(7, 4) = maison 10.
    assert derive_house(7, 4) == 10


def test_second_order_derivation_grand_mere_maternelle():
    assert derive_house(4, 4) == 7


def test_second_order_derivation_neveux_nieces():
    assert derive_house(3, 5) == 7


def test_second_order_derivation_petits_enfants():
    assert derive_house(5, 5) == 9
