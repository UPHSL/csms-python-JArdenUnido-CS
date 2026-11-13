[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=24315713&assignment_repo_type=AssignmentRepo)
Community Services Management System

Python and Flask implementation of the Community Services Management System
for the UPHSL Programming Languages Laboratory.

## Current Scope

The starter repository contains:

- A Flask application factory
- A Sprint 0 welcome page
- A health-check endpoint
- A professional `src` layout
- Initial automated tests
- Architectural placeholders for future sprint work

The starter does not yet contain resident management, persistence, authentication,
or other future features.

## Technology Stack

- Python 3.13 or newer
- Flask 3.1
- pytest
- pip
- `pyproject.toml`

## Sprint 0 Setup

### 1. Clone your assigned repository

```bash
git clone <your-assigned-repository-url>
cd <your-assigned-repository>
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

### 3. Activate the environment

#### macOS or Linux

```bash
source .venv/bin/activate
```

#### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

#### Windows Command Prompt

```cmd
.venv\Scripts\activate.bat
```

### 4. Install the project

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 5. Run the application

```bash
flask --app csms run --debug
```

Open:

```text
http://127.0.0.1:5000
```

You may also run:

```bash
python -m csms.main
```

### 6. Run the automated tests

```bash
pytest
```

Expected result:

```text
3 passed
```

### 7. Complete the developer profile

Update:

```text
ABOUT_THE_DEVELOPER.md
```

Use the required commit message:

```bash
git commit -m "docs: complete developer profile"
```

## Important Rule

Do not implement future sprint requirements before their tickets are released.

Official requirements are maintained in the CSMS specifications repository and
in Moodle.