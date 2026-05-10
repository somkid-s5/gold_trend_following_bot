# Contributing to TITAN Berserker

## Development Environment
1. Clone the repository.
2. Install Python dependencies: `pip install -r requirements.txt`.
3. Install Frontend dependencies: `cd frontend && npm install`.
4. Create a `.env` file from `.env.example`.

## Coding Standards
- **Python**: Follow PEP 8. Use type hints for all function signatures.
- **Frontend**: Use TypeScript and React 19+. Follow the existing component structure.
- **Git**: Use meaningful commit messages following the [Conventional Commits](https://www.conventionalcommits.org/) format.

## Adding a New Strategy
1. Create a new class in `src/strategies/` implementing the `Strategy` protocol.
2. Register the strategy in `main.py` and `api/bot_manager.py`.

## Testing
- Run linting before submitting changes: `cd frontend && npm run lint`.
- Verify the build: `cd frontend && npm run build`.
- Perform a backtest to ensure no regressions in trading logic.
