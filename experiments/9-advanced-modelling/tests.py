from fields import Fields
from tables import Tables

schema = {
    "i": ["ki", "q", "kie", "fi"],
    "j": ["ji", "q", "fj"],
    "k": ["kk", "q", "fk"],
    "a": ["kab", "q", "fa"],
    "b": ["kab", "kbc", "fb"],
    "c": ["kbc", "kcd", "fc"],
    "d": ["kcd", "kde", "fd"],
    "e": ["kde", "kie", "fe"],
}

def case1():
    fields = Fields(schema)

    fields.use_field("", "fa")

    assert fields.selected == ["fa"]
    assert fields.get_excluded_fields() == set()
    assert fields.get_required_tables() == {"a"}

    fields.use_field("", "kbc")

    assert fields.selected == ["fa", "kbc"]
    assert fields.get_excluded_fields() == set()
    assert fields.get_required_tables() == {"a", "b", "c"}

    fields.use_field("", "fb")

    assert fields.selected == ["fa", "kbc", "fb"]
    assert fields.get_excluded_fields() == {"fc", "kab"}
    assert fields.get_required_tables() == {"a", "b"}

    fields.use_field("", "kde")

    assert fields.selected == ["fa", "kbc", "fb", "kde"]
    assert fields.get_excluded_fields() == {"fc", "kab"}
    assert fields.get_required_tables() == {"a", "b", "d", "e"}

    fields.use_field("x", "kcd")

    assert fields.selected == ["fa", "kbc", "fb", "kde", "x.kcd"]
    assert fields.get_excluded_fields() == {'fc', 'kab'}
    assert fields.get_excluded_fields("x") == fields.get_all_fields() - set(schema["c"]) - set(schema["d"])

    tables = Tables(fields)

    assert tables.get_required_tables() == {'a', 'd', 'e', 'b', 'd x', 'c x'}

    tables.use_table('a')

    assert tables.get_joinable_neighbors() == {'j', 'b', 'k', 'i'}

    tables.join_table('b')

    assert tables.get_joinable_neighbors() == {'j', 'k', 'i', 'c x'}

    tables.join_table('c x')

    assert tables.get_joinable_neighbors() == {'j', 'd', 'k', 'i'}
    assert tables.get_required_tables() == {'e', 'd'}

    tables.use_table('e')

    assert tables.get_joinable_neighbors() == {'i'}
    assert tables.get_required_tables() == set()

    tables.join_table('i')
    
    assert tables.get_joinable_neighbors() == {'j', 'a', 'k'}
    assert tables.get_required_tables() == set()
    assert fields.is_satisfied() is True
    assert tables.selected == ['a JOIN b JOIN c x', 'e JOIN i']

if __name__ == "__main__":
    case1()
