import frappe
import json
import requests

from frappe import _


class DigitaxClient:
	def __init__(self, company=None) -> None:
		if not company:
			company = frappe.defaults.get_user_default("company")

		self.settings = frappe.get_doc("FIRS Settings", {"company": company})
		self.environment = frappe.get_doc("DigiTax Environment", self.settings.environment_name)
		self.base_url = self.environment.base_url
		self.api_key = frappe.get_password("DigiTax Environment", self.settings.environment_name, "api_key")
		self.headers = {
			"Content-Type": "application/json",
			"X-API-KEY": self.api_key
		}

	def post(self, endpoint, data):
		url = f"{self.base_url}{endpoint}"

		try:
			response = requests.post(url, headers=self.headers, data=json.dumps(data), timeout=20)
			response.raise_for_status()

			return response.json()
		except requests.exceptions.RequestException as e:
			frappe.log_error(f"DigiTax API Error: {str(e)}", "Digitax Integration Error")
			frappe.msgprint(msg=_(f"{str(e)}"), title="DigiTax Integration Error", indicator="red")
