import frappe
from typing import Tuple, Optional
from frappe import _
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
    DigitaxAPIException,
)


def get_digitax_item_code(doc, method: Optional[str] = None) -> None:
    """
    Hook to sync item with DigiTax API when item is saved

    Args:
        doc: Item document
        method: Method name (on_update, after_insert, etc.)
    """
    if not doc.allow_firs_tracking:
        return

    if doc.digitax_id:
        frappe.logger().info(
            f"Item {doc.name} already has DigiTax ID: {doc.digitax_id}"
        )
        return

    try:
        _validate_item_data(doc)

        req_data = _build_item_request_data(doc)

        client = DigitaxClient()
        api_response = client.post("/items", req_data)

        if api_response:
            _update_item_with_digitax_id(doc, api_response)

    except DigitaxAPIException as e:
        frappe.log_error(
            title="DigiTax Item Sync Failed",
            message=f"Item: {doc.name}\nError: {str(e)}",
        )
        frappe.msgprint(
            msg=_("Failed to sync item with DigiTax. The item has been saved locally."),
            title=_("Sync Warning"),
            indicator="orange",
        )
    except Exception as e:
        frappe.log_error(
            title="DigiTax Item Sync Error",
            message=f"Item: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}",
        )


def _validate_item_data(doc) -> None:
    """
    Validate that all required fields are present

    Args:
        doc: Item document

    Raises:
        frappe.ValidationError: If required fields are missing
    """
    required_fields = {
        "firs_tax_category": "FIRS Tax Category",
        "firs_product_category": "FIRS Product Category",
    }

    missing_fields = []
    for field, label in required_fields.items():
        if not doc.get(field):
            missing_fields.append(label)

    if missing_fields:
        frappe.throw(
            _("Please fill in the following required fields: {0}").format(
                ", ".join(missing_fields)
            ),
            title=_("Missing Required Fields"),
        )


def _build_item_request_data(doc) -> dict:
    """
    Build the request payload for DigiTax API

    Args:
        doc: Item document

    Returns:
        Dictionary containing the request data
    """
    tax_category_code = get_tax_category_code(doc.firs_tax_category)
    hsn_code, is_service = get_hsn_code(doc.firs_product_category)

    return {
        "tax_category_code": tax_category_code,
        "product_category": doc.firs_product_category,
        "hsn_code": hsn_code,
        "item_name": doc.item_name or doc.name,
        "description": _get_item_description(doc),
        "is_service": bool(is_service),
    }


def _get_item_description(doc) -> str:
    """
    Get item description, stripping HTML if present

    Args:
        doc: Item document

    Returns:
        Plain text description
    """
    description = doc.description or doc.item_name or doc.name

    # Strip HTML tags if present
    if "<" in description and ">" in description:
        from frappe.utils import strip_html

        description = strip_html(description)

    return description


def _update_item_with_digitax_id(doc, api_response: dict) -> None:
    """
    Update the item document with DigiTax ID from API response

    Args:
        doc: Item document
        api_response: Response from DigiTax API
    """
    digitax_item_id = api_response.get("id")

    if not digitax_item_id:
        frappe.logger().warning(
            f"DigiTax API response for item {doc.name} did not contain 'id' field"
        )
        return

    # Update the document without triggering hooks
    doc.db_set("digitax_id", digitax_item_id, commit=True, update_modified=False)

    frappe.logger().info(f"Updated item {doc.name} with DigiTax ID: {digitax_item_id}")

    frappe.msgprint(
        msg=_("Item successfully synced with DigiTax. ID: {0}").format(digitax_item_id),
        title=_("Sync Successful"),
        indicator="green",
    )


def get_tax_category_code(firs_tax_category: str) -> str:
    """
    Get tax category code from FIRS Tax Category

    Args:
        firs_tax_category: Name of FIRS Tax Category

    Returns:
        Tax category code

    Raises:
        frappe.DoesNotExistError: If tax category doesn't exist
    """
    if not firs_tax_category:
        frappe.throw(_("FIRS Tax Category is required"))

    tax_code = frappe.db.get_value("FIRS Tax Category", firs_tax_category, "tax_code")

    if not tax_code:
        frappe.throw(
            _("Tax code not found for FIRS Tax Category: {0}").format(firs_tax_category)
        )

    return tax_code


def get_hsn_code(firs_product_category: str) -> Tuple[str, int]:
    """
    Get HSN code and service flag from FIRS Product Category

    Args:
        firs_product_category: Name of FIRS Product Category

    Returns:
        Tuple of (hs_code, is_service)

    Raises:
        frappe.DoesNotExistError: If product category doesn't exist
    """
    if not firs_product_category:
        frappe.throw(_("FIRS Product Category is required"))

    result = frappe.db.get_value(
        "FIRS Product Category",
        firs_product_category,
        ["hs_code", "is_service"],
        as_dict=False,
    )

    if not result:
        frappe.throw(
            _("FIRS Product Category not found: {0}").format(firs_product_category)
        )

    hs_code, is_service = result

    if not hs_code:
        frappe.throw(
            _("HS Code not configured for FIRS Product Category: {0}").format(
                firs_product_category
            )
        )

    return hs_code, is_service or 0
