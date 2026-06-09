```markdown
# testing Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `testing` Python repository. It covers file naming, import/export styles, commit message practices, and outlines how to structure and run tests. While no specific framework or automated workflows are detected, this guide ensures consistency and clarity for contributors.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `my_module.py`, `data_processor.py`

### Import Style
- Use **relative imports** within the codebase.
  - Example:
    ```python
    from .utils import helper_function
    ```

### Export Style
- Use **named exports** by explicitly listing public objects in `__all__`.
  - Example:
    ```python
    __all__ = ['MyClass', 'my_function']
    ```

### Commit Message Patterns
- Messages are freeform, with no strict prefixing.
- Average commit message length: ~31 characters.
  - Example:  
    ```
    Fix bug in data processing logic
    ```

## Workflows

### Setting Up a New Python Module
**Trigger:** When adding a new feature or utility.
**Command:** `/new-module`

1. Create a new file using snake_case (e.g., `feature_extractor.py`).
2. Use relative imports for internal dependencies.
3. Define `__all__` for named exports.
4. Add your implementation.

### Writing and Running Tests
**Trigger:** When verifying code correctness.
**Command:** `/run-tests`

1. Create test files with the pattern `*.test.ts` (note: TypeScript test pattern detected, but codebase is Python; consider aligning test file extensions).
2. Write test cases using your preferred testing approach (framework not detected).
3. Run tests manually or with your chosen test runner.

## Testing Patterns

- **Test File Naming:** Use the pattern `*.test.ts` for test files.
  - Example: `my_module.test.ts`
- **Testing Framework:** Not detected; use your preferred Python testing framework (e.g., `unittest`, `pytest`).
- **Test Structure:** Organize tests in dedicated files, mirroring the modules they test.

## Commands
| Command       | Purpose                                  |
|---------------|------------------------------------------|
| /new-module   | Scaffold a new Python module             |
| /run-tests    | Run all test files in the repository     |
```
