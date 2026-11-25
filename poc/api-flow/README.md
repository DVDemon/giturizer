# P0 PoC: Tree-sitter для API-потоков

Не production-код. Проверяет:

- парсинг C++, Java, TypeScript, Python;
- imports/includes, классы, функции;
- route/handler для Spring, NestJS, FastAPI;
- вызовы и URL-литералы кандидатов во внешние API.

Запуск:

```bash
pip install -r requirements.txt
python syntax_index.py fixtures > syntax-index.json
python verify.py
```

Doxygen-сравнение — в [docs/plan/api-flow-poc.md](../../docs/plan/api-flow-poc.md).
