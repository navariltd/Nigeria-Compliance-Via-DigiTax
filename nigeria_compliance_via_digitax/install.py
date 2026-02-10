# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import frappe
import requests
import csv
from io import StringIO


def after_install():
    frappe.logger().info(
        "Starting Nigeria Compliance Via Digitax installation setup..."
    )

    load_hs_codes()
    load_service_codes()

    frappe.logger().info(
        "Nigeria Compliance Via Digitax installation setup completed successfully."
    )


def load_hs_codes():
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
            f"Could not load HS codes. Please check your internet connection and try again."
        )
    except Exception as e:
        frappe.logger().error(f"Error loading HS codes: {str(e)}")
        frappe.throw(f"An error occurred while loading HS codes: {str(e)}")


def load_service_codes():
    """
    Load service codes from the remote CSV source and create Digitax HS Code records
    with category='Service'.
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
            f"Could not load service codes. Please check your internet connection and try again."
        )
    except Exception as e:
        frappe.logger().error(f"Error loading service codes: {str(e)}")
        frappe.throw(f"An error occurred while loading service codes: {str(e)}")


def reload_digitax_codes():
    frappe.logger().info("Reloading Digitax codes...")

    frappe.db.delete("Digitax HS Code")
    frappe.db.commit()

    load_hs_codes()
    load_service_codes()

    frappe.logger().info("Digitax codes reloaded successfully.")
