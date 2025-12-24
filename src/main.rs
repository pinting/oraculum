use std::{collections::HashMap, rc::Rc};
use base64::{Engine, engine::general_purpose::STANDARD};

pub struct Vocabulary {
    token_to_id: HashMap<String, u32>,
    id_to_token: HashMap<u32, String>,
}

impl Vocabulary {
    pub fn new() -> Self {
        Self {
            token_to_id: HashMap::new(),
            id_to_token: HashMap::new(),
        }
    }

    pub fn load(&mut self, data: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
        let text = std::str::from_utf8(data)?;

        for line in text.lines() {
            let parts: Vec<&str> = line.split_whitespace().collect();
            
            if parts.len() != 2 {
                continue;
            }

            let (raw_token, raw_id) = (parts[0], parts[1]);

            let Ok(token_bytes) = STANDARD.decode(raw_token) else { continue };
            let Ok(token) = String::from_utf8(token_bytes) else { continue };
            let Ok(id) = raw_id.parse::<u32>() else { continue };
            
            self.token_to_id.insert(token.clone(), id);
            self.id_to_token.insert(id, token);
        }

        Ok(())
    }

    pub fn get_token(&self, id: u32) -> Option<String> {
        self.id_to_token.get(&id).cloned()
    }

    pub fn get_id(&self, token: &str) -> Option<u32> {
        self.token_to_id.get(token).copied()
    }
}

enum Route {
    Dead,
    Alive,
    End
}

enum Head {
    Constant(Constant),
}

trait Node {
    fn routes(&self) -> Vec<u8>;
    fn step(&self, token_id: u8) -> Option<Route>;
    fn next(&self) -> Vec<Head>;
}

impl Node for Head {
    fn routes(&self) -> Vec<u8> {
        match self {
            Head::Constant(n) => n.routes(),
        }
    }

    fn step(&self, token_id: u8) -> Option<Route> {
        match self {
            Head::Constant(n) => n.step(token_id),
        }
    }

    fn next(&self) -> Vec<Head> {
        match self {
            Head::Constant(n) => n.next(),
        }
    }
}

struct Constant {
    constant: String,
    vocabulary: Rc<Vocabulary>,
}

impl Constant {
    fn new(vocabulary: Rc<Vocabulary>, constant: String) -> Self {
        Constant { vocabulary, constant }
    }
}

impl Node for Constant {
    fn routes(&self) -> Vec<u8> {
        todo!()
    }

    fn step(&self, token_id: u8) -> Option<Route> {
        todo!()
    }

    fn next(&self) -> Vec<Head> {
        todo!()
    }
}

struct Thunk<F>
where
    F: FnOnce(Rc<Vocabulary>) -> Vec<Head>,
{
    generator: Option<F>,
}

impl<F> Thunk<F>
where
    F: FnOnce(Rc<Vocabulary>) -> Vec<Head>,
{
    fn new(generator: F) -> Self {
        Thunk { generator: Some(generator) }
    }

    fn execute(&mut self, vocabulary: Rc<Vocabulary>) -> Vec<Head> {
        self.generator.take().unwrap()(vocabulary)
    }
}

fn main() {
    let vocabulary = Rc::new(Vocabulary::new());

    let mut thunk = Thunk::new(|vocabulary| {
        vec![
            Head::Constant(Constant::new(vocabulary, "hello".to_string())),
        ]
    });

    let nodes = thunk.execute(vocabulary);

    for node in &nodes {
        continue
    }
}