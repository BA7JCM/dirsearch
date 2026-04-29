use indexmap::IndexSet;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use rayon::prelude::*;
use reqwest::header::{HeaderMap, HeaderName, HeaderValue};
use std::fs;
use std::time::Instant;

#[pyclass]
struct NativeHttpResult {
    #[pyo3(get)]
    path: String,
    #[pyo3(get)]
    status: u16,
    #[pyo3(get)]
    length: usize,
    #[pyo3(get)]
    elapsed_ms: f64,
}

#[pyfunction]
#[pyo3(signature = (
    files,
    extensions,
    force_extensions=false,
    prefixes=Vec::new(),
    suffixes=Vec::new(),
    lowercase=false,
    uppercase=false,
    capitalization=false,
    max_size=None,
))]
fn generate_wordlist(
    files: Vec<String>,
    extensions: Vec<String>,
    force_extensions: bool,
    prefixes: Vec<String>,
    suffixes: Vec<String>,
    lowercase: bool,
    uppercase: bool,
    capitalization: bool,
    max_size: Option<usize>,
) -> PyResult<Vec<String>> {
    let file_lines: Vec<Vec<String>> = files
        .par_iter()
        .map(|path| read_lines(path))
        .collect::<Result<Vec<_>, _>>()?;

    let mut wordlist = IndexSet::new();
    for lines in file_lines {
        for raw_line in lines {
            let line = raw_line.trim_start_matches('/').to_string();
            for expanded in expand_ext(&line, &extensions) {
                if !is_valid(&expanded) {
                    continue;
                }

                add_entry(&mut wordlist, expanded.clone(), max_size)?;

                if force_extensions && !expanded.contains('.') && !expanded.ends_with('/') {
                    add_entry(&mut wordlist, format!("{expanded}/"), max_size)?;
                    for extension in &extensions {
                        add_entry(&mut wordlist, format!("{expanded}.{extension}"), max_size)?;
                    }
                }
            }
        }
    }

    if !prefixes.is_empty() || !suffixes.is_empty() {
        let mut altered = IndexSet::new();
        for path in &wordlist {
            for prefix in &prefixes {
                if !path.starts_with('/') && !path.starts_with(prefix) {
                    add_entry(&mut altered, format!("{prefix}{path}"), max_size)?;
                }
            }
            for suffix in &suffixes {
                if !path.ends_with('/') && !path.ends_with(suffix) && !path.contains('?') && !path.contains('#') {
                    add_entry(&mut altered, format!("{path}{suffix}"), max_size)?;
                }
            }
        }
        if !altered.is_empty() {
            wordlist = altered;
        }
    }

    let items = wordlist
        .into_iter()
        .map(|path| apply_case(path, lowercase, uppercase, capitalization))
        .collect();
    Ok(items)
}

#[pyfunction]
#[pyo3(signature = (
    base_url,
    paths,
    concurrency=25,
    timeout_secs=7.5,
    headers=Vec::new(),
))]
fn scan_http(
    py: Python<'_>,
    base_url: String,
    paths: Vec<String>,
    concurrency: usize,
    timeout_secs: f64,
    headers: Vec<(String, String)>,
) -> PyResult<Vec<NativeHttpResult>> {
    py.allow_threads(move || {
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .worker_threads(concurrency.clamp(1, 256))
            .build()
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;

        runtime.block_on(async move {
            let mut header_map = HeaderMap::new();
            for (name, value) in headers {
                let name = HeaderName::from_bytes(name.as_bytes())
                    .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
                let value = HeaderValue::from_str(&value)
                    .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
                header_map.insert(name, value);
            }

            let client = reqwest::Client::builder()
                .danger_accept_invalid_certs(true)
                .default_headers(header_map)
                .timeout(std::time::Duration::from_secs_f64(timeout_secs))
                .pool_max_idle_per_host(concurrency)
                .build()
                .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;

            let semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(concurrency.max(1)));
            let mut tasks = Vec::with_capacity(paths.len());

            for path in paths {
                let client = client.clone();
                let base_url = base_url.clone();
                let semaphore = semaphore.clone();
                tasks.push(tokio::spawn(async move {
                    let _permit = semaphore.acquire_owned().await.map_err(|error| error.to_string())?;
                    let url = format!("{base_url}{path}");
                    let start = Instant::now();
                    let response = client.get(url).send().await.map_err(|error| error.to_string())?;
                    let status = response.status().as_u16();
                    let body = response.bytes().await.map_err(|error| error.to_string())?;
                    Ok::<NativeHttpResult, String>(NativeHttpResult {
                        path,
                        status,
                        length: body.len(),
                        elapsed_ms: start.elapsed().as_secs_f64() * 1000.0,
                    })
                }));
            }

            let mut results = Vec::with_capacity(tasks.len());
            for task in tasks {
                let result = task
                    .await
                    .map_err(|error| PyRuntimeError::new_err(error.to_string()))?
                    .map_err(PyRuntimeError::new_err)?;
                results.push(result);
            }
            Ok(results)
        })
    })
}

fn read_lines(path: &str) -> PyResult<Vec<String>> {
    let content = fs::read_to_string(path).map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
    Ok(content.lines().map(str::to_string).collect())
}

fn expand_ext(line: &str, extensions: &[String]) -> Vec<String> {
    if !line.to_ascii_lowercase().contains("%ext%") {
        return vec![line.to_string()];
    }

    extensions
        .iter()
        .map(|extension| replace_case_insensitive(line, "%ext%", extension))
        .collect()
}

fn replace_case_insensitive(input: &str, needle: &str, replacement: &str) -> String {
    let lower_input = input.to_ascii_lowercase();
    let lower_needle = needle.to_ascii_lowercase();
    let mut output = String::with_capacity(input.len() + replacement.len());
    let mut start = 0;

    while let Some(pos) = lower_input[start..].find(&lower_needle) {
        let absolute = start + pos;
        output.push_str(&input[start..absolute]);
        output.push_str(replacement);
        start = absolute + needle.len();
    }
    output.push_str(&input[start..]);
    output
}

fn is_valid(path: &str) -> bool {
    !path.is_empty() && !path.starts_with('#')
}

fn add_entry(wordlist: &mut IndexSet<String>, path: String, max_size: Option<usize>) -> PyResult<()> {
    wordlist.insert(path);
    if let Some(limit) = max_size {
        if wordlist.len() > limit {
            return Err(PyRuntimeError::new_err(format!(
                "Generated wordlist exceeded --wordlist-max-size ({limit})"
            )));
        }
    }
    Ok(())
}

fn apply_case(path: String, lowercase: bool, uppercase: bool, capitalization: bool) -> String {
    if lowercase {
        path.to_lowercase()
    } else if uppercase {
        path.to_uppercase()
    } else if capitalization {
        let mut chars = path.chars();
        match chars.next() {
            Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
            None => path,
        }
    } else {
        path
    }
}

#[pymodule]
fn dirsearch_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(generate_wordlist, module)?)?;
    module.add_function(wrap_pyfunction!(scan_http, module)?)?;
    module.add_class::<NativeHttpResult>()?;
    Ok(())
}
