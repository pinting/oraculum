#!/usr/bin/env python
from conflicts import Conflicts
from relationships import Relationships
from schema import Schema, Reference, parse_schema

def schema1() -> Schema:
    sql = """
        CREATE TABLE a (
            kab BIGINT PRIMARY KEY,
            q BIGINT,
            fa BIGINT
        );

        CREATE TABLE b (
            kbc BIGINT PRIMARY KEY,
            kab BIGINT REFERENCES a(kab),
            fb BIGINT
        );

        CREATE TABLE c (
            kcd BIGINT PRIMARY KEY,
            kbc BIGINT REFERENCES b(kbc),
            fc BIGINT
        );

        CREATE TABLE d (
            kde BIGINT PRIMARY KEY,
            kcd BIGINT REFERENCES c(kcd),
            fd BIGINT
        );

        CREATE TABLE e (
            kie BIGINT PRIMARY KEY,
            kde BIGINT REFERENCES d(kde),
            fe BIGINT
        );

        CREATE TABLE i (
            ki BIGINT PRIMARY KEY,
            q BIGINT REFERENCES a(q),
            kie BIGINT REFERENCES e(kie),
            fi BIGINT
        );

        CREATE TABLE j (
            kj BIGINT PRIMARY KEY,
            q BIGINT REFERENCES a(q),
            fj BIGINT
        );

        CREATE TABLE k (
            kk BIGINT PRIMARY KEY,
            q BIGINT REFERENCES a(q),
            fk BIGINT
        );
    """

    schema = parse_schema(sql)

    return schema

def case1():
    schema = schema1()
    conflicts = Conflicts(schema)

    conflicts.use_field("", "fa")

    assert conflicts.used_fields == ["fa"]
    assert conflicts.get_excluded_fields() == set()
    assert conflicts.get_required_tables() == {"a"}

    conflicts.use_field("", "kbc")

    assert conflicts.used_fields == ["fa", "kbc"]
    assert conflicts.get_excluded_fields() == set()
    assert conflicts.get_required_tables() == {"a", "b", "c"}

    conflicts.use_field("", "fb")

    assert conflicts.used_fields == ["fa", "kbc", "fb"]
    assert conflicts.get_excluded_fields() == {"fc", "kab"}
    assert conflicts.get_required_tables() == {"a", "b"}

    conflicts.use_field("", "kde")

    assert conflicts.used_fields == ["fa", "kbc", "fb", "kde"]
    assert conflicts.get_excluded_fields() == {"fc", "kab"}
    assert conflicts.get_required_tables() == {"a", "b", "d", "e"}

    conflicts.use_field("x", "kcd")

    assert conflicts.used_fields == ["fa", "kbc", "fb", "kde", "x.kcd"]
    assert conflicts.get_excluded_fields() == {'fc', 'kab'}
    
    c_fields = set(schema.tables["c"].fields.keys())
    d_fields = set(schema.tables["d"].fields.keys())
    assert conflicts.get_excluded_fields("x") == conflicts.get_all_fields() - c_fields - d_fields

    relationships = Relationships(conflicts, schema)

    assert relationships.get_required_tables() == {'a', 'd', 'e', 'b', 'd x', 'c x'}

    relationships.use_table('a')

    def join(t: str):
        for n in relationships.get_joinable_neighbors():
            if n.table == t:
                relationships.join_table(n)
                return
        raise Exception(f"Neighbor {t} not found")

    assert {n.table for n in relationships.get_joinable_neighbors()} == {'j', 'b', 'k', 'i'}

    join('b')

    assert {n.table for n in relationships.get_joinable_neighbors()} == {'j', 'k', 'i', 'c x'}

    join('c x')

    assert {n.table for n in relationships.get_joinable_neighbors()} == {'j', 'd', 'k', 'i'}
    assert relationships.get_required_tables() == {'e', 'd'}

    relationships.use_table('e')

    assert {n.table for n in relationships.get_joinable_neighbors()} == {'i'}
    assert relationships.get_required_tables() == set()

    join('i')
    
    assert {n.table for n in relationships.get_joinable_neighbors()} == set()
    assert relationships.get_required_tables() == set()
    assert conflicts.is_satisfied() is True
    
    assert "INNER JOIN b ON a.kab = b.kab" in relationships.used_references[0]
    assert "INNER JOIN c x ON b.kbc = c x.kbc" in relationships.used_references[0]
    assert relationships.used_references[0].startswith("a")
    assert relationships.used_references[1] == "e INNER JOIN i ON e.kie = i.kie"

def schema2() -> Schema:
    sql = """
        CREATE TABLE users (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            first_name VARCHAR(255) NOT NULL,
            last_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL
        );

        CREATE TABLE posts (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL
        );

        CREATE TABLE comments (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL
        );
    """
    
    schema = parse_schema(sql)

    return schema

def case2():
    schema = schema2()
    
    assert "users" in schema.tables

    users = schema.tables["users"]

    assert users.primary_key == "id"
    assert "email" in users.unique
    assert users.fields["id"].type.name == "BIGINT"
    assert users.fields["id"].is_primary_key is True
    assert users.fields["first_name"].type.name == "VARCHAR"
    assert users.fields["first_name"].type.length == 255
    assert users.fields["first_name"].is_nullable is False
    assert users.fields["email"].is_unique is True

    assert "posts" in schema.tables

    posts = schema.tables["posts"]

    assert posts.fields["user_id"].reference == Reference("users", "id")

    assert "comments" in schema.tables

    comments = schema.tables["comments"]

    assert comments.fields["user_id"].reference == Reference("users", "id")
    assert comments.fields["post_id"].reference == Reference("posts", "id")



