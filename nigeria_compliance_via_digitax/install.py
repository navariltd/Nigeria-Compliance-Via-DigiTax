# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import csv
import frappe
import requests

from frappe import _
from io import StringIO


def after_install():
    frappe.logger().info(
        "Starting Nigeria Compliance Via Digitax installation setup..."
    )

    load_hs_codes()
    load_service_codes()
    create_nrs_party_types()

    frappe.logger().info(
        "Nigeria Compliance Via Digitax installation setup completed successfully."
    )


def load_hs_codes():
    """
    Load and populate HS (Harmonized System) codes from a remote JSON source.

    This function fetches HS codes from Namiri-Tech GitHub repository and imports them
    into the NRS HS Code doctype. It skips the import if HS codes for
    the "Item" category already exist in the database.

    The function performs the following steps:
    1. Sends a GET request to fetch HS codes from the remote URL
    2. Checks if Item HS codes already exist in the database
    3. Iterates through each HS code entry and creates new NRS HS Code documents
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
            - Creates new "NRS HS Code" documents in the database
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

        existing_count = frappe.db.count("NRS HS Code", {"category": "Item"})
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
                    "NRS HS Code", {"hscode": hscode, "category": "Item"}
                ):
                    doc = frappe.get_doc(
                        {
                            "doctype": "NRS HS Code",
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
            _(
                "Could not load HS codes. Please check your internet connection and try again."
            )
        )
    except Exception as e:
        frappe.logger().error(f"Error loading HS codes: {str(e)}")
        frappe.throw(_("An error occurred while loading HS codes: {0}").format(str(e)))


def load_service_codes():
    """
    Load service codes from a remote CSV file and populate the NRS HS Code database.

    This function fetches service codes from Namiri-Tech GitHub repository and creates NRS HS Code
    records in the database. It skips the import if service codes already exist to prevent
    duplicates.

    Process:
    1. Fetches service codes from a remote CSV URL with a 30-second timeout
    2. Checks if service codes already exist in the database
    3. Iterates through CSV rows and creates new NRS HS Code documents for each unique code
    4. Logs errors for individual records without stopping the entire process
    5. Commits all changes to the database upon completion

    Raises:
            frappe.ValidationError: If the remote URL is unreachable or if a general error occurs
                    during the loading process

    Returns:
            None

    Side Effects:
            - Creates new NRS HS Code records in the database
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

        existing_count = frappe.db.count("NRS HS Code", {"category": "Service"})
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
                    "NRS HS Code", {"hscode": code, "category": "Service"}
                ):
                    doc = frappe.get_doc(
                        {
                            "doctype": "NRS HS Code",
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
            _(
                "Could not load service codes. Please check your internet connection and try again."
            )
        )
    except Exception as e:
        frappe.logger().error(f"Error loading service codes: {str(e)}")
        frappe.throw(
            _("An error occurred while loading service codes: {0}").format(str(e))
        )


def reload_digitax_category_codes():
    frappe.logger().info("Reloading Digitax category codes...")

    frappe.db.delete("NRS HS Code")

    # Only delete NRS Tax Categories if the doctype exists
    if frappe.db.exists("DocType", "NRS Tax Category"):
        frappe.db.delete("NRS Tax Category")

    # Only delete NRS Country Codes if the doctype exists
    if frappe.db.exists("DocType", "NRS Country Codes"):
        frappe.db.delete("NRS Country Codes")

    frappe.db.commit()  # nosemgrep

    load_hs_codes()
    load_service_codes()

    frappe.logger().info("Digitax codes reloaded successfully.")


def create_nrs_party_types():
    """
    Create NRS Party Types if they do not already exist.

    This function checks for the existence of predefined party types in the "NRS Party Type"
    doctype. If any of the party types are missing, it creates them.

    The predefined party types are:
        - "Consumer": Represents a consumer entity.
        - "Business": Represents a business entity or organization.
        - "Government": Represents a government entity or agency.

    Raises:
        frappe.ValidationError: If an error occurs while creating a party type.
    """
    nrs_party_types = [
        {
            "party_type": "Consumer",
            "invoice_type": "B2C",
        },
        {
            "party_type": "Business",
            "invoice_type": "B2B",
        },
        {
            "party_type": "Government",
            "invoice_type": "B2G",
        }
    ]

    for party_type in nrs_party_types:
        if not frappe.db.exists("NRS Party Type", {"party_type": party_type["party_type"]}):
            try:
                doc = frappe.get_doc({
                    "doctype": "NRS Party Type",
                    "party_type": party_type["party_type"],
                    "invoice_type": party_type["invoice_type"]
                })
                doc.insert(ignore_permissions=True)
                frappe.logger().info(f"Created NRS Party Type: {party_type['party_type']}")
            except Exception as e:
                frappe.logger().error(f"Error creating NRS Party Type {party_type['party_type']}: {str(e)}")
                frappe.throw(_("An error occurred while creating NRS Party Type {0}: {1}").format(party_type['party_type'], str(e)))
