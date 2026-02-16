# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import csv
import frappe
import json
import os
import requests

from frappe import _
from io import StringIO


def after_install():
    frappe.logger().info(
        "Starting Nigeria Compliance Via Digitax installation setup..."
    )

    load_hs_codes()
    load_service_codes()
    load_tax_categories()

    frappe.logger().info(
        "Nigeria Compliance Via Digitax installation setup completed successfully."
    )


def load_hs_codes():
    """
    Load and populate HS (Harmonized System) codes from a remote JSON source.

    This function fetches HS codes from Namiri-Tech GitHub repository and imports them
    into the Digitax HS Code doctype. It skips the import if HS codes for
    the "Item" category already exist in the database.

    The function performs the following steps:
    1. Sends a GET request to fetch HS codes from the remote URL
    2. Checks if Item HS codes already exist in the database
    3. Iterates through each HS code entry and creates new Digitax HS Code documents
    4. Skips entries that already exist or lack required fields
    5. Commits all changes to the database

    Raises:
            frappe.exceptions.ValidationError: If the HTTP request fails or an error
                    occurs during HS code creation. The error message guides the user to
                    check their internet connection or provides details about the failure.

    Returns:
            None

    Side Effects:
            - Logs info and error messages to the Frappe logger
            - Creates new "Digitax HS Code" documents in the database
            - Commits database transactions
            - May display error messages to the user via frappe.throw()

    Note:
            - Existing Item HS codes are not reimported
            - The function uses ignore_permissions=True when inserting documents
            - HTTP timeout is set to 30 seconds
    """
    url = "https://raw.githubusercontent.com/namiri-tech/docs-rdme-ng/refs/heads/v1.0/assets/hs-codes.json"

    try:
        frappe.logger().info(f"Fetching HS codes from {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        hs_codes_data = response.json()

        existing_count = frappe.db.count("Digitax HS Code", {"category": "Item"})
        if existing_count > 0:
            frappe.logger().info(
                f"Found {existing_count} existing Item HS codes. Skipping import."
            )
            return

        created_count = 0
        for entry in hs_codes_data:
            hscode = None
            try:
                hscode = entry.get("hscode") or entry.get("code")
                description = entry.get("description", "")

                if not hscode:
                    continue

                if not frappe.db.exists(
                    "Digitax HS Code", {"hscode": hscode, "category": "Item"}
                ):
                    doc = frappe.get_doc(
                        {
                            "doctype": "Digitax HS Code",
                            "category": "Item",
                            "hscode": hscode,
                            "description": description,
                        }
                    )
                    doc.insert(ignore_permissions=True)
                    created_count += 1
            except Exception as e:
                frappe.logger().error(f"Error creating HS code {hscode}: {str(e)}")
                continue

        frappe.db.commit()
        frappe.logger().info(f"Successfully loaded {created_count} HS codes (Items).")

    except requests.exceptions.RequestException as e:
        frappe.logger().error(f"Failed to fetch HS codes from {url}: {str(e)}")
        frappe.throw(
            _("Could not load HS codes. Please check your internet connection and try again.")
        )
    except Exception as e:
        frappe.logger().error(f"Error loading HS codes: {str(e)}")
        frappe.throw(_("An error occurred while loading HS codes: {0}").format(str(e)))


def load_service_codes():
    """
    Load service codes from a remote CSV file and populate the Digitax HS Code database.

    This function fetches service codes from Namiri-Tech GitHub repository and creates Digitax HS Code
    records in the database. It skips the import if service codes already exist to prevent
    duplicates.

    Process:
    1. Fetches service codes from a remote CSV URL with a 30-second timeout
    2. Checks if service codes already exist in the database
    3. Iterates through CSV rows and creates new Digitax HS Code documents for each unique code
    4. Logs errors for individual records without stopping the entire process
    5. Commits all changes to the database upon completion

    Raises:
            frappe.ValidationError: If the remote URL is unreachable or if a general error occurs
                    during the loading process

    Returns:
            None

    Side Effects:
            - Creates new Digitax HS Code records in the database
            - Logs info and error messages using frappe.logger()
            - Commits database transactions
    """
    url = "https://raw.githubusercontent.com/namiri-tech/docs-rdme-ng/refs/heads/v1.0/assets/service-codes.csv"

    try:
        frappe.logger().info(f"Fetching service codes from {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        csv_data = StringIO(response.text)
        csv_reader = csv.DictReader(csv_data)

        existing_count = frappe.db.count("Digitax HS Code", {"category": "Service"})
        if existing_count > 0:
            frappe.logger().info(
                f"Found {existing_count} existing Service codes. Skipping import."
            )
            return

        created_count = 0
        for row in csv_reader:
            code = None
            try:
                code = row.get("code", "").strip()
                description = row.get("description", "").strip()

                if not code:
                    continue

                if not frappe.db.exists(
                    "Digitax HS Code", {"hscode": code, "category": "Service"}
                ):
                    doc = frappe.get_doc(
                        {
                            "doctype": "Digitax HS Code",
                            "category": "Service",
                            "hscode": code,
                            "description": description,
                        }
                    )
                    doc.insert(ignore_permissions=True)
                    created_count += 1
            except Exception as e:
                frappe.logger().error(f"Error creating service code {code}: {str(e)}")
                continue

        frappe.db.commit()
        frappe.logger().info(f"Successfully loaded {created_count} service codes.")

    except requests.exceptions.RequestException as e:
        frappe.logger().error(f"Failed to fetch service codes from {url}: {str(e)}")
        frappe.throw(
            _("Could not load service codes. Please check your internet connection and try again.")
        )
    except Exception as e:
        frappe.logger().error(f"Error loading service codes: {str(e)}")
        frappe.throw(_("An error occurred while loading service codes: {0}").format(str(e)))


# TODO: Remove this functionality before moving to production, as tax categories should be loaded from the DigiTax API instead of a local JSON file.
def load_tax_categories():
    """
    Load tax categories from local JSON file and create Tax Category documents.

    This function reads tax categories from a local JSON file in the assets folder and creates
    Tax Category documents in the ERPNext system. Each tax category code is used as the
    title of the Tax Category document.

    Process:
    1. Checks if tax categories already exist in the database
    2. Reads tax categories from the local JSON file
    3. Iterates through the JSON data and creates new Tax Category documents
    4. Logs errors for individual records without stopping the entire process
    5. Commits all changes to the database upon completion

    Raises:
            frappe.ValidationError: If the file cannot be read or if a general error occurs
                    during the loading process

    Returns:
            None

    Side Effects:
            - Creates new Tax Category records in the database
            - Logs info and error messages using frappe.logger()
            - Commits database transactions

    Note:
            - The function checks if Tax Category doctype is available in the system
            - Existing tax categories are not reimported
            - The function uses ignore_permissions=True when inserting documents
            - Tax categories are loaded from: assets/tax_category.json
    """
    try:
        if not frappe.db.exists("DocType", "Digitax Tax Category"):
            frappe.logger().warning(
                "Digitax Tax Category doctype not found. Skipping tax category import."
            )
            return

        existing_count = frappe.db.count("Digitax Tax Category")
        if existing_count > 0:
            frappe.logger().info(
                f"Found {existing_count} existing Digitax Tax Categories. Skipping import."
            )
            return

        app_path = frappe.get_app_path("nigeria_compliance_via_digitax")
        json_file_path = os.path.join(app_path, "assets", "tax_category.json")

        if not os.path.exists(json_file_path):
            frappe.logger().error(f"Tax category file not found at: {json_file_path}")
            frappe.throw(
                _("Tax category data file not found. Please ensure tax_category.json exists in the assets folder.")
            )

        frappe.logger().info(f"Loading tax categories from {json_file_path}...")

        with open(json_file_path, "r", encoding="utf-8") as f: # nosemgrep
            tax_categories_data = json.load(f)

        created_count = 0

        for entry in tax_categories_data:
            category_name = None
            try:
                tax_code = entry.get("tax_code", "")
                category_name = entry.get("category_name", "")
                tax_rate = entry.get("tax_rate")
                has_tax_rate = entry.get("has_tax_rate", False)

                if not tax_code or not category_name:
                    continue

                if not frappe.db.exists("Digitax Tax Category", category_name):
                    doc = frappe.get_doc(
                        {
                            "doctype": "Digitax Tax Category",
                            "category_name": category_name,
                            "tax_code": tax_code,
                            "tax_rate": tax_rate,
                            "has_tax_rate": has_tax_rate,
                        }
                    )
                    doc.insert(ignore_permissions=True)
                    created_count += 1
            except Exception as e:
                frappe.logger().error(
                    _("Error creating tax category {0}: {1}").format(category_name, str(e))
                )
                continue

        frappe.db.commit()
        frappe.logger().info(f"Successfully loaded {created_count} tax categories.")

    except FileNotFoundError as e:
        frappe.logger().error(f"Tax category file not found: {str(e)}")
        frappe.throw(
            _("Could not find tax category data file. Please ensure tax_category.json exists in the assets folder.")
        )
    except json.JSONDecodeError as e:
        frappe.logger().error(f"Invalid JSON in tax category file: {str(e)}")
        frappe.throw(
            _("Tax category data file contains invalid JSON. Please check the file format.")
        )
    except Exception as e:
        frappe.logger().error(f"Error loading tax categories: {str(e)}")
        frappe.throw(_("An error occurred while loading tax categories: {0}").format(str(e)))


def reload_digitax_category_codes():
    frappe.logger().info("Reloading Digitax category codes...")

    frappe.db.delete("Digitax HS Code")

    # Only delete Digitax Tax Categories if the doctype exists
    if frappe.db.exists("DocType", "Digitax Tax Category"):
        frappe.db.delete("Digitax Tax Category")

    frappe.db.commit() # nosemgrep

    load_hs_codes()
    load_service_codes()
    load_tax_categories()

    frappe.logger().info("Digitax codes reloaded successfully.")
