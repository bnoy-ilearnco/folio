use rusqlite::{params, Connection, OpenFlags};
use serde::Serialize;
use std::{collections::BTreeMap, path::PathBuf};
use tauri::Manager;
use unicode_normalization::{char::is_combining_mark, UnicodeNormalization};

#[derive(Serialize)]
pub struct Book {
    id: i64,
    title: String,
    he_title: String,
    collection: String,
    category: String,
    base_title: Option<String>,
    version: String,
    license: String,
    source_url: String,
    segments: i64,
}
#[derive(Serialize)]
pub struct Catalog {
    books: Vec<Book>,
    metadata: BTreeMap<String, String>,
}
#[derive(Serialize)]
pub struct Passage {
    id: i64,
    ref_: String,
    text: String,
    base_ref: Option<String>,
}
#[derive(Serialize)]
pub struct Reading {
    passages: Vec<Passage>,
    commentary: Vec<Passage>,
    commentary_book: Option<Book>,
}
#[derive(Serialize)]
pub struct SearchHit {
    id: i64,
    book_id: i64,
    title: String,
    section: String,
    ref_: String,
    text: String,
}

fn database(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .resource_dir()
        .map(|p| p.join("resources/library.sqlite"))
        .map_err(|e| e.to_string())
}
fn open(path: &PathBuf) -> Result<Connection, String> {
    Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| format!("Cannot open offline library: {e}"))
}
const BOOK_COLUMNS: &str =
    "id,title,he_title,collection,category,base_title,version,license,source_url,segments";
