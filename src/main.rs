trait Node {
    fn render(&self);
}

struct Constant {
    value: String,
}

impl Constant {
    fn new(value: String) -> Self {
        Constant { value }
    }
}

impl Node for Constant {
    fn render(&self) {
        println!("Constant: {}", self.value);
    }
}

struct RegularExpression {
    pattern: String,
    case_sensitive: bool,
}

impl RegularExpression {
    fn new(pattern: String, case_sensitive: bool) -> Self {
        RegularExpression { pattern, case_sensitive }
    }
}

impl Node for RegularExpression {
    fn render(&self) {
        println!("Regex: {} (case: {})", self.pattern, self.case_sensitive);
    }
}

struct Space {
    count: i32,
}

impl Space {
    fn new(count: i32) -> Self {
        Space { count }
    }
}

impl Node for Space {
    fn render(&self) {
        println!("Space: {}", self.count);
    }
}

enum NodeType {
    Constant(Constant),
    RegularExpression(RegularExpression),
    Space(Space),
}

impl Node for NodeType {
    fn render(&self) {
        match self {
            NodeType::Constant(n) => n.render(),
            NodeType::RegularExpression(n) => n.render(),
            NodeType::Space(n) => n.render(),
        }
    }
}

struct Thunk<F>
where
    F: FnOnce() -> Vec<NodeType>,
{
    generator: Option<F>,
}

impl<F> Thunk<F>
where
    F: FnOnce() -> Vec<NodeType>,
{
    fn new(generator: F) -> Self {
        Thunk { generator: Some(generator) }
    }

    fn execute(&mut self) -> Vec<NodeType> {
        self.generator.take().unwrap()()
    }
}

fn main() {
    let mut thunk = Thunk::new(|| {
        vec![
            NodeType::Constant(Constant::new("hello".to_string())),
            NodeType::RegularExpression(RegularExpression::new("[a-z]+".to_string(), true)),
            NodeType::Space(Space::new(5)),
        ]
    });

    let nodes = thunk.execute();
    for node in &nodes {
        node.render();
    }
}