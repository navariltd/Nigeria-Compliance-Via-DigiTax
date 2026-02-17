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
				title=_("Configuration Error"),
			)
		return frappe.get_doc("FIRS Settings", {"company": self.company})

	def _get_environment(self):
		"""Fetch the DigiTax environment settings"""
		environment_name = self.settings.environment

		if not environment_name:
			frappe.throw(
				_("No environment configured in FIRS Settings for {0}").format(
					self.company
				),
				title=_("Configuration Error"),
			)

		if not frappe.db.exists("DigiTax Environment", environment_name):
			frappe.throw(
				_("DigiTax Environment '{0}' not found").format(environment_name),
				title=_("Configuration Error"),
			)

		return frappe.get_doc("DigiTax Environment", environment_name)

	def _get_api_key(self) -> str:
		"""Get the API key from the environment document"""
		api_key = self.environment.get_password(fieldname="api_key")

		if not api_key:
			frappe.throw(
				_("API Key not configured for environment {0}").format(
					self.environment.name
				),
				title=_("Configuration Error"),
			)

		return api_key

	def _build_auth_headers(self) -> Dict[str, str]:
		"""Build authentication headers for API requests"""
		return {"Content-Type": "application/json", "X-API-KEY": self.api_key}

	def _build_url(self, endpoint: str) -> str:
		if not self.base_url.endswith("/"):
			self.base_url += "/"
		if not endpoint.startswith("/"):
			endpoint = f"/{endpoint}"
		return f"{self.base_url}{endpoint}"

	def _extract_error_message(self, error: requests.exceptions.HTTPError) -> str:
		try:
			response_data = error.response.json()
			return response_data.get("message") or response_data.get("error") or str(error)
		except:
			return error.response.text or str(error)

	def post(
		self,
		endpoint: str,
		data: Dict[str, Any],
		reference_doctype: Optional[str] = None,
		reference_docname: Optional[str] = None,
	) -> Optional[Dict[str, Any]]:
		"""
		Make a POST request to the DigiTax API

		Args:
			endpoint: API endpoint (e.g., "/items")
			data: Request payload
			reference_doctype: DocType of the document making this request (e.g., "Item")
			reference_docname: Name of the document making this request (e.g., "PRODUCT-001")

		Returns:
			Response data as dictionary or None if request fails

		Raises:
			DigitaxAPIException: If the API request fails
		"""
		url = self._build_url(endpoint)
		integration_request = None

		try:
			# Create Integration Request to log this API call
			integration_request = self._create_integration_request(
				url=url,
				request_data=data,
				reference_doctype=reference_doctype,
				reference_docname=reference_docname,
			)

			frappe.logger().info(f"DigiTax API Request: POST {url}")
			frappe.logger().debug(f"Request data: {json.dumps(data, indent=2)}")

			response = requests.post(
				url, headers=self.headers, data=json.dumps(data), timeout=self.timeout
			)

			response.raise_for_status()
			response_data = response.json()

			frappe.logger().info(f"DigiTax API Response: {response.status_code}")
			frappe.logger().debug(
				f"Response data: {json.dumps(response_data, indent=2)}"
			)

			# Update Integration Request with successful response
			self._update_integration_request(
				integration_request=integration_request,
				status="Completed",
				response_data=response_data,
				status_code=response.status_code,
			)

			return response_data

		except requests.exceptions.HTTPError as e:
			self._handle_http_error(e, url, integration_request)
		except requests.exceptions.ConnectionError as e:
			self._handle_connection_error(e, url, integration_request)
		except requests.exceptions.Timeout as e:
			self._handle_timeout_error(e, url, integration_request)
		except requests.exceptions.RequestException as e:
			self._handle_generic_error(e, url, integration_request)
		except json.JSONDecodeError as e:
			self._handle_json_error(e, url, integration_request)

		return None

	def _create_integration_request(
		self,
		url: str,
		request_data: dict,
		reference_doctype: Optional[str] = None,
		reference_docname: Optional[str] = None,
	):
		"""Create an Integration Request document to log the API call"""
		try:
			integration_request = frappe.get_doc(
				{
					"doctype": "Integration Request",
					"integration_type": "Remote",
					"integration_request_service": "DigiTax Nigeria",
					"method": "POST",
					"url": url,
					"request_headers": json.dumps(
						self._sanitize_headers(self.headers), indent=2
					),
					"data": json.dumps(request_data, indent=2),
					"reference_doctype": reference_doctype,
					"reference_docname": reference_docname,
					"status": "Queued",
				}
			)
			integration_request.insert(ignore_permissions=True)
			frappe.db.commit()
			return integration_request
		except Exception as e:
			frappe.logger().error(f"Failed to create Integration Request: {str(e)}")
			return None

	def _update_integration_request(
		self,
		integration_request,
		status: str,
		response_data: Optional[dict] = None,
		error: Optional[str] = None,
		status_code: Optional[int] = None,
	):
		"""Update Integration Request with response or error"""
		if not integration_request:
			return

		try:
			integration_request.status = status

			if response_data:
				integration_request.output = json.dumps(response_data, indent=2)

			if error:
				integration_request.error = str(error)

			if status_code:
				integration_request.status_code = status_code

			integration_request.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.logger().error(f"Failed to update Integration Request: {str(e)}")

	def _sanitize_headers(self, headers: dict) -> dict:
		"""Remove sensitive information from headers before logging"""
		sanitized = headers.copy()
		if "X-API-KEY" in sanitized:
			sanitized["X-API-KEY"] = "***REDACTED***"
		return sanitized

	def _handle_http_error(
		self, error: requests.exceptions.HTTPError, url: str, integration_request=None
	) -> None:
		"""Handle HTTP errors (4xx, 5xx)"""
		error_message = self._extract_error_message(error)

		frappe.log_error(
			title="DigiTax HTTP Error",
			message=f"URL: {url}\nStatus: {error.response.status_code}\nError: {error_message}",
		)

		# Update Integration Request with error
		self._update_integration_request(
			integration_request=integration_request,
			status="Failed",
			error=error_message,
			status_code=error.response.status_code,
			response_data=self._safe_json_response(error.response),
		)

		raise DigitaxAPIException(f"HTTP {error.response.status_code}: {error_message}")

	def _handle_connection_error(
		self,
		error: requests.exceptions.ConnectionError,
		url: str,
		integration_request=None,
	) -> None:
		"""Handle connection errors"""
		error_message = (
			"Failed to connect to DigiTax API. Please check your network connection."
		)

		frappe.log_error(
			title="DigiTax Connection Error", message=f"URL: {url}\nError: {str(error)}"
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(error_message)

	def _handle_timeout_error(
		self, error: requests.exceptions.Timeout, url: str, integration_request=None
	) -> None:
		"""Handle timeout errors"""
		error_message = "DigiTax API request timed out. Please try again."

		frappe.log_error(
			title="DigiTax Timeout Error",
			message=f"URL: {url}\nTimeout: {self.timeout}s\nError: {str(error)}",
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(error_message)

	def _handle_generic_error(
		self,
		error: requests.exceptions.RequestException,
		url: str,
		integration_request=None,
	) -> None:
		"""Handle generic request errors"""
		frappe.log_error(
			title="DigiTax Request Error", message=f"URL: {url}\nError: {str(error)}"
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(
			f"An error occurred while communicating with DigiTax API: {str(error)}"
		)

	def _handle_json_error(
		self, error: json.JSONDecodeError, url: str, integration_request=None
	) -> None:
		"""Handle JSON decode errors"""
		error_message = "Invalid response received from DigiTax API."

		frappe.log_error(
			title="DigiTax JSON Error", message=f"URL: {url}\nError: {str(error)}"
		)

		self._update_integration_request(
			integration_request=integration_request, status="Failed", error=str(error)
		)

		raise DigitaxAPIException(error_message)

	def _safe_json_response(self, response):
		"""Safely extract JSON from response"""
		try:
			return response.json()
		except:
			return {"raw_response": response.text[:1000]}  # Limit length
