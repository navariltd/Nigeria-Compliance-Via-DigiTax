# Nigeria Compliance Via Digitax

Federal Inland Revenue Service (FIRS) integration via Digitax by Navari Ltd for Nigeria.

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app nigeria_compliance_via_digitax
```

## Features

### Automatic HS Code and Service Code Loading

When the app is installed, it automatically loads:

- **HS Codes** for Items from [hs-codes.json](https://raw.githubusercontent.com/namiri-tech/docs-rdme-ng/refs/heads/v1.0/assets/hs-codes.json)
- **Service Codes** from [service-codes.csv](https://raw.githubusercontent.com/namiri-tech/docs-rdme-ng/refs/heads/v1.0/assets/service-codes.csv)

These codes are required for DigiTax integration to generate unique item IDs for tax compliance.

### Manual Code Management

If you need to reload the codes manually, you can use the following methods:

**From Frappe Console:**

```python
# Get statistics about loaded codes
frappe.call("nigeria_compliance_via_digitax.utils.get_codes_stats")

# Load codes only if missing
frappe.call("nigeria_compliance_via_digitax.utils.load_codes_if_missing")

# Reload all codes (this will delete existing and reload)
frappe.call("nigeria_compliance_via_digitax.utils.reload_codes")
```

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/nigeria_compliance_via_digitax
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

## CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

## License

MIT