def test_use_missing_field_root():
    conflicts = Conflicts(schema1())
    try:
        conflicts.use_field("", "nonexistent")
        assert False
    except Exception as e:
        assert "does not exist" in str(e)

def test_use_missing_field_scope():
    conflicts = Conflicts(schema1())
    try:
        conflicts.use_field("x", "nonexistent")
        assert False
    except Exception as e:
        assert "does not exist" in str(e)

def test_scope_no_intersection():
    conflicts = Conflicts(schema1())
    conflicts.use_field("x", "fa")
    try:
        conflicts.use_field("x", "fb")
        assert False
    except Exception as e:
        assert "No intersection" in str(e)

def test_root_contradiction_tables():
    schema = parse_schema("""
        CREATE TABLE t1 ( f1 BIGINT );
        CREATE TABLE t2 ( f1 BIGINT );
    """)
    conflicts = Conflicts(schema)
    conflicts.use_field("", "f1")
    conflicts.use_table("t1")
    try:
        conflicts.use_table("t2")
        assert False
    except Exception as e:
        assert "would collapse" in str(e)

def test_alias_propagation_success():
    schema = parse_schema("""
        CREATE TABLE a ( id BIGINT PRIMARY KEY, f_a BIGINT );
        CREATE TABLE b ( id BIGINT PRIMARY KEY, a_id BIGINT REFERENCES a(id), f_b BIGINT );
        CREATE TABLE c ( id BIGINT PRIMARY KEY, b_id BIGINT REFERENCES b(id), f_c BIGINT );
        CREATE TABLE d ( id BIGINT PRIMARY KEY, b_id BIGINT REFERENCES b(id), f_d BIGINT );
    """)
    conflicts = Conflicts(schema)
    conflicts.use_field("", "f_d")
    conflicts.use_field("x", "f_d")
    conflicts.use_table("d x")
    assert "d" not in conflicts.root.get_required_tables()

def test_alias_propagation_ignored():
    schema = parse_schema("""
        CREATE TABLE t1 ( f1 BIGINT );
        CREATE TABLE t2 ( f1 BIGINT );
    """)
    conflicts = Conflicts(schema)
    conflicts.use_field("", "f1")
    conflicts.use_table("t1")
    conflicts.use_field("x", "f1")
    conflicts.use_table("t2 x")
    assert "t2" in conflicts.get_excluded_tables()

def test_relationship_use_not_required():
    schema = parse_schema("""
        CREATE TABLE a ( id BIGINT PRIMARY KEY, f_a BIGINT );
    """)
    conflicts = Conflicts(schema)
    rels = Relationships(conflicts, schema)
    try:
        rels.use_table("a")
        assert False
    except Exception as e:
        assert "not required" in str(e)

def test_relationship_join_not_joinable():
    schema = parse_schema("""
        CREATE TABLE a ( id BIGINT PRIMARY KEY, f_a BIGINT );
        CREATE TABLE b ( id BIGINT PRIMARY KEY, a_id BIGINT REFERENCES a(id), f_b BIGINT );
        CREATE TABLE c ( id BIGINT PRIMARY KEY, b_id BIGINT REFERENCES b(id), f_c BIGINT );
    """)
    conflicts = Conflicts(schema)
    conflicts.use_field("", "f_a")
    conflicts.use_field("", "f_c")
    rels = Relationships(conflicts, schema)
    rels.use_table("a")
    try:
        from relationships import Neighbor
        rels.join_table(Neighbor("c", "a.id", "c.a_id"))
        assert False
    except Exception as e:
        assert "Cannot join node" in str(e)

def test_relationship_join_excluded():
    schema = parse_schema("""
        CREATE TABLE a ( id BIGINT PRIMARY KEY, f1 BIGINT );
        CREATE TABLE b ( id BIGINT PRIMARY KEY, a_id BIGINT REFERENCES a(id), f1 BIGINT );
    """)
    conflicts = Conflicts(schema)
    conflicts.use_field("", "f1")
    rels = Relationships(conflicts, schema)
    rels.use_table("a")
    neighbors = rels.get_joinable_neighbors()
    assert len(neighbors) == 0

def test_relationships_join_type_format():
    from relationships import Neighbor, JoinType
    n = Neighbor("b", "a.id", "b.a_id")
    assert n.format(JoinType.LEFT) == "LEFT JOIN b ON a.id = b.a_id"
    assert n.format(JoinType.FULL) == "FULL JOIN b ON a.id = b.a_id"

def test_relationship_undirected_orient():
    from relationships import EdgeLabel, FieldRef
    label = EdgeLabel(FieldRef("a", "a.id"), FieldRef("b", "b.a_id"))
    n1 = label.orient("a", "b")
    assert n1.table == "b"
    assert n1.src_field == "a.id"
    assert n1.dst_field == "b.a_id"
    n2 = label.orient("b", "a")
    assert n2.table == "a"
    assert n2.src_field == "b.a_id"
    assert n2.dst_field == "a.id"

if __name__ == "__main__":
    case1()
    case2()
    test_use_missing_field_root()
    test_use_missing_field_scope()
    test_scope_no_intersection()
    test_root_contradiction_tables()
    test_alias_propagation_success()
    test_alias_propagation_ignored()
    test_relationship_use_not_required()
    test_relationship_join_not_joinable()
    test_relationship_join_excluded()
    test_relationships_join_type_format()
    test_relationship_undirected_orient()
    print("All tests passed!")
