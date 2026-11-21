# Contributing to Vellum Research

Thank you for contributing to Vellum Research!

## Development Workflow

1. Fork the repository and create a feature branch from `main`.
2. Never commit `.env` files, API keys, or sensitive credentials.
3. Follow existing code conventions:
   - Backend: Python 3.12+, typed FastAPI/Pydantic schemas, `ruff check` clean, and Pytest coverage for new logic.
   - Frontend: TypeScript strict mode, accessible UI components, and Vitest tests for new views or interactions.
4. Run all checks before opening a Pull Request:
   ```bash
   cd backend && pytest -v && ruff check app tests
   cd frontend && npm test && npm run build
   ```

## Good First Issues

- Add new `BaseSearchProvider` adapters (e.g., Brave Search, DuckDuckGo, arXiv API).
- Improve extraction metadata parsers for academic PDFs or regional news formats.
- Add keyboard shortcuts to the Report Reader citation inspector.
