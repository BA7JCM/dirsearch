# Python API

dirsearch can be used from Python code for local automation, MCP servers, REST wrappers, or other integrations.

```python
from dirsearch import DirsearchFuzzer, FuzzerConfig, WordlistTemplate

template = WordlistTemplate(
    ["%SUBJECT%.%EXT%"],
    placeholders={"SUBJECT": ["admin", "login"]},
)
config = FuzzerConfig(
    url="https://example.com",
    wordlist=template,
    extensions=("php",),
)

results = DirsearchFuzzer(config).run()
```

The importable API keeps its configuration in `FuzzerConfig`; callers do not need to mutate CLI globals.
