# Fixtures directory

Place Django fixture JSON files here to load them with:

```bash
python manage.py loaddata <filename_without_.json>
```

Example: put `initial_questions.json` here, then run:

```bash
python manage.py loaddata initial_questions
```

You can also run `loaddata` with a full path to a JSON file anywhere on disk.
