use std::io::{BufReader, BufRead};
use std::fs::File;
use std::sync::Arc;
use rustc_hash::{FxHashMap as HashMap};

use base64::{Engine, engine::general_purpose::STANDARD};

use crate::number::Number;

pub struct Vocabulary<T> {
    token_to_id: HashMap<Arc<str>, T>,
    id_to_token: HashMap<T, Arc<str>>,
    idx_to_id: HashMap<usize, T>,
    tokens: Vec<Arc<str>>,
    ids: Vec<T>,
    eos_id: T,
}

impl<T> Vocabulary<T> where T: Number {
    fn _process_lines<I>(vocabulary: &mut Self, lines: I) -> Option<()>
    where
        I: Iterator<Item = Result<String, std::io::Error>>,
    {
        for line in lines {
            let line = line.ok()?;
            let parts: Vec<&str> = line.split_whitespace().collect();

            if parts.len() != 2 {
                continue;
            }

            let (token, id) = (parts[0], parts[1]);

            let Ok(token) = STANDARD.decode(token) else { continue };
            let Ok(token) = String::from_utf8(token) else { continue };
            let Ok(id) = id.parse::<usize>() else { continue };

            let id = T::from_usize(id);

            if id == vocabulary.eos_id {
                continue;
            }

            let token: Arc<str> = Arc::from(token);
            let idx = vocabulary.tokens.len();

            vocabulary.token_to_id.insert(token.clone(), id);
            vocabulary.id_to_token.insert(id, token.clone());
            vocabulary.idx_to_id.insert(idx, id);
            vocabulary.tokens.push(token);
            vocabulary.ids.push(id);
        }
        Some(())
    }

    pub fn from_file_path(file_path: &str, eos_id: T) -> Option<Self> {
        let file = File::open(file_path).ok()?;
        let reader = BufReader::new(file);
        
        let mut vocabulary = Self {
            token_to_id: HashMap::default(),
            id_to_token: HashMap::default(),
            idx_to_id: HashMap::default(),
            tokens: Vec::new(),
            ids: Vec::new(),
            eos_id: eos_id,
        };

        Self::_process_lines(&mut vocabulary, reader.lines())?;

        Some(vocabulary)
    }

    // EOS = 1 for pre-trained Gemma 3 model
    // EOS = 106 for instruction-tuned Gemma 3 model
    pub fn new(data: &[u8], eos_id: T) -> Option<Self> {
        let mut vocabulary = Self {
            token_to_id: HashMap::default(),
            id_to_token: HashMap::default(),
            idx_to_id: HashMap::default(),
            tokens: Vec::new(),
            ids: Vec::new(),
            eos_id: eos_id,
        };

        let text = std::str::from_utf8(data).ok()?;
        let lines_iter = text.lines().map(|s| Ok(s.to_string()));

        Self::_process_lines(&mut vocabulary, lines_iter)?;

        Some(vocabulary)
    }
    
    #[inline(always)]
    pub fn get_tokens(&self) -> &Vec<Arc<str>> {
        &self.tokens
    }

    #[inline(always)]
    pub fn get_eos_id(&self) -> T {
        self.eos_id
    }

    #[inline(always)]
    pub fn get_ids(&self) -> &Vec<T> {
        &self.ids
    }

    #[inline(always)]
    pub fn get_token_by_id(&self, id: T) -> Option<&str> {
        self.id_to_token.get(&id).map(|s| &**s)
    }

    #[inline(always)]
    pub fn get_token_by_idx(&self, idx: usize) -> Option<&str> {
        self.tokens.get(idx).map(|s| &**s)
    }

    #[inline(always)]
    pub fn get_id_by_idx(&self, idx: usize) -> Option<T> {
        let token = self.idx_to_id.get(&idx);

        let Some(id) = token else {
            return None;
        };

        Some(id.clone())
    }

    #[inline(always)]
    pub fn get_id_by_token(&self, token: &str) -> Option<T> {
        let token = self.token_to_id.get(token);

        let Some(token) = token else {
            return None;
        };

        Some(token.clone())
    }
}