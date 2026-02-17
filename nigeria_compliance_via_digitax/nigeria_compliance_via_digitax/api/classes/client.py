import frappe
import json
import requests

from frappe import _


class DigitaxClient:
	def __init__(self, company=None) -> None:
		if not company:
			company = frappe.defaults.get_user_default("company")

		self.company = company
		self.settings = self._get_settings()
		self.environment = self._get_environment()
		self.base_url = self._get_base_url()
		self.api_key = self._get_api_key()
		self.headers = self._get_auth_headers()

	def _get_auth_headers(self):
		return {"Content-Type": "application/json", "X-API-KEY": self.api_key}

	def _get_base_url(self):
		return self.environment.base_url

	def _get_api_key(self):
		env_doc = frappe.get_doc("DigiTax Environment", self.environment.name)
		api_key = env_doc.get_password(fieldname="api_key")
		return api_key

	def _get_environment(self):
		environment_name = self.settings.environment
		environment = frappe.get_doc("DigiTax Environment", environment_name)
		return environment

	def _get_settings(self):
		settings = frappe.get_doc("FIRS Settings", {"company": self.company})
		return settings

	def post(self, endpoint, data):
		url = f"{self.base_url}{endpoint}"
		response = None

		try:
			response = requests.post(
				url, headers=self.headers, data=json.dumps(data), timeout=20
			)
			response.raise_for_status()

			return response.json()
		except requests.exceptions.RequestException as e:
			frappe.log_error(
				f"DigiTax API Error: {str(e)}", "Digitax Integration Error"
			)
			frappe.msgprint(
				msg=_(f"{str(e)}"), title="DigiTax Integration Error", indicator="red"
			)
