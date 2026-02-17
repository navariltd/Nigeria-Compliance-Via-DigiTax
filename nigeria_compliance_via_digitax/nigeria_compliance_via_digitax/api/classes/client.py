import frappe
import json
import requests
from typing import Dict, Any, Optional
from frappe import _


class DigitaxAPIException(Exception):
	"""Custom exception for DigiTax API errors"""
	pass


class DigitaxClient:
	"""Client for interacting with the DigiTax API"""

	def __init__(self, company: Optional[str] = None) -> None:
		"""
		Initialize the DigiTax client

		Args:
			company: Company name. Defaults to user's default company if not provided
		"""
		self.company = company or self._get_default_company()
		self.settings = self._get_settings()
		self.environment = self._get_environment()
		self.base_url = self.environment.base_url
		self.api_key = self._get_api_key()
		self.headers = self._build_auth_headers()
		self.timeout = 20

	def _get_default_company(self) -> str:
		"""Get the default company for the current user"""
		company = frappe.defaults.get_user_default("company")
		if not company:
			frappe.throw(_("No default company found for user"))
		return company

	def _get_settings(self):
		"""Fetch FIRS settings for the company"""
		if not frappe.db.exists("FIRS Settings", {"company": self.company}):
			frappe.throw(
				_("FIRS Settings not found for company {0}").format(self.company),
				title=_("Configuration Error")
			)
		return frappe.get_doc("FIRS Settings", {"company": self.company})

	def _get_environment(self):
		"""Fetch the DigiTax environment settings"""
		environment_name = self.settings.environment

		if not environment_name:
			frappe.throw(
				_("No environment configured in FIRS Settings for {0}").format(self.company),
				title=_("Configuration Error")
			)

		if not frappe.db.exists("DigiTax Environment", environment_name):
			frappe.throw(
				_("DigiTax Environment '{0}' not found").format(environment_name),
				title=_("Configuration Error")
			)

		return frappe.get_doc("DigiTax Environment", environment_name)

	def _get_api_key(self) -> str:
		"""Get the API key from the environment document"""
		api_key = self.environment.get_password(fieldname="api_key")

		if not api_key:
			frappe.throw(
				_("API Key not configured for environment {0}").format(self.environment.name),
				title=_("Configuration Error")
			)

		return api_key

	def _build_auth_headers(self) -> Dict[str, str]:
		"""Build authentication headers for API requests"""
		return {
			"Content-Type": "application/json",
			"X-API-KEY": self.api_key
		}

	def post(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		"""
		Make a POST request to the DigiTax API

		Args:
			endpoint: API endpoint (e.g., "/items")
			data: Request payload

		Returns:
			Response data as dictionary or None if request fails

		Raises:
			DigitaxAPIException: If the API request fails
		"""
		url = self._build_url(endpoint)

		try:
			frappe.logger().info(f"DigiTax API Request: POST {url}")
			frappe.logger().debug(f"Request data: {json.dumps(data, indent=2)}")

			response = requests.post(
				url,
				headers=self.headers,
				data=json.dumps(data),
				timeout=self.timeout
			)

			response.raise_for_status()
			response_data = response.json()

			frappe.logger().info(f"DigiTax API Response: {response.status_code}")
			frappe.logger().debug(f"Response data: {json.dumps(response_data, indent=2)}")

			return response_data

		except requests.exceptions.HTTPError as e:
			self._handle_http_error(e, url)
		except requests.exceptions.ConnectionError as e:
			self._handle_connection_error(e, url)
		except requests.exceptions.Timeout as e:
			self._handle_timeout_error(e, url)
		except requests.exceptions.RequestException as e:
			self._handle_generic_error(e, url)
		except json.JSONDecodeError as e:
			self._handle_json_error(e, url)

		return None

	def _build_url(self, endpoint: str) -> str:
		if not self.base_url.endswith("/"):
			self.base_url += "/"
		if not endpoint.startswith("/"):
			endpoint = f"/{endpoint}"
		return f"{self.base_url}{endpoint}"

	def _handle_http_error(self, error: requests.exceptions.HTTPError, url: str) -> None:
		"""Handle HTTP errors (4xx, 5xx)"""
		error_message = self._extract_error_message(error)

		frappe.log_error(
			title="DigiTax HTTP Error",
			message=f"URL: {url}\nStatus: {error.response.status_code}\nError: {error_message}"
		)

		frappe.msgprint(
			msg=_("DigiTax API Error: {0}").format(error_message),
			title=_("API Error"),
			indicator="red"
		)

	def _handle_connection_error(self, error: requests.exceptions.ConnectionError, url: str) -> None:
		"""Handle connection errors"""
		frappe.log_error(
			title="DigiTax Connection Error",
			message=f"URL: {url}\nError: {str(error)}"
		)

		frappe.msgprint(
			msg=_("Failed to connect to DigiTax API. Please check your network connection."),
			title=_("Connection Error"),
			indicator="red"
		)

	def _handle_timeout_error(self, error: requests.exceptions.Timeout, url: str) -> None:
		"""Handle timeout errors"""
		frappe.log_error(
			title="DigiTax Timeout Error",
			message=f"URL: {url}\nTimeout: {self.timeout}s\nError: {str(error)}"
		)

		frappe.msgprint(
			msg=_("DigiTax API request timed out. Please try again."),
			title=_("Timeout Error"),
			indicator="orange"
		)

	def _handle_generic_error(self, error: requests.exceptions.RequestException, url: str) -> None:
		"""Handle generic request errors"""
		frappe.log_error(
			title="DigiTax Request Error",
			message=f"URL: {url}\nError: {str(error)}"
		)

		frappe.msgprint(
			msg=_("An error occurred while communicating with DigiTax API: {0}").format(str(error)),
			title=_("Request Error"),
			indicator="red"
		)

	def _handle_json_error(self, error: json.JSONDecodeError, url: str) -> None:
		"""Handle JSON decode errors"""
		frappe.log_error(
			title="DigiTax JSON Error",
			message=f"URL: {url}\nError: {str(error)}"
		)

		frappe.msgprint(
			msg=_("Invalid response received from DigiTax API."),
			title=_("Response Error"),
			indicator="red"
		)

	def _extract_error_message(self, error: requests.exceptions.HTTPError) -> str:
		"""Extract error message from HTTP error response"""
		try:
			error_data = error.response.json()
			return error_data.get("message") or error_data.get("error") or str(error)
		except (json.JSONDecodeError, AttributeError):
			return str(error)