fn book(row: &rusqlite::Row<'_>) -> rusqlite::Result<Book> {
    Ok(Book {
        id: row.get(0)?,
        title: row.get(1)?,
        he_title: row.get(2)?,
        collection: row.get(3)?,
        category: row.get(4)?,
        base_title: row.get(5)?,
        version: row.get(6)?,
        license: row.get(7)?,
        source_url: row.get(8)?,
        segments: row.get(9)?,
    })
}
fn passages(db: &Connection, book_id: i64, section: &str) -> Result<Vec<Passage>, String> {
    let mut stmt=db.prepare("SELECT id,ref,text,base_ref FROM passages WHERE book_id=?1 AND section=?2 ORDER BY ordinal LIMIT 3000").map_err(|e|e.to_string())?;
    let rows = stmt
        .query_map(params![book_id, section], |r| {
            Ok(Passage {
                id: r.get(0)?,
                ref_: r.get(1)?,
                text: r.get(2)?,
                base_ref: r.get(3)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn library_catalog(app: tauri::AppHandle) -> Result<Catalog, String> {
    let path = database(&app)?;
    tauri::async_runtime::spawn_blocking(move || {
        let db = open(&path)?;
        let mut stmt = db
            .prepare(&format!(
                "SELECT {BOOK_COLUMNS} FROM books ORDER BY sort_order,base_title IS NOT NULL,id"
            ))
            .map_err(|e| e.to_string())?;
        let books = stmt
            .query_map([], book)
            .map_err(|e| e.to_string())?
            .collect::<rusqlite::Result<Vec<_>>>()
            .map_err(|e| e.to_string())?;
        let mut stmt = db
            .prepare("SELECT key,value FROM metadata")
            .map_err(|e| e.to_string())?;
        let metadata = stmt
            .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))
            .map_err(|e| e.to_string())?
            .collect::<rusqlite::Result<BTreeMap<_, _>>>()
            .map_err(|e| e.to_string())?;
        Ok(Catalog { books, metadata })
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn library_sections(app: tauri::AppHandle, book_id: i64) -> Result<Vec<String>, String> {
    let path = database(&app)?;
    tauri::async_runtime::spawn_blocking(move || {
        let db=open(&path)?;
        let mut stmt=db.prepare("SELECT section FROM passages WHERE book_id=?1 GROUP BY section ORDER BY min(ordinal)").map_err(|e|e.to_string())?;
        let rows=stmt.query_map([book_id],|r|r.get(0)).map_err(|e|e.to_string())?;
        rows.collect::<rusqlite::Result<Vec<_>>>().map_err(|e|e.to_string())
    }).await.map_err(|e|e.to_string())?
}

#[tauri::command]
pub async fn library_read(
    app: tauri::AppHandle,
    book_id: i64,
    section: String,
) -> Result<Reading, String> {
    if section.len() > 80 {
        return Err("Invalid section".into());
    }
    let path = database(&app)?;
    tauri::async_runtime::spawn_blocking(move || {
        let db=open(&path)?;
        let commentary_book=db.query_row(&format!("SELECT {BOOK_COLUMNS} FROM books WHERE base_title=(SELECT title FROM books WHERE id=?1)"),[book_id],book).optional().map_err(|e|e.to_string())?;
        let commentary=if let Some(ref b)=commentary_book{passages(&db,b.id,&section)?}else{vec![]};
        Ok(Reading{passages:passages(&db,book_id,&section)?,commentary,commentary_book})
    }).await.map_err(|e|e.to_string())?
}

use rusqlite::OptionalExtension;
fn normalized(text: &str) -> String {
    text.nfd()
        .filter(|c| !is_combining_mark(*c))
        .map(|c| match c {
            'ך' => 'כ',
            'ם' => 'מ',
            'ן' => 'נ',
            'ף' => 'פ',
            'ץ' => 'צ',
            c if c.is_alphanumeric() || c.is_whitespace() => c,
            _ => ' ',
        })
        .collect::<String>()
        .to_lowercase()
}
fn search(
    db: &Connection,
    query: &str,
    collection: &str,
    book_id: Option<i64>,
    offset: i64,
) -> Result<Vec<SearchHit>, String> {
    let normalized = normalized(query);
    let terms: Vec<_> = normalized
        .split_whitespace()
        .take(12)
        .map(|s| format!("\"{s}\"*"))
        .collect();
    if terms.is_empty() {
        return Ok(vec![]);
    }
    let expression = terms.join(" AND ");
    let mut stmt=db.prepare("SELECT p.id,b.id,b.title,p.section,p.ref,p.text FROM passage_search JOIN passages p ON p.id=passage_search.rowid JOIN books b ON b.id=p.book_id WHERE passage_search MATCH ?1 AND (?2='' OR b.collection=?2) AND (?3 IS NULL OR b.id=?3) ORDER BY b.sort_order,b.id,p.ordinal LIMIT 51 OFFSET ?4").map_err(|e|e.to_string())?;
    let rows = stmt
        .query_map(params![expression, collection, book_id, offset], |r| {
            Ok(SearchHit {
                id: r.get(0)?,
                book_id: r.get(1)?,
                title: r.get(2)?,
                section: r.get(3)?,
                ref_: r.get(4)?,
                text: r.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub async fn library_search(
    app: tauri::AppHandle,
    query: String,
    collection: String,
    book_id: Option<i64>,
    offset: i64,
) -> Result<Vec<SearchHit>, String> {
    if query.len() > 500
        || !(0..=100_000).contains(&offset)
        || !["", "Tanakh", "Bavli"].contains(&collection.as_str())
    {
        return Err("Invalid library search".into());
    }
    let path = database(&app)?;
    tauri::async_runtime::spawn_blocking(move || {
        search(&open(&path)?, &query, &collection, book_id, offset)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    fn db() -> Connection {
        open(&PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("resources/library.sqlite")).unwrap()
    }
    #[test]
    fn corpus_integrity_and_coverage() {
        let db = db();
        let count: i64 = db
            .query_row(
                "SELECT count(*) FROM books WHERE collection='Tanakh' AND base_title IS NULL",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 39);
        let count: i64 = db
            .query_row(
                "SELECT count(*) FROM books WHERE collection='Bavli' AND base_title IS NULL",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 37);
        let count: i64 = db
            .query_row(
                "SELECT count(*) FROM books WHERE collection NOT IN ('Tanakh','Bavli')",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 0);
        let count: i64 = db
            .query_row(
                "SELECT count(*) FROM books WHERE base_title IS NOT NULL AND collection='Tanakh'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 39);
        let mismatch:i64=db.query_row("SELECT count(*) FROM books b WHERE b.segments!=(SELECT count(*) FROM passages p WHERE p.book_id=b.id)",[],|r|r.get(0)).unwrap();
        assert_eq!(mismatch, 0);
        let integrity: String = db
            .query_row("PRAGMA integrity_check", [], |r| r.get(0))
            .unwrap();
        assert_eq!(integrity, "ok");
    }
    #[test]
    fn hebrew_search_and_commentary_links() {
        let db = db();
        let hits = search(&db, "בְּרֵאשִׁית ברא", "Tanakh", Some(1), 0).unwrap();
        assert!(!hits.is_empty());
        assert_eq!(hits[0].ref_, "1:1");
        assert_eq!(normalized("מֶלֶךְ"), normalized("מלכ"));
        assert!(search(&db, "\" OR *", "", None, 0).is_ok());
        let rashi_id: i64 = db
            .query_row(
                "SELECT id FROM books WHERE title='Rashi on Genesis'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        let comments = passages(&db, rashi_id, "1").unwrap();
        assert!(comments
            .iter()
            .any(|p| p.base_ref.as_deref() == Some("1:1")));
    }
}
